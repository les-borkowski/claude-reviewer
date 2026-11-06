import json
import pathlib
import tempfile
import unittest

from reviewer_merge import merge, rank, rule_ids
from tests.helpers import ROOT, make_repo, run_cli, write

RULES = {"PY-02", "PY-04", "CM-03", "CM-01"}
SCOPE = {"files": [{"path": "app/x.py", "lang": "python", "ranges": [[38, 60]]}],
         "keep_markers": [{"path": "app/x.py", "line": 39, "rule": "CM-03", "reason": "port"}]}


def cand(rule="PY-02", lines=(40, 52), saved=4, **extra):
    c = {"rule": rule, "path": "app/x.py", "lines": list(lines), "case": "loop rebuilds Counter",
         "fix": "Counter(words)", "lines_saved": saved, "removes": [],
         "preserves": "same dict", "source": "llm"}
    c.update(extra)
    return {k: v for k, v in c.items() if v is not None}


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def finder(self, n, content):
        path = self.dir / f"finder-{n}.json"
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        return path

    def run_merge(self, *files, disabled=()):
        pairs = [(lens, self.finder(i, c)) for i, (lens, c) in enumerate(files, 1)]
        return merge(pairs, SCOPE, RULES, set(disabled))

    def test_dedupe_counts_votes_and_lenses(self):
        out = self.run_merge(("reuse", [cand(lines=(40, 52), saved=4)]),
                             ("dead", [cand(lines=(45, 50), saved=6)]))
        self.assertEqual(len(out["findings"]), 1)
        f = out["findings"][0]
        self.assertEqual((f["id"], f["votes"], f["lenses"], f["lines_saved"], f["lines"]),
                         ("f1", 2, ["dead", "reuse"], 6, [45, 50]))
        self.assertEqual(out["lenses"], ["reuse", "dead"])  # one per finder, for the run log

    def test_same_finder_twice_is_one_vote(self):
        out = self.run_merge(("reuse", [cand(lines=(40, 52)), cand(lines=(41, 44))]))
        self.assertEqual(out["findings"][0]["votes"], 1)

    def test_same_lines_different_rule_not_merged(self):
        out = self.run_merge(("reuse", [cand()]), ("dead", [cand(rule="PY-04")]))
        self.assertEqual([f["id"] for f in out["findings"]], ["f1", "f2"])

    def test_drops_missing_fields(self):
        out = self.run_merge(("reuse", [cand(preserves=None), cand(case=""), cand()]))
        self.assertEqual(out["dropped"]["missing_fields"], 2)
        self.assertEqual(len(out["findings"]), 1)

    def test_unparsable_finder_file_counted_and_run_continues(self):
        out = self.run_merge(("reuse", "not json"), ("dead", [cand()]))
        self.assertEqual(len(out["findings"]), 1)
        self.assertEqual(out["dropped"]["missing_fields"], 1)

    def test_non_list_file_counts_once(self):
        out = self.run_merge(("reuse", {"candidates": [], "note": "x"}), ("dead", [cand(), "junk"]))
        self.assertEqual(out["dropped"]["missing_fields"], 2)  # 1 for the file, 1 for "junk"

    def test_drops_unknown_rule(self):
        out = self.run_merge(("reuse", [cand(rule="ZZ-99")]))
        self.assertEqual((out["findings"], out["dropped"]["unknown_rule"]), ([], 1))

    def test_drops_outside_diff(self):
        out = self.run_merge(("reuse", [cand(lines=(1, 10)), cand(path="other.py")]))
        self.assertEqual((out["findings"], out["dropped"]["outside_diff"]), ([], 2))

    def test_drops_disabled_rule(self):
        out = self.run_merge(("reuse", [cand()]), disabled={"PY-02"})
        self.assertEqual((out["findings"], out["dropped"]["rule_switch"]), ([], 1))

    def test_keep_marker_suppresses_line_and_next(self):
        out = self.run_merge(("reuse", [cand(rule="CM-03", lines=(40, 44)),
                                        cand(rule="CM-03", lines=(41, 44)),
                                        cand(rule="PY-02", lines=(40, 44))]))
        self.assertEqual(out["dropped"]["keep_marker"], 1)
        self.assertEqual([(f["rule"], f["lines"]) for f in out["findings"]],
                         [("CM-03", [41, 44]), ("PY-02", [40, 44])])

    def test_min_value(self):
        out = self.run_merge(("reuse", [cand(saved=2),
                                        cand(rule="PY-04", saved=2, removes=["class Foo"])]))
        self.assertEqual(out["dropped"]["min_value"], 1)
        self.assertEqual([f["rule"] for f in out["findings"]], ["PY-04"])

    def test_all_dropped_keys_present(self):
        self.assertEqual(set(self.run_merge(("reuse", []))["dropped"]),
                         {"missing_fields", "unknown_rule", "outside_diff", "min_value",
                          "rule_switch", "keep_marker"})


