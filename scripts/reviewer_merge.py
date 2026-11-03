"""Merge finder candidates (votes, filters) and rank verified findings."""
import json
import re
from pathlib import Path

REQUIRED = ("case", "preserves", "rule", "path", "lines", "lines_saved")
DROP_KEYS = ("missing_fields", "unknown_rule", "outside_diff", "min_value",
             "rule_switch", "keep_marker")
MIN_LINES_SAVED = 3
SHOW_CAP = 5
RULE_HEADING = re.compile(r"^###\s+([A-Z]{2}-\d{2})\b", re.M)


def rule_ids(standards_dir):
    return {m for p in Path(standards_dir).glob("*.md") for m in RULE_HEADING.findall(p.read_text())}


def _overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def _well_formed(c):
    if not isinstance(c, dict) or not all(c.get(k) not in (None, "") for k in REQUIRED):
        return False
    lines = c["lines"]
    return (isinstance(lines, list) and len(lines) == 2 and all(isinstance(n, int) for n in lines)
            and isinstance(c["lines_saved"], int))


def _load(path):
    """Candidates in a finder file, or the count to drop when the file is bad."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return [], 1
    if not isinstance(data, list):
        return [], max(1, len(data)) if isinstance(data, dict) else 1
    return data, 0


def _drop_reason(c, scope, rules, disabled):
    if not _well_formed(c):
        return "missing_fields"
    if c["rule"] not in rules:
        return "unknown_rule"
    ranges = next((f["ranges"] for f in scope["files"] if f["path"] == c["path"]), [])
    if not any(_overlaps(c["lines"], r) for r in ranges):
        return "outside_diff"
    if c["rule"] in disabled:
        return "rule_switch"
    start, end = c["lines"]
    for m in scope.get("keep_markers", []):
        if (m["path"], m["rule"]) == (c["path"], c["rule"]) and (
                start <= m["line"] <= end or start <= m["line"] + 1 <= end):
            return "keep_marker"
    return None


def merge(candidate_files, scope, rules, disabled):
    dropped = dict.fromkeys(DROP_KEYS, 0)
    groups = []  # [{"best": candidate, "members": [lines], "finders": set, "lenses": set}]
    for n, (lens, path) in enumerate(candidate_files):
        candidates, bad = _load(path)
        dropped["missing_fields"] += bad
        for c in candidates:
            reason = _drop_reason(c, scope, rules, disabled)
            if reason:
                dropped[reason] += 1
                continue
            group = next((g for g in groups if (g["best"]["rule"], g["best"]["path"]) ==
                          (c["rule"], c["path"]) and any(_overlaps(c["lines"], m) for m in g["members"])),
                         None)
            if group is None:
                group = {"best": c, "members": [], "finders": set(), "lenses": set()}
                groups.append(group)
            elif c["lines_saved"] > group["best"]["lines_saved"]:
                group["best"] = c
            group["members"].append(c["lines"])
            group["finders"].add(n)
            group["lenses"].add(lens)

    findings = []
    for g in groups:
        best = {"removes": [], "source": "llm", **g["best"]}
        if best["lines_saved"] < MIN_LINES_SAVED and not best["removes"]:
            dropped["min_value"] += 1
            continue
        findings.append({**best, "id": f"f{len(findings) + 1}", "votes": len(g["finders"]),
                         "lenses": sorted(g["lenses"])})
    return {"findings": findings, "dropped": dropped}


def rank(findings, verdicts, cap):
    by_id = {v.get("id"): v for v in verdicts if isinstance(v, dict)}
    kept = []
    for f in findings:
        v = by_id.get(f["id"])
        if v and v.get("keep") is True:
            confidence = float(v.get("confidence") or 0)
            kept.append({**f, "confidence": confidence, "reason": v.get("reason", ""),
                         "coverage": v.get("coverage", "unknown"),
                         "score": f["lines_saved"] * confidence * f["votes"]})
    kept.sort(key=lambda f: (-f["score"], int(f["id"][1:])))
    return {"shown": kept if cap is None else kept[:cap], "kept": kept,
            "dropped_by_verifier": len(findings) - len(kept)}
