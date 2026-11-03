import json
import unittest

import reviewer_log as rl
from tests.helpers import commit, make_repo, run_cli, write

TWENTY = "".join(f"line {i}\n" for i in range(1, 21))


def run_rec(run_id, branch, head="h", **extra):
    return {"type": "run", "run_id": run_id, "branch": branch, "head": head, **extra}


def finding_rec(run_id, fid, path, lines, shown=True):
    return {"type": "finding", "run_id": run_id, "id": fid, "rule": "PY-02",
            "path": path, "lines": lines, "shown": shown, "kept": shown}


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

    def test_log_run_cli_appends_run_then_findings(self):
        run_file = write(self.repo, "run.json", json.dumps(run_rec("r1", "main")))
        f_file = write(self.repo, "f.json", json.dumps([finding_rec("r1", "f1", "a.py", [1, 3])]))
        code, _, _ = run_cli(self.repo, "log-run", "--run", str(run_file), "--findings", str(f_file))
        self.assertEqual(code, 0)
        self.assertEqual([r["type"] for r in rl.read_records(self.repo)], ["run", "finding"])


class ActedOnTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        write(self.repo, "a.py", TWENTY)
        head = commit(self.repo, "add a.py")
        rl.append_records(self.repo, [run_rec("r1", "main", head),
                                      finding_rec("r1", "f1", "a.py", [5, 8])])

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


if __name__ == "__main__":
    unittest.main()
