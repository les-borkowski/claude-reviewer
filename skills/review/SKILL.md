---
name: review
description: "Pre-PR simplification review of local changes: finds code that can be smaller without changing behaviour, checked against written per-language rules. Report only. Use for /reviewer:review, \"review before PR\", \"can this be simpler\"."
argument-hint: "[ref] [--deep] [--all] [--full]"
---

# /reviewer:review

Arguments: `$ARGUMENTS` — optional `[ref]` (base to diff against), `--deep`
(5 finders), `--all` (show every kept finding), `--full` (ignore the last
review; diff from the merge-base).

Review the current repo's local changes for code that can be smaller without
changing behaviour. Follow the steps in order; the step numbers match
`docs/design.md`.

**Rules for the whole run**

- Report only. Never apply fixes. Never edit or create files outside
  `.reviewer/` in the reviewed repo.
- Every deterministic step goes through the CLI. Below, `reviewer.py` means
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py"`, run from the repo
  root with `--repo .`. Run files live in `.reviewer/run/`.
- If a CLI command fails unexpectedly (non-zero exit other than the exit 2 in
  step 1, or output that is not JSON), show its error and stop. Do not review
  without it.

## 1. Scope

Generate `run_id` = the current UTC time as `YYYYMMDDTHHMMSSZ`. Then:

```bash
rm -rf .reviewer/run && mkdir -p .reviewer/run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" scope --repo . [--ref <ref>] [--full] > .reviewer/run/scope.json
```

- Exit code 2: show its stderr message (e.g. `no base found; pass a ref:
  /reviewer:review <ref>`) and stop.
- `files` is `[]`: print `Nothing to review.` and stop. Dispatch no agent.

Then mark earlier findings the developer has acted on:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" acted-on --repo . --run-id <run_id>
```

## 2. Prepare

Standards: `common.md` plus one file per `lang` present in `scope.json`
(`python` → `python.md`, `java` → `java.md`, `typescript-react` →
`typescript-react.md`):

```bash
cat "${CLAUDE_PLUGIN_ROOT}/standards/common.md" "${CLAUDE_PLUGIN_ROOT}/standards/<lang>.md" ... > .reviewer/run/standards.md
```

If the reviewed repo has `CLAUDE.md` or `CONTRIBUTING.md`, append each under
the heading `# Repo docs (these win over the rules above on conflict)`.

Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" tools --repo . --scope .reviewer/run/scope.json > .reviewer/run/tools.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" context --repo . --scope .reviewer/run/scope.json > .reviewer/run/context.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" intent --repo . --scope .reviewer/run/scope.json > .reviewer/run/intent.json
```

## 3. Find

- Finder count: 2 when `changed_lines < 100`, else 5. `--deep` forces 5.
- Lenses: with 2 finders, `reuse` and `abstraction`; with 5, in this order:
  `reuse`, `abstraction`, `dead`, `noise`, `language`.
- Finder *n* (1-based) reviews the scope's files rotated by *n − 1*
  positions (finder 2 starts at the second file, and so on).

Dispatch all finders **in one message, in parallel**, as `reviewer:finder`
agents. Each prompt gives: the run directory `.reviewer/run/` and its files
(`scope.json`, `standards.md`, `context.json`, `intent.json`, `tools.json`),
the `base` sha, its lens id, its file order, and its output path
`.reviewer/run/finder-<n>.json`.

## 3b. Merge

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" merge --repo . --scope .reviewer/run/scope.json --standards "${CLAUDE_PLUGIN_ROOT}/standards" --finder <lens1>=.reviewer/run/finder-1.json --finder <lens2>=.reviewer/run/finder-2.json ... > .reviewer/run/merged.json
```

Pass every finder's file, even one that was not written (merge counts it as
bad output and carries on). If `findings` is empty, skip step 4: use an empty
ranking (`shown` and `kept` empty, `dropped_by_verifier` 0) and go to step 6.

## 4. Verify

Dispatch one `reviewer:verifier` agent. Its prompt gives the run directory and
files (`merged.json`, `scope.json`, `standards.md`, `context.json`,
`intent.json`, `tools.json`) and the output path `.reviewer/run/verdicts.json`.
Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" rank --repo . --merged .reviewer/run/merged.json --verdicts .reviewer/run/verdicts.json [--all] > .reviewer/run/ranked.json
```

## 5–6. Rank and report

Write the report from `ranked.json`, `merged.json`, `scope.json`,
`tools.json`, `context.json` and `intent.json`, following
[report-format.md](report-format.md) exactly.

## 7. Log

The CLI builds the run and finding records from the run files; do not write
them yourself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" log-run --repo . --run-id <run_id> --run-dir .reviewer/run
```
