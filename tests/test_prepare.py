import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from reviewer_prepare import build_context, collect_intent, run_tools
from reviewer_scope import compute_scope
from tests.helpers import commit, git, make_repo, run_cli, write


def fake_tool(bin_dir, name, body):
    """An executable `name` in bin_dir running `body` as Python."""
    path = pathlib.Path(bin_dir) / name
    path.write_text(f"#!{sys.executable}\nimport sys, json, pathlib\n{body}\n")
    path.chmod(0o755)


def scope_for(files):
    return {"base": "HEAD", "branch": "feat", "files": files, "keep_markers": []}


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.bin = tempfile.mkdtemp()
        # Only fake tools on PATH, plus git, which run_tools uses to list source files.
        os.symlink(shutil.which("git"), pathlib.Path(self.bin) / "git")
        self.path_env = mock.patch.dict(os.environ, {"PATH": self.bin})
        self.path_env.start()
        self.addCleanup(self.path_env.stop)

    def test_missing_tool_is_recorded_not_fatal(self):
        scope = scope_for([{"path": "a.py", "lang": "python", "ranges": [[1, 5]]},
                           {"path": "b.ts", "lang": "typescript-react", "ranges": [[1, 5]]}])
        out = run_tools(self.repo, scope)
        self.assertEqual(out["tools"], {t: "missing" for t in
                                        ["vulture", "jscpd", "knip", "ruff", "eslint"]})
        self.assertEqual((out["hints"], out["lint"]), ([], []))

    def test_only_tools_for_scope_languages(self):
        out = run_tools(self.repo, scope_for([{"path": "a.py", "lang": "python",
                                               "ranges": [[1, 5]]}]))
        self.assertEqual(set(out["tools"]), {"vulture", "jscpd", "ruff"})

    def test_vulture_adapter_maps_to_cm01(self):
        fake_tool(self.bin, "vulture",
                  "print(\"a.py:4: unused function 'x' (90% confidence)\")\nsys.exit(3)")
        out = run_tools(self.repo, scope_for([{"path": "a.py", "lang": "python",
                                               "ranges": [[2, 6]]}]))
        self.assertEqual(out["tools"]["vulture"], "ran")
        self.assertEqual(len(out["hints"]), 1)
        self.assertEqual(out["hints"][0]["rule"], "CM-01")
        self.assertEqual(out["hints"][0]["lines"], [4, 4])
        out = run_tools(self.repo, scope_for([{"path": "a.py", "lang": "python",
                                               "ranges": [[10, 12]]}]))
        self.assertEqual(out["hints"], [])

    def test_failing_tool_is_failed(self):
        fake_tool(self.bin, "vulture", "print('boom', file=sys.stderr)\nsys.exit(2)")
        out = run_tools(self.repo, scope_for([{"path": "a.py", "lang": "python",
                                               "ranges": [[1, 2]]}]))
        self.assertEqual(out["tools"]["vulture"], "failed")

    def test_jscpd_adapter_reads_report(self):
        write(self.repo, "package.json", json.dumps({"devDependencies": {"jscpd": "^4"}}))
        fake_tool(self.bin, "jscpd", """
out = pathlib.Path(sys.argv[sys.argv.index("--output") + 1])
out.mkdir(parents=True, exist_ok=True)
dup = {"firstFile": {"name": "a.ts", "start": 3, "end": 9},
       "secondFile": {"name": "b.ts", "start": 20, "end": 26}}
(out / "jscpd-report.json").write_text(json.dumps({"duplicates": [dup]}))""")
        scope = scope_for([{"path": "a.ts", "lang": "typescript-react", "ranges": [[1, 10]]}])
        out = run_tools(self.repo, scope)
        self.assertEqual(out["tools"]["jscpd"], "ran")
        self.assertEqual([(h["rule"], h["path"], h["lines"]) for h in out["hints"]],
                         [("CM-09", "a.ts", [3, 9])])

    def test_vulture_and_jscpd_see_the_whole_repo(self):
        # Unused-code and duplicate checks are wrong when only changed files are passed:
        # a new function called from unchanged code looks unused.
        write(self.repo, "package.json", json.dumps({"devDependencies": {"jscpd": "^4"}}))
        write(self.repo, "old.py", "def helper():\n    return 1\n")
        write(self.repo, "a.py", "from old import helper\n")
        commit(self.repo, "files")
        args_log = pathlib.Path(self.bin) / "args.txt"
        for name in ("vulture", "jscpd"):
            fake_tool(self.bin, name, f"pathlib.Path({str(args_log)!r}).open('a')"
                                      f".write({name!r} + ' ' + ' '.join(sys.argv[1:]) + '\\n')")
        run_tools(self.repo, scope_for([{"path": "a.py", "lang": "python", "ranges": [[1, 1]]}]))
        seen = {line.split()[0]: line.split()[1:] for line in args_log.read_text().splitlines()}
        self.assertIn("old.py", seen["vulture"])
        self.assertIn("old.py", seen["jscpd"])

    def test_node_tool_needs_package_json(self):
        fake_tool(self.bin, "jscpd", "sys.exit(0)")
        scope = scope_for([{"path": "a.ts", "lang": "typescript-react", "ranges": [[1, 10]]}])
        self.assertEqual(run_tools(self.repo, scope)["tools"]["jscpd"], "missing")

    def test_ruff_and_eslint_become_lint_on_changed_lines(self):
        write(self.repo, "package.json", json.dumps({"devDependencies": {"eslint": "^9"}}))
        root = str(self.repo.resolve())
        fake_tool(self.bin, "ruff", f"""
print(json.dumps([{{"filename": "{root}/a.py", "location": {{"row": 2}}, "code": "F401"}},
                  {{"filename": "{root}/a.py", "location": {{"row": 9}}, "code": "E501"}}]))
sys.exit(1)""")
        fake_tool(self.bin, "eslint", f"""
print(json.dumps([{{"filePath": "{root}/b.tsx", "messages": [{{"line": 1, "ruleId": "no-unused-vars"}}]}}]))
sys.exit(1)""")
        scope = scope_for([{"path": "a.py", "lang": "python", "ranges": [[1, 3]]},
                           {"path": "b.tsx", "lang": "typescript-react", "ranges": [[1, 3]]}])
        out = run_tools(self.repo, scope)
        self.assertEqual(sorted((l["tool"], l["path"], l["line"], l["code"]) for l in out["lint"]),
                         [("eslint", "b.tsx", 1, "no-unused-vars"), ("ruff", "a.py", 2, "F401")])

    def test_knip_unused_export_hint(self):
        write(self.repo, "package.json", json.dumps({"devDependencies": {"knip": "^5"}}))
        fake_tool(self.bin, "knip", """
print(json.dumps({"files": ["src/new.ts"], "issues": [{"file": "src/x.ts",
      "exports": [{"name": "helper", "line": 4, "col": 1}]}]}))
sys.exit(1)""")
        scope = scope_for([{"path": "src/x.ts", "lang": "typescript-react", "ranges": [[3, 5]]},
                           {"path": "src/new.ts", "lang": "typescript-react",
                            "ranges": [[1, 2], [6, 9]]}])
        hints = run_tools(self.repo, scope)["hints"]
        self.assertEqual([(h["path"], h["rule"], h["lines"]) for h in hints],
                         [("src/new.ts", "CM-01", [1, 9]), ("src/x.ts", "CM-01", [4, 4])])


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        git(self.repo, "checkout", "-q", "-b", "feat")

    def test_context_finds_callers(self):
        write(self.repo, "util.py", "import re\n\n\ndef slugify(text):\n    return re.sub(' ', '-', text)\n")
        write(self.repo, "views.py", "import util\n\nprint(util.slugify('A B'))\n")
        commit(self.repo, "slugify")
        pack = build_context(self.repo, compute_scope(self.repo))
        sym = next(s for s in pack["symbols"] if s["name"] == "slugify")
        self.assertEqual((sym["path"], sym["line"]), ("util.py", 4))
        self.assertEqual([(c["path"], c["line"]) for c in sym["callers"]], [("views.py", 3)])
        self.assertIn({"name": "slugify", "path": "util.py", "line": 4}, pack["index"])
        self.assertFalse(pack["truncated"])

    def test_context_ts_and_java_symbols(self):
        write(self.repo, "a.tsx", "export function Card() {}\nconst useThing = () => 1;\n")
        write(self.repo, "B.java", "public class B {\n    public static int size(int x) {\n"
              "        return x;\n    }\n}\n")
        names = {s["name"] for s in build_context(self.repo, compute_scope(self.repo))["symbols"]}
        self.assertEqual(names, {"Card", "useThing", "B", "size"})

    def test_context_dependencies_from_pyproject_and_package_json(self):
        write(self.repo, "pyproject.toml", '[project]\nname = "x"\ndependencies = [\n'
              '  "requests>=2",\n  "Click[extra]",\n]\n\n[dependency-groups]\n'
              'dev = ["pytest>=8", {include-group = "lint"}]\nlint = ["ruff"]\n')
        write(self.repo, "requirements-dev.txt", "# comment\n-r base.txt\nhttpx==0.27\n")
        write(self.repo, "package.json", json.dumps({"dependencies": {"react": "^18"},
                                                     "devDependencies": {"vitest": "^1"}}))
        write(self.repo, "pom.xml", "<project><dependencies><dependency>"
              "<artifactId>guava</artifactId></dependency></dependencies></project>")
        write(self.repo, "a.py", "x = 1\n")
        deps = build_context(self.repo, compute_scope(self.repo))["dependencies"]
        self.assertEqual(deps, sorted(["requests", "Click", "pytest", "ruff", "httpx", "react",
                                       "vitest", "guava"]))

    def test_pyproject_without_tomllib(self):
        write(self.repo, "pyproject.toml", '[project]\ndependencies = ["requests>=2"]\n\n'
              '[dependency-groups]\ndev = ["pytest", {include-group = "lint"}]\nlint = ["ruff"]\n')
        write(self.repo, "a.py", "x = 1\n")
        with mock.patch("reviewer_prepare.tomllib", None):
            deps = build_context(self.repo, compute_scope(self.repo))["dependencies"]
        self.assertEqual(deps, ["pytest", "requests", "ruff"])

    def test_context_truncates_to_budget(self):
        for i in range(30):
            write(self.repo, f"m{i}.py", f"def func_{i}(x):\n    return x\n")
        write(self.repo, "use.py", "".join(f"func_{i}(1)\n" for i in range(30)) * 3)
        pack = build_context(self.repo, compute_scope(self.repo), budget_chars=400)
        self.assertTrue(pack["truncated"])
        self.assertLessEqual(len(json.dumps(pack)), 400)
        big = build_context(self.repo, compute_scope(self.repo))
        self.assertFalse(big["truncated"])
        self.assertEqual(len(big["symbols"]), 30)


class IntentTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        git(self.repo, "checkout", "-q", "-b", "feat/csv-export")

    def test_intent_commits_and_plan(self):
        write(self.repo, "docs/csv-export-plan.md", "# Plan\nExport CSV.\n")
        write(self.repo, "docs/other-plan.md", "# Unrelated\n")
        commit(self.repo, "add plan")
        write(self.repo, "a.py", "x = 1\n")
        commit(self.repo, "feat: export rows\n\nBody line.")
        intent = collect_intent(self.repo, compute_scope(self.repo))
        self.assertEqual(intent["sources"], ["commits", "plan"])
        self.assertEqual(intent["branch"], "feat/csv-export")
        self.assertEqual(intent["commits"], ["feat: export rows\n\nBody line.", "add plan"])
        self.assertEqual([p["path"] for p in intent["plans"]], ["docs/csv-export-plan.md"])

    def test_intent_scratch_dir_and_cap(self):
        write(self.repo, ".scratch/csv-export/issues/01.md", "x" * 30000)
        intent = collect_intent(self.repo, compute_scope(self.repo))
        self.assertEqual(intent["sources"], ["plan"])
        self.assertEqual(len(intent["plans"][0]["text"]), 20000)

    def test_no_plan_lookup_on_default_branch(self):
        # On main the branch name says nothing about the task; "main" would match
        # any plan with "main" in its name.
        git(self.repo, "checkout", "-q", "main")
        write(self.repo, "docs/domain-plan.md", "# Unrelated\n")
        intent = collect_intent(self.repo, compute_scope(self.repo))
        self.assertEqual(intent["plans"], [])

    def test_intent_none_found(self):
        intent = collect_intent(self.repo, compute_scope(self.repo))
        self.assertEqual((intent["sources"], intent["commits"], intent["plans"]), ([], [], []))


class PrepareCliTest(unittest.TestCase):
    def test_cli_subcommands_print_json(self):
        repo = make_repo()
        write(repo, "a.py", "def f():\n    return 1\n")
        scope_file = write(repo, ".reviewer/run/scope.json", json.dumps(compute_scope(repo)))
        for cmd, key in [("tools", "tools"), ("context", "symbols"), ("intent", "sources")]:
            code, out, _ = run_cli(repo, cmd, "--scope", str(scope_file))
            self.assertEqual(code, 0, cmd)
            self.assertIn(key, json.loads(out))


if __name__ == "__main__":
    unittest.main()
