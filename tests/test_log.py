import json
import unittest

import reviewer_log as rl
from tests.helpers import commit, make_repo, run_cli, write

TWENTY = "".join(f"line {i}\n" for i in range(1, 21))


def run_rec(run_id, branch, head="h", **extra):
    return {"type": "run", "run_id": run_id, "branch": branch, "head": head, **extra}


def finding_rec(run_id, fid, path, lines, text, shown=True):
    return {"type": "finding", "run_id": run_id, "id": fid, "rule": "PY-02",
            "path": path, "lines": lines, "shown": shown, "kept": shown, "text": text}


class LogReadWriteTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def test_read_skips_corrupt_lines(self):
        rl.ensure_dir(self.repo)
        rl.log_path(self.repo).write_text(
            json.dumps(run_rec("r1", "main")) + "\n" + '{"type": "run", "ru')
        self.assertEqual(len(rl.read_records(self.repo)), 1)

    def test_read_missing_log_is_empty(self):
        self.assertEqual(rl.read_records(self.repo), [])

    def test_ensure_dir_writes_gitignore(self):
        d = rl.ensure_dir(self.repo)
        self.assertEqual((d / ".gitignore").read_text(), "*\n")

    def test_last_review_picks_newest_for_branch(self):
        rl.append_records(self.repo, [run_rec("r1", "main"), run_rec("r2", "main"),
                                      run_rec("r3", "feat")])
        self.assertEqual(rl.last_review(self.repo, "main")["run_id"], "r2")
        self.assertIsNone(rl.last_review(self.repo, "other"))


class ActedOnTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        write(self.repo, "a.py", TWENTY)
        head = commit(self.repo, "add a.py")
        rl.append_records(self.repo, [
            run_rec("r1", "main", head),
            finding_rec("r1", "f1", "a.py", [5, 8], rl.flagged_text(self.repo, "a.py", [5, 8]))])

    def edit_line(self, n):
        lines = TWENTY.splitlines(keepends=True)
        lines[n - 1] = "changed\n"
        write(self.repo, "a.py", "".join(lines))

    def test_acted_on_when_flagged_lines_change(self):
        self.edit_line(6)
        found = rl.detect_acted_on(self.repo, "r2")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], "f1")
        self.assertEqual(found[0]["run_id"], "r1")
        self.assertEqual(found[0]["detected_in"], "r2")

    def test_not_acted_on_when_other_lines_change(self):
        self.edit_line(15)
        self.assertEqual(rl.detect_acted_on(self.repo, "r2"), [])

    def test_not_acted_on_when_lines_only_shift(self):
        write(self.repo, "a.py", "import os\n\n" + TWENTY)
        self.assertEqual(rl.detect_acted_on(self.repo, "r2"), [])

    def test_block_must_match_whole_lines(self):
        # "line 5".."line 8" must not match inside "line 15".."line 18"
        write(self.repo, "a.py", "".join(f"line {i}\n" for i in range(10, 21)))
        self.assertEqual(len(rl.detect_acted_on(self.repo, "r2")), 1)

    def test_acted_on_when_file_deleted(self):
        (self.repo / "a.py").unlink()
        self.assertEqual(len(rl.detect_acted_on(self.repo, "r2")), 1)

    def test_acted_on_for_new_file_reviewed_before_commit(self):
        write(self.repo, "new.py", "a = 1\nb = 2\nc = 3\nd = 4\n")
        rl.append_records(self.repo, [
            finding_rec("r1", "f2", "new.py", [2, 3], rl.flagged_text(self.repo, "new.py", [2, 3]))])
        write(self.repo, "new.py", "a = 1\nd = 4\n")
        commit(self.repo, "simplify new.py")
        self.assertEqual([f["id"] for f in rl.detect_acted_on(self.repo, "r2")], ["f2"])

    def test_removing_one_of_two_copies_is_acted_on(self):
        block = "total = 0\nfor x in xs:\n    total += x\n"
        write(self.repo, "dup.py", block + "\n" + block)
        rl.append_records(self.repo, [{**finding_rec("r1", "f3", "dup.py", [5, 7],
                                                     rl.flagged_text(self.repo, "dup.py", [5, 7])),
                                       "text_count": 2}])
        self.assertEqual(rl.detect_acted_on(self.repo, "r2"), [])  # both copies still there
        write(self.repo, "dup.py", block)
        self.assertEqual([f["id"] for f in rl.detect_acted_on(self.repo, "r3")], ["f3"])

    def test_occurrences_counts_adjacent_copies(self):
        self.assertEqual(rl.occurrences("x = 1", ["x = 1", "x = 1", "y"]), 2)
        self.assertEqual(rl.occurrences("a\nb", ["a", "b", "a", "b"]), 2)

    def test_acted_on_reported_once(self):
        self.edit_line(6)
        rl.append_records(self.repo, [{"type": "acted_on", "run_id": "r1", "id": "f1",
                                       "detected_in": "r2"}])
        self.assertEqual(rl.detect_acted_on(self.repo, "r3"), [])

    def test_acted_on_cli_appends_and_prints_count(self):
        self.edit_line(6)
        code, out, _ = run_cli(self.repo, "acted-on", "--run-id", "r2")
        self.assertEqual((code, out.strip()), (0, "1"))
        self.assertEqual(rl.read_records(self.repo)[-1]["type"], "acted_on")