def finding(i, saved, votes=1):
    return {"id": f"f{i}", "rule": "PY-02", "path": "a.py", "lines": [i, i],
            "lines_saved": saved, "votes": votes}


class RankTest(unittest.TestCase):
    def test_rank_orders_by_score_and_caps(self):
        findings = [finding(i, saved=i) for i in range(1, 8)]
        findings[0]["votes"] = 10  # f1: 1 * 1.0 * 10 = 10, the highest score
        verdicts = [{"id": f"f{i}", "keep": True, "confidence": 1.0, "coverage": "tested"}
                    for i in range(1, 8)]
        out = rank(findings, verdicts, cap=5)
        self.assertEqual([f["id"] for f in out["shown"]], ["f1", "f7", "f6", "f5", "f4"])
        self.assertEqual(len(out["kept"]), 7)
        self.assertEqual(len(rank(findings, verdicts, cap=None)["shown"]), 7)

    def test_rank_ties_broken_by_numeric_id(self):
        findings = [finding(10, 4), finding(2, 4)]
        verdicts = [{"id": "f10", "keep": True, "confidence": 1}, {"id": "f2", "keep": True,
                                                                   "confidence": 1}]
        self.assertEqual([f["id"] for f in rank(findings, verdicts, 5)["shown"]], ["f2", "f10"])

    def test_rank_unreadable_confidence_scores_zero(self):
        findings = [finding(1, 4), finding(2, 4)]
        verdicts = [{"id": "f1", "keep": True, "confidence": "high"},
                    {"id": "f2", "keep": True, "confidence": 0.5}]
        out = rank(findings, verdicts, 5)
        self.assertEqual([(f["id"], f["confidence"]) for f in out["shown"]],
                         [("f2", 0.5), ("f1", 0.0)])

    def test_verifier_can_correct_the_rule(self):
        findings = [finding(1, 4), finding(2, 4)]
        verdicts = [{"id": "f1", "keep": True, "confidence": 1, "rule": "RE-05"},
                    {"id": "f2", "keep": True, "confidence": 1, "rule": "XX-99"}]
        out = rank(findings, verdicts, 5, rules={"RE-05", "PY-02"})
        self.assertEqual({f["id"]: f["rule"] for f in out["kept"]},
                         {"f1": "RE-05", "f2": findings[1]["rule"]})  # unknown id: keep the old

    def test_rank_missing_verdict_is_dropped(self):
        findings = [finding(1, 4), finding(2, 4), finding(3, 4)]
        verdicts = [{"id": "f1", "keep": True, "confidence": 0.9},
                    {"id": "f2", "keep": False, "reason": "changes order"}]
        out = rank(findings, verdicts, cap=5)
        self.assertEqual([f["id"] for f in out["kept"]], ["f1"])
        self.assertEqual(out["dropped_by_verifier"], 2)
        self.assertEqual(out["kept"][0]["confidence"], 0.9)


class RuleIdsAndCliTest(unittest.TestCase):
    def test_rule_ids_from_standards(self):
        ids = rule_ids(ROOT / "standards")
        self.assertTrue({"CM-01", "PY-02", "JV-01", "RE-01", "TS-01"} <= ids)
        self.assertNotIn("PY-03 Manual", ids)

    def test_cli_merge_reads_config_then_rank(self):
        repo = make_repo()
        write(repo, ".reviewer/config.json", json.dumps({"disabled_rules": ["PY-04"]}))
        scope = write(repo, "scope.json", json.dumps(SCOPE))
        f1 = write(repo, "f1.json", json.dumps([cand(), cand(rule="PY-04")]))
        code, out, _ = run_cli(repo, "merge", "--scope", str(scope), "--standards",
                               str(ROOT / "standards"), "--finder", f"reuse={f1}")
        self.assertEqual(code, 0)
        merged = json.loads(out)
        self.assertEqual((len(merged["findings"]), merged["dropped"]["rule_switch"]), (1, 1))
        merged_file = write(repo, "merged.json", out)
        verdicts = write(repo, "v.json", json.dumps([{"id": "f1", "keep": True, "confidence": 1}]))
        code, out, _ = run_cli(repo, "rank", "--merged", str(merged_file), "--verdicts", str(verdicts),
                               "--standards", str(ROOT / "standards"))
        self.assertEqual((code, len(json.loads(out)["shown"])), (0, 1))


if __name__ == "__main__":
    unittest.main()
