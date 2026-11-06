# Evaluation set (I4)

Run before changing finder count, models, rules or prompts, and compare the
numbers with the previous run. Offline numbers only mean something if the
cases look like real use, so real cases from your own repos are worth more
than invented ones.

## Run

```bash
python3 eval/run_eval.py                         # every case
python3 eval/run_eval.py --case py-planted-counter
```

Needs the `claude` CLI on `PATH` (exits 2 with `claude CLI not found`
otherwise). Each case runs `claude -p "/reviewer:review --all" --plugin-dir
<this repo>` inside a throwaway git repo, so every run spends tokens (a few
finders plus an Opus verifier per case). Results go to
`eval/results/<UTC timestamp>.json` (git-ignored); the script prints a table
and:

- **precision** — shown findings that match an expected one. The number that
  matters most.
- **recall** — expected findings that were shown.
- **false positives per clean case** — any finding on a clean case is one.
- **cost** — `total_cost_usd` per case, as reported by `claude -p`.

A shown finding matches an expected one when the rule and path are the same
and the line ranges overlap. Each expected finding matches at most once.

## Case layout

```
eval/cases/<id>/
  case.json      {"id", "lang", "kind": "planted"|"clean", "expected": [{"rule", "path", "lines": [s, e]}]}
  before/        a tiny project tree, committed on main
  change.patch   a `git diff` applied on top and left uncommitted (the change under review)
```

- **planted**: a change with known bloat; `expected` names each rule id,
  path and line range (working-tree lines after the patch). Measures recall.
- **clean**: a change a human judged lean; `expected` is `[]`. Measures
  precision.

## Add a case

1. Copy an existing case directory and rename it; set `id` in `case.json`
   to the directory name.
2. Keep `before/` small (under ~60 lines): only what the change needs to make
   sense, callers and tests included.
3. Make the change in a scratch copy of `before/` and write the patch with
   git so it applies cleanly:

   ```bash
   git -C <scratch> add -A && git -C <scratch> diff --cached > eval/cases/<id>/change.patch
   ```

4. For planted cases, list every expected finding with the rule id from
   `standards/` and the line range after the patch. Make sure nothing else in
   the change is a legitimate finding, or it will count as a false positive.
5. Run `python3 -m unittest tests.test_eval -v`: it checks the patch applies
   and `case.json` is valid.

Real cases from your own repos (e.g. AI-written commits) are added the same
way: the parent commit's relevant files go in `before/`, the commit's diff in
`change.patch`.
