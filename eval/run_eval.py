#!/usr/bin/env python3
"""Evaluation harness for /reviewer:review (design I4).

Per case: materialise the case into a temp git repo, run the review headless
with `claude -p`, read the shown findings from the repo's .reviewer/log.jsonl,
and score them against the case's expected findings.

    python3 eval/run_eval.py [--case ID ...] [--plugin-dir .]
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from reviewer_log import read_records  # noqa: E402

CASES_DIR = ROOT / "eval" / "cases"
RESULTS_DIR = ROOT / "eval" / "results"
TIMEOUT = 900
# Tools the review needs in a headless run; the repo is a throwaway temp dir.
ALLOWED_TOOLS = ["Bash", "Read", "Write", "Grep", "Glob", "Agent", "Task", "Skill"]


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def materialise(case_dir, dest):
    """Copy before/, commit it on main, apply change.patch uncommitted."""
    dest = Path(dest)
    shutil.copytree(Path(case_dir) / "before", dest)
    _git(dest, "init", "-q", "-b", "main")
    _git(dest, "add", "-A")
    _git(dest, "-c", "user.name=eval", "-c", "user.email=eval@example.com",
         "-c", "commit.gpgsign=false", "commit", "-q", "-m", "before")
    _git(dest, "apply", str((Path(case_dir) / "change.patch").resolve()))
    return dest


def _matches(expected, shown):
    return (expected["rule"], expected["path"]) == (shown["rule"], shown["path"]) and \
        expected["lines"][0] <= shown["lines"][1] and shown["lines"][0] <= expected["lines"][1]


def score(expected, shown):
    """Each expected finding matches at most one shown finding."""
    unmatched = list(expected)
    tp = fp = 0
    for s in shown:
        hit = next((e for e in unmatched if _matches(e, s)), None)
        if hit is None:
            fp += 1
        else:
            unmatched.remove(hit)
            tp += 1
    return {"tp": tp, "fp": fp, "fn": len(unmatched)}


def summarise(results):
    tp, fp, fn = (sum(r[k] for r in results) for k in ("tp", "fp", "fn"))
    clean = [r for r in results if r["kind"] == "clean"]
    return {"precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "fp_per_clean_case": sum(r["fp"] for r in clean) / len(clean) if clean else None,
            "cases": len(results)}


def shown_findings(repo):
    """Shown findings of the newest run in the repo's review log."""
    records = read_records(repo)
    runs = [r["run_id"] for r in records if r.get("type") == "run"]
    last = runs[-1] if runs else None
    return [r for r in records if r.get("type") == "finding" and r.get("shown")
            and (last is None or r.get("run_id") == last)]


def run_case(case_dir, plugin_dir):
    case = json.loads((case_dir / "case.json").read_text())
    with tempfile.TemporaryDirectory(prefix=f"reviewer-eval-{case['id']}-") as tmp:
        repo = materialise(case_dir, Path(tmp) / "repo")
        started = time.monotonic()
        cmd = ["claude", "-p", "/reviewer:review --all", "--plugin-dir", str(plugin_dir),
               "--output-format", "json", "--allowedTools", *ALLOWED_TOOLS]
        try:
            proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=TIMEOUT,
                                  stdin=subprocess.DEVNULL)
            error = None if proc.returncode == 0 else proc.stderr[-1000:]
            try:
                out = json.loads(proc.stdout)
            except ValueError:
                out = {}
        except subprocess.TimeoutExpired:
            out, error = {}, f"timed out after {TIMEOUT}s"
        shown = shown_findings(repo)
    return {"id": case["id"], "kind": case["kind"], "lang": case["lang"],
            **score(case["expected"], shown),
            "shown": [{k: f.get(k) for k in ("rule", "path", "lines")} for f in shown],
            "seconds": round(time.monotonic() - started), "cost_usd": out.get("total_cost_usd"),
            "report": out.get("result"), "error": error}


def _fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", action="append", help="case id (repeatable); default: all")
    parser.add_argument("--plugin-dir", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if shutil.which("claude") is None:
        print("claude CLI not found", file=sys.stderr)
        return 2
    cases = sorted(p for p in CASES_DIR.iterdir() if (p / "case.json").exists())
    if args.case:
        cases = [p for p in cases if p.name in args.case]
    results = []
    print("| case | kind | tp | fp | fn | seconds | cost $ |\n|---|---|---|---|---|---|---|")
    for case_dir in cases:
        r = run_case(case_dir, args.plugin_dir.resolve())
        results.append(r)
        print(f"| {r['id']} | {r['kind']} | {r['tp']} | {r['fp']} | {r['fn']} | {r['seconds']} "
              f"| {_fmt(r['cost_usd'])} |" + (f" error: {r['error'][:80]}" if r["error"] else ""))
    summary = summarise(results)
    print(f"\nprecision {_fmt(summary['precision'])}, recall {_fmt(summary['recall'])}, "
          f"false positives per clean case {_fmt(summary['fp_per_clean_case'])}, "
          f"{summary['cases']} cases")
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2) + "\n")
    print(f"results: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
