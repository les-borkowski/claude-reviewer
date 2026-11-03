# Code standards for the simplification reviewer

What the reviewer checks a change against. Goal: catch code that can be
smaller without losing behaviour. Not a style guide: anything a linter,
formatter, type checker or compiler already enforces is out of scope.

## Files

| File | Applies to |
|------|-----------|
| `common.md` | every language; always loaded |
| `python.md` | `*.py` |
| `java.md` | `*.java` |
| `typescript-react.md` | `*.ts`, `*.tsx` |

The reviewer loads `common.md` plus the file for each language in the diff.

## Precedence

1. The repo's own docs (`CLAUDE.md`, `CONTRIBUTING.md`, a style guide) win.
   If the repo endorses a pattern a rule here flags, the rule is silent.
2. `common.md` **Never cut** list wins over every simplification rule.
3. Language file, then `common.md`.

## Rule format

Every rule has the same shape, so findings can cite it (`PY-03`):

```markdown
### PY-03 Short name
**Flag when:** the concrete pattern in the diff.
**Not a finding when:** the cases where the pattern is right.
**Fix:** the smaller form.
(optional 2–4 line before/after)
```

"Not a finding when" is mandatory: it is what keeps false positives out.

## Writing a rule

- One pattern per rule. Rules that cover several topics produced
  unactionable comments at Google (see `docs/research-automated-code-review.md`).
- If a rule has many legitimate exceptions, it belongs in "Not a finding when"
  or it should not exist.
- Rules whose findings are rarely acted on get rewritten or deleted
  (see the feedback log in `docs/design.md`). Rule IDs are never reused.

## Adding a language

1. Copy `python.md` to `<language>.md`, pick a two-letter prefix (`GO-`, `RS-`).
2. Keep it to about 8–12 rules. Only patterns that make code bigger, not taste.
3. Skip anything the language's standard linter already flags.
4. Add a row to the table above with the file globs.
