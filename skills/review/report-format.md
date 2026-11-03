# Report format

The exact output of `/reviewer:review`. Plain English, no extra sections.

## First line

```
Reviewed <changed_lines> changed lines in <number of scope files> files since <base_kind> <first 7 chars of base>.
```

When `scope.json` has `large: true`, append to the same line:
` Large diff: findings may be missed; consider reviewing per area.`

## Nothing shown

If `ranked.json` `shown` is empty:

```
Looks lean. Ship.
Checked against <loaded standards files, e.g. common, python>; tools run: <tools with "ran", or "none">.
```

Then the `Dropped:` line and the last lines below.

## Findings

Otherwise, the shown findings in `ranked.json` order, numbered from 1:

```
1. **<short title>** (`<path>:L<start>-L<end>`, <RULE-ID>, -<lines_saved> lines, <coverage>)
   - **What this is:** <the code as it is now, from the finding's case>
   - **Problem:** <why it is bigger than it needs to be, in terms of the rule>
   - **Fix:** <the smaller form; say what it preserves>
   - **If we skip it:** <the cost of leaving it: what someone maintaining it pays>
```

When the coverage label is `untested`, write `untested — check by hand` in
its place.

After the findings, when `ranked.json` has more `kept` than `shown`:

```
<kept − shown> more kept findings not shown (use --all).
```

## Dropped line (always)

```
Dropped: <dropped_by_verifier> by verifier, <merged dropped.min_value> below minimum value, <dropped.keep_marker + dropped.rule_switch> by keep markers/rule switches.
```

## Last lines (always)

```
Lean: -<sum of lines_saved over shown findings> lines possible.
Verdict: ship.
Missing: <what was missing>.
```

- `Verdict: ship.` when no shown finding has confidence ≥ 0.7; otherwise
  `Verdict: apply <numbers of shown findings with confidence ≥ 0.7, e.g. 1, 3> first.`
- `Missing:` names any of: `no tools ran` (no tool in `tools.json` has
  `ran`), `no intent found` (`intent.json` `sources` is empty), `context pack
  truncated` (`context.json` `truncated`), joined by `, `. Omit the line when
  none apply.
