import unittest

from reviewer_stats import stats
from tests.helpers import make_repo, run_cli
import reviewer_log as rl


def run(run_id, **extra):
    rec = {"type": "run", "run_id": run_id, "branch": "feat", "base_kind": "merge_base",
           "changed_lines": 100, "finders": 2, "tools": {"vulture": "missing"}, "tool_hints": 0,
           "context_pack": {"symbols": 4, "truncated": False}, "intent": [],
           "dropped": {"min_value": 1, "rule_switch": 0, "keep_marker": 2, "verifier": 3},
           "shown": 0, "coverage": {}}
    rec.update(extra)
    return rec


def finding(run_id, fid, rule="PY-02", shown=True, **extra):
    rec = {"type": "finding", "run_id": run_id, "id": fid, "rule": rule, "path": "a.py",
           "lines": [1, 5], "source": "llm", "lenses": ["reuse"], "votes": 1,
           "kept": shown, "shown": shown, "reason": "ok", "coverage": "tested"}
    rec.update(extra)
    return rec


def acted(run_id, fid):
    return {"type": "acted_on", "run_id": run_id, "id": fid, "detected_in": "later"}


def section(text, heading):
    return text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


class StatsTest(unittest.TestCase):
    def test_no_runs_message(self):
        self.assertEqual(stats([]), "No reviews logged yet.")
        self.assertEqual(stats([finding("r1", "f1")]), "No reviews logged yet.")

    def test_rule_acted_on_rate(self):
        recs = [run("r1")] + [finding("r1", f"f{i}") for i in range(1, 5)] + [acted("r1", "f2")]
        self.assertIn("| PY-02 | 4 | 1 | 25% |", section(stats(recs), "Rules"))

    def test_empty_sections_say_none_yet(self):
        out = stats([run("r1")])
        for heading in ("Rules", "Sources", "Votes and lenses", "Verifier"):
            self.assertEqual(section(out, heading).strip(), "none yet", heading)

    def test_sources_split_tool_vs_llm(self):
        recs = [run("r1"), finding("r1", "f1"), finding("r1", "f2"),
                finding("r1", "f3", source="tool:vulture"), acted("r1", "f3")]
        out = section(stats(recs), "Sources")
        self.assertIn("| llm | 2 | 0% |", out)
        self.assertIn("| tool:vulture | 1 | 100% |", out)

    def test_votes_and_single_finder_count(self):
        recs = [run("r1"), finding("r1", "f1", votes=1), finding("r1", "f2", votes=3),
                finding("r1", "f3", votes=1, lenses=["dead", "reuse"]),
                acted("r1", "f1"), acted("r1", "f2")]
        out = section(stats(recs), "Votes and lenses")
        self.assertIn("| 1 | 2 | 50% |", out)
        self.assertIn("| 3 | 1 | 100% |", out)
        self.assertIn("| reuse | 3 | 67% |", out)
        self.assertIn("| dead | 1 | 0% |", out)
        self.assertIn("Acted-on findings only one finder found: 1", out)

    def test_improvements_rows_present(self):
        recs = [run("r1", tools={"vulture": "ran"}, tool_hints=2, intent=["commits"],
                    base_kind="last_review"), run("r2"), finding("r1", "f1")]
        out = section(stats(recs), "Improvements")
        for imp in ("I1", "I2", "I3", "I5", "I6", "I7", "I8"):
            self.assertIn(f"| {imp} ", out)
        self.assertIn("1 of 2 runs", out)
        self.assertIn("50%", out)

    def test_verifier_section(self):
        recs = [run("r1"), finding("r1", "f1"), finding("r1", "f2", shown=False, kept=True),
                finding("r1", "f3", shown=False, kept=False)]
        self.assertIn("| 3 | 2 | 40% |", section(stats(recs), "Verifier"))

    def test_respects_last_n(self):
        recs = [run("r1"), finding("r1", "f1", rule="CM-01"), run("r2"), finding("r2", "f1"),
                run("r3"), finding("r3", "f1")]
        out = stats(recs, last=2)
        self.assertNotIn("CM-01", out)
        self.assertIn("| PY-02 | 2 |", out)

    def test_cli_stats(self):
        repo = make_repo()
        self.assertEqual(run_cli(repo, "stats")[:2], (0, "No reviews logged yet.\n"))
        rl.append_records(repo, [run("r1"), run("r2"), finding("r1", "f1", rule="CM-01")])
        code, out, _ = run_cli(repo, "stats", "--last", "1")
        self.assertEqual(code, 0)
        self.assertNotIn("CM-01", out)


if __name__ == "__main__":
    unittest.main()
