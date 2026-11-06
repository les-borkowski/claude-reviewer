# Reviewer: design

Status: draft, not implemented. v1 plan:
[docs/superpowers/plans/2026-11-03-reviewer-v1.md](superpowers/plans/2026-11-03-reviewer-v1.md);
its data formats supersede the examples here.

## Goal

A Claude Code plugin that reviews local changes **before a PR is opened** and
finds code that can be smaller without changing behaviour. AI-written code
duplicates more and refactors less (see
[research](research-automated-code-review.md)); this is the layer that catches
it while it is still cheap to fix.

## Where it sits

| Tool | Runs on | Focus | Gap |
|---|---|---|---|
| Official `code-review` plugin | GitHub PR (`gh`) | bugs, CLAUDE.md compliance | filters out general quality issues, so never flags bloat |
| Built-in `/code-review` | diff / PR | bugs | not about size |
| Built-in `/simplify` | diff | reuse, simplification, efficiency | no explicit standards, applies fixes directly |
| `ponytail-review` | local diff | correct, safe, load, tests, speed, then lean | lean ranks last |
| `expediter:code-review` | since a ref | repo standards + spec | no simplification rules |
| **reviewer** | local diff, pre-PR | **simplification first**, against written rules | — |

Out of scope: bug hunting, security review, style. Other tools do those. The
"Never cut" list in `standards/common.md` makes sure our suggestions do not
create those problems.

## Principles (from the research)

1. **Precision over recall.** Developers reject over half of AI review
   comments; noise makes teams drop the tool. Show few findings, all verified.
2. **Every finding cites a rule ID** from `standards/`. No rule, no finding.
3. **Changed lines only.** At Google, 80% of raw predictions landed on
   unchanged code.
4. **Separate verification.** A second agent checks each finding before it is
   shown (ByteDance: precision 60% → 75%).
5. **Context, not just the diff.** Missing context caused 48% of false
   positives in SWR-Bench.
6. **Simplifications can break behaviour** (~15–30% of raw LLM refactorings
   do). Every suggested fix states what it preserves.
7. **Measure what gets acted on** and retire what doesn't land: rules,
   finders and the improvements below alike.

## Improvements

Each has an ID so the tracker (below) can report on it.

| ID | Improvement | Why (research) | Step | v1? |
|---|---|---|---|---|
| I1 | Static-tool candidates and lint skip-list | tools find dead code/duplication cheaper and more reliably; Google, ByteDance, ReviewBench pair LLMs with static analysis | 2 | yes |
| I2 | Shared context pack | missing context = 48% of FPs (SWR-Bench) | 2 | yes |
| I3 | Intent input (commits, branch, plan) | rejections for misaligned intent (CodeRabbit); deliberate deviations misjudged (SWR-Bench) | 2 | yes |
| I4 | Evaluation set | offline evals must track real use (ReviewBench); needed to tune anything | `eval/` | yes |
| I5 | Minimum-value threshold | "correct but low value" comments (Google) | 3b | yes |
| I6 | Keep markers and repo rule switches | silenced issues are not findings; subjective rules disabled per repo (Google) | 1, 3b | yes |
| I7 | Incremental review since last run | quality drops on large diffs | 1 | yes |
| I8 | Test-coverage label per finding | refactorings break behaviour; tests kept curl's PRs clean | 4 | yes |
| I9 | Prevention skill from the same standards | cheapest finding is the one never written | — | later |
| I10 | Rule-improvement suggestions from stats | ByteDance flywheel; Google rule suppression 54% → 80% useful | stats | later |
| I11 | Cross-family reviewer | self-preference bias; evidence anecdotal | 3 | later, only if I4 shows blind spots |

## Pipeline

```
/reviewer:review [ref] [--deep] [--all] [--full]
  1. Scope     changed files + line ranges since base; drop keep-marked lines   (I6, I7)
  2. Prepare   standards + repo docs; run repo tools; build context pack;
               collect intent                                                   (I1, I2, I3)
  3. Find      2–5 finder agents in parallel (sonnet), varied input
  3b. Merge    orchestrator, no agent: dedupe, votes, min-value filter, rule switches (I5, I6)
  4. Verify    one verifier agent (opus): keep/drop, coverage label             (I8)
  5. Rank+cap  top 5 by (lines saved × confidence × votes)
  6. Report    plain-English findings, rule IDs, verdict
  7. Log       append run + findings to .reviewer/log.jsonl                     (tracker)
```