def merged_finding(fid, path, lines, **extra):
    return {"id": fid, "rule": "PY-02", "path": path, "lines": lines, "case": "c", "fix": "x",
            "lines_saved": 4, "removes": [], "preserves": "p", "source": "llm",
            "votes": 2, "lenses": ["reuse"], **extra}


class BuildRecordsTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        write(self.repo, "a.py", TWENTY)
        self.run_dir = self.repo / ".reviewer" / "run"
        files = {
            "scope.json": {"base": "b0", "base_kind": "merge_base", "head": "h1", "branch": "feat",
                           "changed_lines": 20, "files": [], "keep_markers": []},
            "tools.json": {"tools": {"vulture": "ran", "jscpd": "missing"},
                           "hints": [{}, {}], "lint": []},
            "context.json": {"symbols": [{}, {}, {}], "index": [], "dependencies": [],
                             "truncated": True},
            "intent.json": {"sources": ["commits"]},
            "merged.json": {"lenses": ["reuse", "abstraction"],
                            "findings": [merged_finding("f1", "a.py", [5, 8]),
                                         merged_finding("f2", "a.py", [10, 12]),
                                         merged_finding("f3", "a.py", [14, 16])],
                            "dropped": {"min_value": 2, "keep_marker": 1}},
            "verdicts.json": [{"id": "f1", "keep": True, "confidence": 0.9, "reason": "r1",
                               "coverage": "tested"},
                              {"id": "f2", "keep": False, "reason": "changes order"}],
            "ranked.json": {"shown": [{"id": "f1", "coverage": "tested"}],
                            "kept": [{"id": "f1"}], "dropped_by_verifier": 2},
        }
        for name, data in files.items():
            write(self.repo, f".reviewer/run/{name}", json.dumps(data))

    def test_run_record_from_run_files(self):
        run = rl.build_records(self.repo, self.run_dir, "r9")[0]
        self.assertEqual({k: run[k] for k in ("type", "run_id", "branch", "head", "base",
                                              "base_kind", "changed_lines", "finders", "lenses",
                                              "tools", "tool_hints", "context_pack", "intent",
                                              "dropped", "shown", "coverage")},
                         {"type": "run", "run_id": "r9", "branch": "feat", "head": "h1",
                          "base": "b0", "base_kind": "merge_base", "changed_lines": 20,
                          "finders": 2, "lenses": ["reuse", "abstraction"],
                          "tools": {"vulture": "ran", "jscpd": "missing"}, "tool_hints": 2,
                          "context_pack": {"symbols": 3, "truncated": True},
                          "intent": ["commits"],
                          "dropped": {"min_value": 2, "keep_marker": 1, "verifier": 2},
                          "shown": 1, "coverage": {"tested": 1, "untested": 0, "unknown": 0}})
        self.assertIn("ts", run)

    def test_finding_records_from_verdicts_and_ranking(self):
        records = rl.build_records(self.repo, self.run_dir, "r9")[1:]
        self.assertEqual([(r["id"], r["kept"], r["shown"], r["reason"], r["coverage"])
                          for r in records],
                         [("f1", True, True, "r1", "tested"),
                          ("f2", False, False, "changes order", None),
                          ("f3", False, False, "no verdict", None)])
        self.assertEqual(records[0]["text"], "line 5\nline 6\nline 7\nline 8")
        self.assertEqual(records[0]["votes"], 2)
        self.assertEqual(records[0]["text_count"], 1)

    def test_no_findings_means_no_ranking_files(self):
        (self.run_dir / "verdicts.json").unlink()
        (self.run_dir / "ranked.json").unlink()
        write(self.repo, ".reviewer/run/merged.json",
              json.dumps({"lenses": ["reuse", "abstraction"], "findings": [], "dropped": {}}))
        records = rl.build_records(self.repo, self.run_dir, "r9")
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0]["shown"], records[0]["dropped"]["verifier"]), (0, 0))

    def test_log_run_cli_appends_run_then_findings(self):
        code, _, _ = run_cli(self.repo, "log-run", "--run-id", "r9", "--run-dir", str(self.run_dir))
        self.assertEqual(code, 0)
        self.assertEqual([r["type"] for r in rl.read_records(self.repo)],
                         ["run", "finding", "finding", "finding"])


if __name__ == "__main__":
    unittest.main()
