"""Append-only review log (.reviewer/log.jsonl) and acted-on detection."""
import json
import re
import subprocess
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


def _old_side_touches(diff_text, start, end):
    for old_start, old_count, _, _ in hunks(diff_text):
        if old_count == 0:  # pure insertion after old_start
            if start <= old_start < end:
                return True
        elif old_start <= end and start <= old_start + old_count - 1:
            return True
    return False


def detect_acted_on(repo, current_run_id):
    # shortcut: finding lines are working-tree lines at review time but are compared
    # with that run's head; off by the shift when the review covered uncommitted edits.
    records = read_records(repo)
    heads = {r["run_id"]: r.get("head") for r in records if r.get("type") == "run"}
    done = {(r.get("run_id"), r.get("id")) for r in records if r.get("type") == "acted_on"}
    found = []
    for rec in records:
        key = (rec.get("run_id"), rec.get("id"))
        if rec.get("type") != "finding" or not rec.get("shown") or key in done:
            continue
        head = heads.get(rec["run_id"])
        try:
            diff = git(repo, "diff", "--unified=0", head, "--", rec["path"])
        except (subprocess.CalledProcessError, TypeError, KeyError):
            continue  # head gone (rebased away) or malformed record
        start, end = rec["lines"]
        if _old_side_touches(diff, start, end):
            found.append({"type": "acted_on", "run_id": rec["run_id"], "id": rec["id"],
                          "detected_in": current_run_id})
            done.add(key)
    return found
