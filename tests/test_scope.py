import os
import unittest

import reviewer_log as rl
from reviewer_scope import compute_scope
from tests.helpers import commit, git, make_repo, run_cli, write

FIVE = "".join(f"x{i} = {i}\n" for i in range(1, 6))


class ScopeTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        write(self.repo, "a.py", "a = 1\nb = 2\n")
        commit(self.repo, "add a.py")
        git(self.repo, "checkout", "-q", "-b", "feat")

    def scope(self, ref=None, full=False):
        return compute_scope(self.repo, ref, full)

    def files(self, scope):
        return {f["path"]: f for f in scope["files"]}

    def test_branch_vs_merge_base(self):
        write(self.repo, "a.py", "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n")
        commit(self.repo, "more")
        s = self.scope()
        self.assertEqual(s["base_kind"], "merge_base")
        self.assertEqual(s["branch"], "feat")
        self.assertEqual(s["files"], [{"path": "a.py", "lang": "python", "ranges": [[3, 5]]}])
        self.assertEqual(s["changed_lines"], 3)
        self.assertFalse(s["large"])

    def test_user_diff_prefix_config_ignored(self):
        git(self.repo, "config", "diff.noprefix", "true")
        write(self.repo, "a.py", "a = 1\nb = 2\nc = 3\n")
        self.assertEqual(list(self.files(self.scope())), ["a.py"])

    def test_uncommitted_and_untracked_included(self):
        write(self.repo, "a.py", "a = 1\nb = 3\n")
        write(self.repo, "b.ts", "export const x = 1;\nexport const y = 2;\n")
        files = self.files(self.scope())
        self.assertEqual(files["a.py"]["ranges"], [[2, 2]])
        self.assertEqual(files["b.ts"]["lang"], "typescript-react")
        self.assertEqual(files["b.ts"]["ranges"], [[1, 2]])

    def test_nothing_to_review(self):
        s = self.scope()
        self.assertEqual((s["files"], s["changed_lines"]), ([], 0))

    def test_skips_lockfiles_deleted_binary(self):
        write(self.repo, "old.py", "x = 1\n")
        commit(self.repo, "old")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "feat")
        git(self.repo, "checkout", "-q", "feat")
        os.remove(self.repo / "old.py")
        write(self.repo, "uv.lock", "lock\n")
        (self.repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00binary")
        s = self.scope()
        self.assertEqual(s["files"], [])
        self.assertTrue({"uv.lock", "old.py", "logo.png"} <= set(s["skipped"]))

    def test_committed_binary_skipped(self):
        (self.repo / "data.py").write_bytes(b"x = 1\n\x00\x01\x02")
        write(self.repo, "Main.java", "class Main {}\n")
        commit(self.repo, "binary and java")
        s = self.scope()
        self.assertEqual([f["path"] for f in s["files"]], ["Main.java"])
        self.assertIn("data.py", s["skipped"])

    def test_skips_generated_dirs_and_unsupported(self):
        write(self.repo, "app/migrations/0001.py", "x = 1\n")
        write(self.repo, "notes.md", "hi\n")
        write(self.repo, "types.d.ts", "declare const x: number;\n")
        s = self.scope()
        self.assertEqual(s["files"], [])
        self.assertEqual(set(s["skipped"]), {"app/migrations/0001.py", "notes.md", "types.d.ts"})

    def test_rename_uses_new_path(self):
        write(self.repo, "a.py", "".join(f"v{i} = {i}\n" for i in range(20)))
        commit(self.repo, "grow a")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "feat")
        git(self.repo, "checkout", "-q", "feat")
        git(self.repo, "mv", "a.py", "b.py")
        text = (self.repo / "b.py").read_text().replace("v3 = 3", "v3 = 33")
        write(self.repo, "b.py", text)
        files = self.files(self.scope())
        self.assertEqual(list(files), ["b.py"])
        self.assertEqual(files["b.py"]["ranges"], [[4, 4]])

    def test_incremental_base_from_last_review(self):
        write(self.repo, "a.py", "a = 1\nb = 2\nc = 3\n")
        first = commit(self.repo, "first")
        rl.append_records(self.repo, [{"type": "run", "run_id": "r1", "branch": "feat",
                                       "head": first}])
        write(self.repo, "a.py", "a = 1\nb = 2\nc = 3\nd = 4\n")
        commit(self.repo, "second")
        s = self.scope()
        self.assertEqual(s["base_kind"], "last_review")
        self.assertEqual(s["base"], first)
        self.assertEqual(s["files"][0]["ranges"], [[4, 4]])
        full = self.scope(full=True)
        self.assertEqual(full["base_kind"], "merge_base")
        self.assertEqual(full["files"][0]["ranges"], [[3, 4]])

    def test_last_review_not_ancestor_falls_back(self):
        write(self.repo, "a.py", "a = 1\nb = 2\nc = 3\n")
        first = commit(self.repo, "first")
        rl.append_records(self.repo, [{"type": "run", "run_id": "r1", "branch": "feat",
                                       "head": first}])
        git(self.repo, "reset", "-q", "--hard", "HEAD~1")
        write(self.repo, "a.py", "a = 1\nb = 2\nz = 9\n")
        commit(self.repo, "other")
        self.assertEqual(self.scope()["base_kind"], "merge_base")

    def test_ref_overrides(self):
        write(self.repo, "a.py", "a = 1\nb = 2\nc = 3\n")
        commit(self.repo, "c")
        s = self.scope(ref="HEAD")
        self.assertEqual((s["base_kind"], s["files"]), ("ref", []))

    def test_on_default_branch_reviews_uncommitted_only(self):
        git(self.repo, "checkout", "-q", "main")
        write(self.repo, "a.py", "a = 1\nb = 2\nc = 3\n")
        s = self.scope()
        self.assertEqual(s["base"], git(self.repo, "rev-parse", "HEAD").strip())
        self.assertEqual(s["files"][0]["ranges"], [[3, 3]])

    def test_no_base_found(self):
        repo = make_repo(branch="trunk")
        git(repo, "checkout", "-q", "-b", "feat")
        code, _, err = run_cli(repo, "scope")
        self.assertEqual(code, 2)
        self.assertIn("no base found; pass a ref: /reviewer:review <ref>", err)

    def test_keep_marker_parsed(self):
        body = "".join(f"x{i} = {i}\n" for i in range(1, 9))
        write(self.repo, "k.py", body + "# reviewer: keep CM-03 port to billing API\n"
              "# reviewer: keep CM-03\n")
        s = self.scope()
        self.assertEqual(s["keep_markers"], [{"path": "k.py", "line": 9, "rule": "CM-03",
                                              "reason": "port to billing API"}])

    def test_keep_marker_strips_block_comment_close(self):
        write(self.repo, "k.ts", "/* reviewer: keep RE-03 hot path */\n/* reviewer: keep RE-03 */\n")
        self.assertEqual([m["reason"] for m in self.scope()["keep_markers"]], ["hot path"])

    def test_large_flag(self):
        write(self.repo, "big.py", "".join(f"v{i} = {i}\n" for i in range(401)))
        s = self.scope()
        self.assertEqual(s["changed_lines"], 401)
        self.assertTrue(s["large"])

    def test_cli_prints_scope_json(self):
        write(self.repo, "a.py", "a = 1\nb = 3\n")
        code, out, _ = run_cli(self.repo, "scope")
        self.assertEqual(code, 0)
        self.assertIn('"base_kind": "merge_base"', out)


if __name__ == "__main__":
    unittest.main()
