import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from reviewer_merge import rule_ids
from tests.helpers import ROOT, git

sys.path.insert(0, str(ROOT / "eval"))
import run_eval  # noqa: E402

CASES = sorted(p for p in (ROOT / "eval" / "cases").iterdir() if p.is_dir())


def f(rule, path, lines):
    return {"rule": rule, "path": path, "lines": lines}


class EvalTest(unittest.TestCase):
    def test_six_seed_cases(self):
        self.assertEqual(len(CASES), 6)

    def test_materialise_applies_patch(self):
        for case in CASES:
            with self.subTest(case.name), tempfile.TemporaryDirectory() as tmp:
                repo = run_eval.materialise(case, Path(tmp) / "repo")
                self.assertNotEqual(git(repo, "status", "--porcelain"), "")
                self.assertEqual(git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip(), "main")

    def test_case_json_valid(self):
        rules = rule_ids(ROOT / "standards")
        for case in CASES:
            with self.subTest(case.name):
                data = json.loads((case / "case.json").read_text())
                self.assertEqual(set(data), {"id", "lang", "kind", "expected"})
                self.assertEqual(data["id"], case.name)
                self.assertIn(data["lang"], {"python", "java", "typescript-react"})
                self.assertIn(data["kind"], {"planted", "clean"})
                if data["kind"] == "planted":
                    self.assertGreaterEqual(len(data["expected"]), 1)
                else:
                    self.assertEqual(data["expected"], [])
                for exp in data["expected"]:
                    self.assertIn(exp["rule"], rules)
                    self.assertEqual(set(exp), {"rule", "path", "lines"})

    def test_score_matches_overlapping_same_rule(self):
        out = run_eval.score([f("PY-02", "a.py", [8, 15])], [f("PY-02", "a.py", [10, 12])])
        self.assertEqual(out, {"tp": 1, "fp": 0, "fn": 0})

    def test_score_wrong_rule_is_fp_and_fn(self):
        out = run_eval.score([f("PY-02", "a.py", [8, 15])], [f("CM-04", "a.py", [8, 15])])
        self.assertEqual(out, {"tp": 0, "fp": 1, "fn": 1})

    def test_score_duplicate_match_is_fp(self):
        exp = [f("PY-02", "a.py", [8, 15])]
        out = run_eval.score(exp, [f("PY-02", "a.py", [8, 9]), f("PY-02", "a.py", [14, 15])])
        self.assertEqual(out, {"tp": 1, "fp": 1, "fn": 0})

    def test_summarise_clean_case_fp_rate(self):
        out = run_eval.summarise([{"id": "c", "kind": "clean", "tp": 0, "fp": 2, "fn": 0}])
        self.assertEqual(out["fp_per_clean_case"], 2.0)
        self.assertEqual(out["precision"], 0.0)
        self.assertIsNone(out["recall"])
        self.assertEqual((out["cases"], out["errored"]), (1, []))

    def test_summarise_precision_recall(self):
        out = run_eval.summarise([{"id": "p", "kind": "planted", "tp": 1, "fp": 1, "fn": 1},
                                  {"id": "q", "kind": "planted", "tp": 0, "fp": 0, "fn": 0}])
        self.assertEqual((out["precision"], out["recall"]), (0.5, 0.5))
        self.assertIsNone(out["fp_per_clean_case"])

    def test_summarise_leaves_out_errored_cases(self):
        out = run_eval.summarise([{"id": "c", "kind": "clean", "tp": 0, "fp": 0, "fn": 0,
                                   "error": "no review logged"},
                                  {"id": "p", "kind": "planted", "tp": 1, "fp": 1, "fn": 0}])
        self.assertEqual((out["cases"], out["errored"]), (1, ["c"]))
        self.assertEqual(out["precision"], 0.5)
        self.assertIsNone(out["fp_per_clean_case"])  # the only clean case errored

    def test_no_claude_exits_2(self):
        with tempfile.TemporaryDirectory() as empty, \
                mock.patch.dict(os.environ, {"PATH": empty}), \
                mock.patch("sys.stderr") as err:
            self.assertEqual(run_eval.main([]), 2)
        self.assertIn("claude CLI not found", "".join(c.args[0] for c in err.write.call_args_list))

    def test_shown_findings_from_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / ".reviewer" / "log.jsonl"
            log.parent.mkdir()
            log.write_text("\n".join(json.dumps(r) for r in [
                {"type": "run", "run_id": "r1"},
                {"type": "finding", "run_id": "r1", "id": "f1", "shown": True, **f("PY-02", "a.py", [1, 2])},
                {"type": "finding", "run_id": "r1", "id": "f2", "shown": False, **f("PY-04", "a.py", [3, 4])},
            ]) + "\n")
            self.assertEqual([x["id"] for x in run_eval.shown_findings(Path(tmp))], ["f1"])

    def test_shown_findings_none_without_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(run_eval.shown_findings(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