### 1. Scope

- **Base (I7):** the commit of the last review run on this branch, from the
  log, if it is still an ancestor of HEAD. Otherwise the merge-base with the
  default branch. Uncommitted changes are always included. `[ref]` overrides;
  `--full` forces the merge-base.
- Diff over ~400 changed lines: say so in the report; recall drops sharply
  on large diffs. (v1 warns only; reviewing per file group is later.)
- Skip generated files, lockfiles, migrations, vendored code.
- **Keep markers (I6):** a line or block marked
  `reviewer: keep <RULE-ID> <reason>` (in the language's comment syntax) is
  excluded for that rule. A marker without a reason is ignored.

### 2. Prepare (orchestrator, no agent)

Done once and passed to every finder, so they work from the same facts and
their votes are comparable.

- **Standards:** `standards/common.md` + one file per language in the diff;
  repo docs (CLAUDE.md, CONTRIBUTING.md) win on conflict.
- **Repo rule switches (I6):** `.reviewer/config.json` may list disabled
  rule IDs: `{"disabled_rules": ["PY-04"]}`.
- **Static tools (I1):** v1 runs only tools already on `PATH` or declared by
  the repo; no `uvx`/`npx` downloads. Never add a dependency to the repo.
  Java adapters (PMD/CPD) are deferred to the first Java repo reviewed.

  | Need | Python | TypeScript | Java |
  |---|---|---|---|
  | dead code (CM-01) | `vulture` | `knip` | PMD unused rules |
  | duplication (CM-09) | `jscpd` | `jscpd` | PMD CPD |
  | lint skip-list | `ruff` | `eslint`, `tsc` | the build's checkstyle/PMD |

  Tool hits on changed lines become **hints** for the finders, not findings:
  they still need a rule and a verifier pass. Lint output becomes the
  skip-list for verifier check 5. A missing tool is skipped silently and
  recorded in the run log.
- **Context pack (I2):** for each changed function or component:
  - its callers and callees (LSP if available, else grep);
  - existing repo functions with similar names or signatures (for CM-04);
  - installed dependencies from the manifest (for CM-05).

  Capped at a size budget; what was cut is noted in the pack.
- **Intent (I3):** commit messages since base, branch name, and a plan or
  ticket file if one matches the branch (`docs/*-plan.md`,
  `.scratch/<slug>/issues/*`, the layout expediter writes). Finders use it
  for CM-02 (speculative flexibility) and to recognise deliberate choices.
  None found → noted in the report.

### 3. Find (agent `finder`, model: sonnet, 2–5 in parallel)

Several independent finders, because merging several review runs raised F1
by 23–44% in SWR-Bench, gains flattened after about 5, and 5 runs of a cheap
model beat 1 run of an expensive one. The gain is mostly recall, so the
verifier (step 4) is what keeps precision.

- **How many:** 2 finders for diffs under ~100 changed lines, 5 above that or
  with `--deep`.
- **Diversity:** identical prompts on one model give correlated results, and
  agent temperature cannot be set. Each finder gets the **full rule set**
  (so votes stay comparable) plus a different input:
  - files in a different order, and
  - a different focus lens: reuse/stdlib, unneeded abstraction, dead code
    and unused options, defensive noise and comments, language-specific rules.
- **All sonnet.** The Opus budget goes to the verifier.

Input: hunks, standards, context pack, intent, tool hints, the lens. Output
per candidate:

```json
{"rule": "PY-02", "file": "app/x.py", "lines": "40-52",
 "case": "the loop rebuilds Counter", "fix": "counts = Counter(words)",
 "lines_saved": 4, "removes": [], "preserves": "same dict contents and order",
 "source": "llm"}
```

`case` and `preserves` are mandatory; a candidate without them is dropped.
`removes` lists whole units the fix deletes (file, class, dependency, layer).
`source` is `llm` or `tool:<name>` when it came from a tool hint.

### 3b. Merge (orchestrator, no agent)

- **Dedupe:** same rule, same file, overlapping lines → one finding. Keep the
  clearest `case`/`fix` (most `lines_saved` that still states `preserves`);
  `votes` = number of finders that reported it.
- **Minimum value (I5):** drop findings with `lines_saved < 3` and an empty
  `removes`. Counted, not shown.
- **Rule switches (I6):** drop findings for rules disabled in
  `.reviewer/config`.

An agent here would add cost and could merge things that are not the same.

### 4. Verify (agent `verifier`, a different model from the finder: opus)

One verifier, not two: a second one would mostly agree, and a disagreement
would need a third to break it. The evidence is for having a separate
verification stage, not for doubling it.

Fresh context, one batch per file. Sees each merged candidate with its vote
count; a 1-vote finding needs the same bar as a 5-vote one, votes only
inform. For each candidate, checks:

1. The flagged lines are in the diff.
2. The rule's "Flag when" matches and no "Not a finding when" applies.
3. The fix touches nothing on the Never-cut list.
4. The fix keeps behaviour: same outputs, errors, side effects for the
   callers that exist. If unsure → drop, not "maybe".
5. Not on the lint skip-list from step 2.

Returns keep/drop + one-line reason, and for kept findings a **coverage
label (I8)**: `tested` (v1: a test file references the function or
component; real coverage data later), `untested`, or `unknown` (no tests in
the repo). The report shows the label next to the fix; `untested` fixes say
"check by hand".

### 5–6. Rank and report

- Rank by lines saved × verifier confidence × votes.
- Cap at 5 findings. `--all` shows everything that passed verification.
- Format borrowed from ponytail-review: numbered findings, each with
  **What / Problem / Fix / If we skip it**, plus rule ID, lines saved and
  coverage label.
- Ends with `Lean: -N lines possible.` and `Verdict: ship` or
  `Verdict: apply 1, 3 first`, plus one line on what was missing (no tools,
  no intent found, context pack truncated).
- Report only. Changes no code.

### 7. Log and tracker

`.reviewer/log.jsonl` in the reviewed repo (git-ignored). Two record types.

**Run record**, one per review — this is the tracker of how the
improvements are used:

```json
{"type": "run", "ts": "2026-11-03T10:00:00Z", "branch": "feat/x",
 "head": "<sha>", "base": "<sha>", "base_kind": "last_review|merge_base|ref",
 "changed_lines": 140, "finders": 5, "lenses": ["reuse", "abstraction", "..."],
 "tools": {"vulture": "ran", "jscpd": "missing"}, "tool_hints": 3,
 "context_pack": {"symbols": 12, "truncated": false},
 "intent": ["commits", "plan"],
 "dropped": {"min_value": 4, "rule_switch": 1, "keep_marker": 2, "verifier": 6},
 "shown": 5, "coverage": {"tested": 2, "untested": 2, "unknown": 1}}
```

**Finding record**, one per merged candidate: run id, rule, file, lines,
source, lens(es), votes, kept/dropped, reason, coverage label, and the
flagged lines' text. `log-run` builds both record types from the run files.

**Acted on:** at the start of each run, earlier shown findings whose flagged
text no longer appears (as whole lines) in their file are marked acted on
(ByteDance's "Outdated Rate"). Matching text, not line numbers, survives line
shifts and works for files that were new when reviewed.

**`/reviewer:stats`** (v1, read-only) prints, over the last N runs:

| Question | From |
|---|---|
| Acted-on rate per rule | finding records |
| Acted-on rate by source: tool hint vs LLM (I1) | `source` |
| Acted-on rate by vote count and lens; findings only extra finders found | `votes`, `lenses` |
| How often tools ran / were missing (I1) | `tools` |
| Context pack size and truncation rate (I2) | `context_pack` |
| Runs with intent found, by kind (I3) | `intent` |
| Findings dropped by min-value, rule switch, keep marker, verifier (I5, I6) | `dropped` |
| Share of runs reviewed incrementally; average changed lines (I7) | `base_kind`, `changed_lines` |
| Acted-on rate by coverage label (I8) | coverage |

Any improvement whose numbers show it never fires or never changes
acted-on rates is a candidate for deletion. That is the point of the tracker.

## Evaluation set (I4)

`eval/` in this repo, run by `/reviewer:eval` (or a script) before changing
finder count, models, rules or prompts.

- **Planted cases:** real diffs from your own repos (e.g. AI-written commits
  in simple-project-tool) with known bloat added, each labelled with the
  rule ID expected. Measures recall.
- **Clean cases:** diffs reviewed by a human and judged lean. Any finding is
  a false positive. Measures precision, the number that matters most.
- Start small: ~10 planted, ~10 clean, across the three languages.
- Output: precision, recall, findings per clean diff, cost per run. Stored
  per run so changes can be compared.

## Plugin layout

```
reviewer/
  .claude-plugin/plugin.json
  skills/review/SKILL.md     orchestrator: steps 1, 2, 3b, 5, 6, 7
  skills/stats/SKILL.md      tracker report
  agents/finder.md           step 3
  agents/verifier.md         step 4
  standards/                 README, common, python, java, typescript-react
  eval/                      planted/, clean/, results/
  docs/                      this file, research
```

Agents pin their model explicitly (the global default is haiku). One
`finder.md`; the lens is passed in the prompt, not five agent files.

## Distribution

Third plugin in the `les-borkowski` marketplace
(`~/dev/claude-plugins`, github `les-borkowski/claude-plugins`). That repo
only lists plugins; each lives in its own repo, so this one follows
expediter and warden:

- Repo: `~/dev/reviewer` → github `les-borkowski/claude-reviewer`.
- `plugin.json`: name `reviewer`, `version` starting `0.1.0`, `author`
  `Les Borkowski`, `keywords`, same shape as expediter's and warden's.
- Listing, added to `claude-plugins/.claude-plugin/marketplace.json` and its
  README table **once v1 installs and works** (an entry pointing at an empty
  repo would break `/plugin install`):

  ```json
  {
    "name": "reviewer",
    "source": { "source": "github", "repo": "les-borkowski/claude-reviewer" },
    "description": "Pre-PR simplification review: finds code that can be smaller without changing behaviour, against written per-language rules."
  }
  ```

  Then `claude plugin validate .` in claude-plugins.
- Install: `/plugin install reviewer@les-borkowski`.

## Relation to expediter

Different job, kept apart on purpose:

- **expediter** reviews during the build, per ticket: correctness, repo
  standards, match with the spec.
- **reviewer** runs once over the finished branch, before the PR, and asks
  only "can this be smaller without changing behaviour?" — with more depth
  on that one question.

Overlap risk: expediter's smell baseline (e.g. duplicated code) can flag the
same thing, and duplicate comments from several tools are a known reason
teams drop AI review. Rule: reviewer reports size findings only; expediter
leaves those to it. expediter's plan/ticket files are the intent source (I3).

## Cost

A run costs roughly one single-agent review per finder plus the Opus
verifier. Steps 2 and 3b are deterministic and cheap; the context pack
(I2) should make each finder cheaper, since none explores the repo alone.
Incremental review (I7) keeps repeat runs small.

## Later, not v1

- `--fix`: apply kept findings in a worktree, run the repo's tests, revert
  any that fail (RefactorAssist: test-checked refactorings 68% → 93% pass).
- **I9 Prevention skill:** a short rules skill generated from the same
  standards files, loaded while code is written (as ponytail does).
- **I10 Rule suggestions:** `/reviewer:stats` proposes rewriting or
  disabling rules with low acted-on rates; a human edits the rule.
- **I11 Cross-family reviewer:** an outside CLI as one finder, only if the
  evaluation set shows blind spots.
- A hook that offers the review before `gh pr create`.
- expediter `build-feature` calling the review as its final step.

## Open questions

1. ~~Distribution~~ — decided: own repo, listed in the les-borkowski
   marketplace (see Distribution).
2. Opus verifier cost per run: accept, or try sonnet first and compare on the
   eval set?
3. Should the log live in the repo (`.reviewer/`) or under `~/.config/reviewer/`?
4. Cap of 5: fixed, or per-repo setting?
5. Finder count thresholds (2 under ~100 lines, else 5): tune from the eval
   set and tracker.
6. Static tools via `uvx`/`npx` download on first use: v1 says no (only
   `PATH` or repo-declared tools). Revisit if the tracker shows tools rarely run.
7. Minimum value of 3 lines: right threshold? Tune on the eval set.
