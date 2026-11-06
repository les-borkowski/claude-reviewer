# reviewer

A Claude Code plugin that reviews local changes **before a PR is opened** and
finds code that can be smaller without changing behaviour. AI-written code
duplicates more and refactors less; this is the layer that catches it while it
is still cheap to fix. Every finding cites a rule from [`standards/`](standards/README.md),
covers changed lines only, and is checked by a separate verifier before it is
shown. Report only: it never changes your code.

## Install

```
/plugin marketplace add les-borkowski/claude-plugins
/plugin install reviewer@les-borkowski
```

## Use

- `/reviewer:review [ref] [--deep] [--all] [--full]` — review the current branch.
- `/reviewer:stats` — how findings and improvements are used (acted-on rates).

## Local development

```
claude --plugin-dir .
```

Tests (Python ≥ 3.10, standard library only):

```
python3 -m unittest discover -s tests -v
```

## Docs

- [Design](docs/design.md)
- [Standards](standards/README.md)

## License

[MIT](LICENSE)
