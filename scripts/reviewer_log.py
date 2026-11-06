"""Append-only review log (.reviewer/log.jsonl) and acted-on detection."""
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)


def git(repo, *args, check=True):
    """Run git in `repo` and return stdout; raises CalledProcessError if check."""
    return subprocess.run(["git", *args], cwd=repo, check=check,
                          capture_output=True, text=True).stdout


def hunks(diff_text):
    """(old_start, old_count, new_start, new_count) per `@@` header of a --unified=0 diff."""
    return [(int(a), int(b or 1), int(c), int(d or 1))
            for a, b, c, d in HUNK.findall(diff_text)]


def log_path(repo):
    return Path(repo) / ".reviewer" / "log.jsonl"


def ensure_dir(repo):
    d = Path(repo) / ".reviewer"
    d.mkdir(exist_ok=True)
    ignore = d / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n")
    return d


def read_records(repo):
    path = log_path(repo)
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    return records


def append_records(repo, records):
    ensure_dir(repo)
    with log_path(repo).open("a") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def last_review(repo, branch):
    runs = [r for r in read_records(repo) if r.get("type") == "run" and r.get("branch") == branch]
    return runs[-1] if runs else None


def _normalised(text):
    return "\n".join(line.strip() for line in text.splitlines())


def flagged_text(repo, path, lines):
    """The flagged lines as they are now, whitespace-trimmed; None if the file is gone."""
    try:
        text = (Path(repo) / path).read_text(errors="replace")
    except OSError:
        return None
    start, end = lines
    return _normalised("\n".join(text.splitlines()[start - 1:end]))


def detect_acted_on(repo, current_run_id):
    """Shown findings whose flagged text no longer appears, as whole lines, in their file."""
    records = read_records(repo)
    done = {(r.get("run_id"), r.get("id")) for r in records if r.get("type") == "acted_on"}
    found = []
    for rec in records:
        key = (rec.get("run_id"), rec.get("id"))
        if rec.get("type") != "finding" or not rec.get("shown") or key in done \
                or not rec.get("text"):
            continue
        try:
            current = _normalised((Path(repo) / rec["path"]).read_text(errors="replace"))
        except OSError:
            current = None  # file deleted: the flagged code is gone
        if current is None or f"\n{rec['text']}\n" not in f"\n{current}\n":
            found.append({"type": "acted_on", "run_id": rec["run_id"], "id": rec["id"],
                          "detected_in": current_run_id})
            done.add(key)
    return found


def _read_run_file(run_dir, name, default):
    path = Path(run_dir) / name
    return json.loads(path.read_text()) if path.exists() else default


def build_records(repo, run_dir, run_id):
    """The run record and one finding record per merged finding, from the run files."""
    scope = _read_run_file(run_dir, "scope.json", {})
    tools = _read_run_file(run_dir, "tools.json", {})
    context = _read_run_file(run_dir, "context.json", {})
    intent = _read_run_file(run_dir, "intent.json", {})
    merged = _read_run_file(run_dir, "merged.json", {})
    # Steps 4–5 are skipped when merge leaves no findings, so these may not exist.
    verdicts = {v.get("id"): v for v in _read_run_file(run_dir, "verdicts.json", [])
                if isinstance(v, dict)}
    ranked = _read_run_file(run_dir, "ranked.json", {})
    shown = {f["id"]: f for f in ranked.get("shown", [])}
    coverage = {"tested": 0, "untested": 0, "unknown": 0,
                **Counter(f.get("coverage", "unknown") for f in shown.values())}
    lenses = merged.get("lenses", [])
    run = {"type": "run", "run_id": run_id,
           "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           **{k: scope.get(k) for k in ("branch", "head", "base", "base_kind", "changed_lines")},
           "finders": len(lenses), "lenses": lenses, "tools": tools.get("tools", {}),
           "tool_hints": len(tools.get("hints", [])),
           "context_pack": {"symbols": len(context.get("symbols", [])),
                            "truncated": bool(context.get("truncated"))},
           "intent": intent.get("sources", []),
           "dropped": {**merged.get("dropped", {}),
                       "verifier": ranked.get("dropped_by_verifier", 0)},
           "shown": len(shown), "coverage": coverage}
    findings = []
    for f in merged.get("findings", []):
        v = verdicts.get(f["id"], {})
        kept = v.get("keep") is True
        findings.append({"type": "finding", "run_id": run_id,
                         **{k: f.get(k) for k in ("id", "rule", "path", "lines", "source",
                                                  "lenses", "votes")},
                         "kept": kept, "shown": f["id"] in shown,
                         "reason": v.get("reason", "no verdict"),
                         "coverage": v.get("coverage") if kept else None,
                         "text": flagged_text(repo, f["path"], f["lines"])})
    return [run, *findings]
