"""Append-only review log (.reviewer/log.jsonl) and acted-on detection."""
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path



def git(repo, *args, check=True):
    """Run git in `repo` and return stdout; raises CalledProcessError if check."""
    return subprocess.run(["git", *args], cwd=repo, check=check,
                          capture_output=True, text=True).stdout


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


def _file_lines(repo, path):
    """The file's lines, whitespace-trimmed; None if the file is gone."""
    try:
        return [line.strip() for line in (Path(repo) / path).read_text(errors="replace").splitlines()]
    except OSError:
        return None


def flagged_text(repo, path, lines):
    """The flagged lines as they are now, whitespace-trimmed; None if the file is gone."""
    file_lines = _file_lines(repo, path)
    start, end = lines
    return None if file_lines is None else "\n".join(file_lines[start - 1:end])


def occurrences(text, file_lines):
    """How many times the block `text` appears as whole consecutive lines."""
    block = text.split("\n")
    k = len(block)
    return sum(file_lines[i:i + k] == block for i in range(len(file_lines) - k + 1))


def detect_acted_on(repo, current_run_id):
    """Shown findings with fewer copies of their flagged text than when they were logged."""
    records = read_records(repo)
    done = {(r.get("run_id"), r.get("id")) for r in records if r.get("type") == "acted_on"}
    found = []
    for rec in records:
        key = (rec.get("run_id"), rec.get("id"))
        if rec.get("type") != "finding" or not rec.get("shown") or key in done \
                or not rec.get("text"):
            continue
        file_lines = _file_lines(repo, rec["path"])  # None: file deleted, the code is gone
        if file_lines is None or occurrences(rec["text"], file_lines) < rec.get("text_count", 1):
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
        text = flagged_text(repo, f["path"], f["lines"])
        count = occurrences(text, _file_lines(repo, f["path"])) if text else 0
        findings.append({"type": "finding", "run_id": run_id,
                         **{k: f.get(k) for k in ("id", "rule", "path", "lines", "source",
                                                  "lenses", "votes")},
                         "kept": kept, "shown": f["id"] in shown,
                         "reason": v.get("reason", "no verdict"),
                         "coverage": v.get("coverage") if kept else None,
                         # several copies (e.g. a CM-09 duplicate): acted on once one goes
                         "text": text, "text_count": count})
    return [run, *findings]
