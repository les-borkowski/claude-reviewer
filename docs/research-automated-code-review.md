# Automated code review: state of the field (Nov 2026)

Research notes behind the reviewer's design. Weight: peer-reviewed papers and
industry deployments first; vendor blogs flagged as such.

## Where things stand

- **Adoption high, value mixed.** One survey cites ~91% of engineering orgs
  using AI review; its authors note adoption ≠ value.
- **Developers reject most comments.** CodeRabbit field study (31,073
  comments, 239 repos, Jul 2026): 36.4% accepted, 7.3% discussed, **56.3%
  rejected**. Main reasons: false positives, redundant/out-of-scope comments,
  suggestions misaligned with the team's intent and practices.
- **Benchmark precision is low.** SWR-Bench (1,000 real Python PRs): best tool
  ~17% precision / 23% recall / 19% F1; most under 10% precision. Recall fell
  from 38% (one issue per PR) to 9% (five or more).
- **GitHub ReviewBench (Oct 2026)** measures *addressed rate* (comments that
  led to a code change). Multi-model Copilot review: addressed rate +8%,
  recall +13.6%. Lesson: more comments ≠ better; severity beats volume.
- **Google AutoCommenter** (best-practice violations, linked to style-guide
  URLs):
  - Started at 54% developer-rated useful vs an 80% target.
  - Suppressing 17 non-actionable guideline URLs → 66% (devs) / 74% (raters);
    rewriting guideline summaries got it to 80%.
  - 80% of raw predictions were on unchanged lines → only comment on changed
    lines.
  - ~40% of comments resolved by a later code change.
  - Not-useful patterns: guidelines covering several topics, subjective
    rules with legitimate exceptions, systematic model errors, correct but
    low-value nits.
- **ByteDance BitsAI-CR** (12k+ weekly users, 219 rules in a taxonomy):
  - Two stages: RuleChecker finds, ReviewFilter verifies. Filter raised
    precision 60% → 75% (Go: 31% → 66%).
  - "Outdated Rate" (flagged lines later changed) as cheap acceptance signal;
    rules with low value are removed by the data flywheel.
  - Lesson: **precision over recall** for adoption; early noise makes users
    leave.

## Why AI-written code needs it

- **GitClear 2026** (vendor; 623M changed lines): block duplication +81% since
  2023, in-commit copy/paste +41%, moved/refactored code 21% (2022) → 3.8%
  (2026 YTD). AI attribution method not stated: correlation only.
- **Counterpoint** (arXiv 2603.27130): human code had *higher* duplication
  ratios; AI duplication smaller and more scattered. Evidence mixed.
- ~89% of 484k AI-introduced issues were code smells (arXiv 2603.28592, seen
  only in secondary coverage).
- **Open source overload:** curl ended its bug bounty (Jan 2026) over AI
  reports; tldraw auto-closes outside PRs; GitHub added PR restriction
  controls. curl saw far less slop in PRs, credited to strong test coverage.

## Main problems

1. **False positives.** SWR-Bench sample of 100: 48% missing context, 17%
   over-sensitive to modification, 16% vague/unactionable, 13% missing domain
   knowledge, 3% misjudged deliberate deviations.
2. **Correct but not worth fixing.** Google counts any comment not acted on
   as an "effective false positive" and aims for <10%.
3. **Noise** — volume, duplicate bots, conflicting advice → teams chase
   everything or ignore everything, then drop the tool.
4. **Large diffs** degrade quality sharply.
5. **Broad or subjective rules** produce unactionable comments.
6. **Self-review bias.** LLM judges favour their own output (NeurIPS 2024);
   GPT-4 was worst at repairing its own code. No controlled study of
   cross-model *code* review yet — anecdotes only.
7. **Behaviour-breaking simplifications.** LLM refactorings: ~32% failed unit
   tests out of the box (RefactorAssist); best small model still changed
   behaviour in 15%; CodeScene (vendor) 37% correct raw, 98% with
   fact-checking.
8. **Benchmarks disagree** on what a false positive is; vendor precision
   numbers are not comparable.

