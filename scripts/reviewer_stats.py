"""/reviewer:stats: how findings and improvements are used, from the log."""
from collections import Counter, defaultdict

NO_RUNS = "No reviews logged yet."
NONE_YET = "none yet"


def _pct(part, whole):
    return f"{round(100 * part / whole)}%" if whole else "n/a"


def _table(header, rows):
    if not rows:
        return NONE_YET
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def _rate_rows(groups):
    """groups: {key: [acted flags]} → rows of key, shown, acted-on %."""
    return [(k, len(v), _pct(sum(v), len(v))) for k, v in groups.items()]


def stats(records, last=20):
    runs = [r for r in records if r.get("type") == "run"][-last:]
    if not runs:
        return NO_RUNS
    run_ids = {r["run_id"] for r in runs}
    acted = {(r.get("run_id"), r.get("id")) for r in records if r.get("type") == "acted_on"}
    findings = [r for r in records if r.get("type") == "finding" and r.get("run_id") in run_ids]
    shown = [(f, (f["run_id"], f["id"]) in acted) for f in findings if f.get("shown")]

    by_rule, by_source, by_votes, by_lens, by_cov = (defaultdict(list) for _ in range(5))
    for f, was_acted in shown:
        by_rule[f.get("rule")].append(was_acted)
        by_source[f.get("source", "llm")].append(was_acted)
        by_votes[f.get("votes", 1)].append(was_acted)
        by_cov[f.get("coverage", "unknown")].append(was_acted)
        for lens in f.get("lenses", []):
            by_lens[lens].append(was_acted)
    rules = [(k, len(v), sum(v), _pct(sum(v), len(v))) for k, v in sorted(by_rule.items())]
    single = sum(1 for f, was_acted in shown if was_acted and f.get("votes") == 1)
    votes_lenses = NONE_YET if not shown else "\n\n".join([
        _table(["Votes", "Shown", "Acted-on %"], _rate_rows(dict(sorted(by_votes.items())))),
        _table(["Lens", "Shown", "Acted-on %"], _rate_rows(dict(sorted(by_lens.items())))),
        f"Acted-on findings only one finder found: {single}"])

    n = len(runs)
    dropped = Counter()
    for r in runs:
        dropped.update(r.get("dropped", {}))
    tool_runs = sum(1 for r in runs if "ran" in r.get("tools", {}).values())
    packs = [r.get("context_pack", {}) for r in runs]
    intent_kinds = Counter(k for r in runs for k in r.get("intent", []))
    with_intent = sum(1 for r in runs if r.get("intent"))
    incremental = sum(1 for r in runs if r.get("base_kind") == "last_review")
    avg_lines = sum(r.get("changed_lines", 0) for r in runs) / n
    improvements = _table(["Improvement", "Usage"], [
        ("I1 static tools", f"{tool_runs} of {n} runs ran a tool; "
                            f"{sum(r.get('tool_hints', 0) for r in runs)} tool hints"),
        ("I2 context pack", f"avg {sum(p.get('symbols', 0) for p in packs) / n:.1f} symbols; "
                            f"truncated in {_pct(sum(1 for p in packs if p.get('truncated')), n)}"),
        ("I3 intent", f"{with_intent} of {n} runs; "
                      + (", ".join(f"{k} {v}" for k, v in sorted(intent_kinds.items())) or "none")),
        ("I5 min value", f"{dropped['min_value']} dropped"),
        ("I6 keep markers, rule switches",
         f"{dropped['keep_marker']} by keep markers, {dropped['rule_switch']} by rule switches"),
        ("I7 incremental", f"{_pct(incremental, n)} of runs since last review; "
                           f"avg {avg_lines:.0f} changed lines"),
        ("I8 coverage", ", ".join(f"{k} {_pct(sum(v), len(v))} acted on"
                                  for k, v in sorted(by_cov.items())) or "no findings shown"),
    ])

    kept = sum(1 for f in findings if f.get("kept"))
    verifier_rows = [(dropped["verifier"], kept, _pct(kept, kept + dropped["verifier"]))]
    verifier = _table(["Dropped", "Kept", "Kept %"], verifier_rows if findings else [])

    return "\n\n".join([
        f"# Reviewer stats (last {n} runs)",
        "## Rules\n" + _table(["Rule", "Shown", "Acted on", "Acted-on %"], rules),
        "## Sources\n" + _table(["Source", "Shown", "Acted-on %"], _rate_rows(dict(sorted(by_source.items())))),
        "## Votes and lenses\n" + votes_lenses,
        "## Improvements\n" + improvements,
        "## Verifier\n" + verifier,
    ])