## Common fixes

| Fix | Evidence |
|---|---|
| Precision over recall; fewer, high-confidence findings | ByteDance, Google, official Claude plugin (score ≥ 80) |
| Separate verification pass per finding | ByteDance 60→75%; Qodo precise/exhaustive modes (vendor) |
| Several review passes merged | SWR-Bench: +23–44% F1; 5 cheap runs beat 1 expensive run |
| Explicit, narrow rules cited by ID | Google URLs, ByteDance taxonomy, Copilot/Claude instruction files |
| Comment only on changed lines | Google; Anthropic's false-positive list |
| Leave linter/type/compiler issues to tools | Google, Anthropic, most vendors |
| More context (callers, related files, conventions) | SWR-Bench top FP cause |
| Measure acted-on rate; retire rules that don't land | Google useful ratio, ByteDance Outdated Rate, GitHub addressed rate |
| Cap comments per change | Practitioner advice ~5 (vendor blogs) |
| Advisory, human decides | Copilot never blocks merges |
| Verify refactorings by running tests | All refactoring papers; RefactorAssist 68% → 93% with repair loop |

## Not verified

Diff-size F1 drop, the 89% smell share, Qodo and CodeScene numbers were seen
only in summaries. Many 2026 sources are vendor blogs; arXiv preprints are not
peer-reviewed.

## Sources

- [Is Agentic Code Review Helpful? (CodeRabbit, arXiv 2607.03316)](https://arxiv.org/abs/2607.03316)
- [SWR-Bench (arXiv 2509.01494)](https://arxiv.org/html/2509.01494v2)
- [GitHub ReviewBench](https://github.blog/ai-and-ml/github-copilot/reviewbench-an-open-benchmark-for-ai-code-review/)
- [Google AutoCommenter (arXiv 2405.13565)](https://arxiv.org/pdf/2405.13565)
- [BitsAI-CR (arXiv 2501.15134)](https://arxiv.org/pdf/2501.15134)
- [GitClear Maintainability Gap 2026](https://www.gitclear.com/the_ai_code_quality_maintainability_gap)
- [AI code in real repos (arXiv 2603.27130)](https://arxiv.org/html/2603.27130v2)
- [LLM Evaluators Favor Their Own Generations (NeurIPS 2024)](https://proceedings.neurips.cc/paper_files/paper/2024/file/7f1f0218e45f5414c79c0679633e47bc-Paper-Conference.pdf)
- [Secure code agents / self-repair (arXiv 2408.10495)](https://arxiv.org/pdf/2408.10495)
- [Do LLM Evaluators Prefer Themselves for a Reason?](https://arxiv.org/html/2504.03846v2)
- [RefactorAssist (arXiv 2608.00924)](https://arxiv.org/html/2608.00924)
- [Small open-weight models refactoring (MDPI)](https://www.mdpi.com/2674-113X/5/2/19)
- [LLMs in automated refactoring (arXiv 2411.04444)](https://arxiv.org/pdf/2411.04444)
- [CodeScene: Refactoring vs Refuctoring](https://codescene.com/hubfs/whitepapers/Refactoring%20vs%20Refuctoring%20Advancing%20the%20state%20of%20AI%20automated%20code%20improvements.pdf)
- [The Register: curl ends bug bounty](https://www.theregister.com/2026/01/21/curl_ends_bug_bounty/)
- [LeadDev: open source AI slop](https://leaddev.com/software-quality/open-source-has-a-big-ai-slop-problem)
- [AI review tools by false-positive rate (DEV)](https://dev.to/dev_barron/best-ai-code-review-tools-by-false-positive-rate-what-the-benchmarks-actually-show-2e8l)
- [Augment: AI code review accuracy](https://www.augmentcode.com/guides/ai-code-review-accuracy)
- [CodeAnt: AI review overload](https://codeant.ai/blogs/prevent-ai-code-review-overload)
- [Addy Osmani: Code Review in the Age of AI](https://addyo.substack.com/p/code-review-in-the-age-of-ai)
