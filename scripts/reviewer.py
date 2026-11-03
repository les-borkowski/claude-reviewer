#!/usr/bin/env python3
"""reviewer CLI: the deterministic steps of /reviewer:review and /reviewer:stats.

Each subcommand reads/writes JSON so the orchestrator skill can pass files
between agent steps. Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

import reviewer_log
import reviewer_merge
import reviewer_scope

SUBCOMMANDS = ["scope", "merge", "rank", "log-run", "acted-on",
               "tools", "context", "intent", "stats"]


def read_json(path):
    return json.loads(Path(path).read_text())


def print_json(data):
    print(json.dumps(data, indent=2))


def cmd_log_run(args):
    run = read_json(args.run)
    reviewer_log.append_records(args.repo, [run, *read_json(args.findings)])
    return 0


def cmd_acted_on(args):
    found = reviewer_log.detect_acted_on(args.repo, args.run_id)
    reviewer_log.append_records(args.repo, found)
    print(len(found))
    return 0


def cmd_scope(args):
    try:
        print_json(reviewer_scope.compute_scope(args.repo, args.ref, args.full))
    except reviewer_scope.NoBase as e:
        print(e, file=sys.stderr)
        return 2
    return 0


def cmd_merge(args):
    config = Path(args.repo) / ".reviewer" / "config.json"
    disabled = set(read_json(config).get("disabled_rules", [])) if config.exists() else set()
    pairs = [tuple(spec.split("=", 1)) for spec in args.finder]
    print_json(reviewer_merge.merge(pairs, read_json(args.scope),
                                    reviewer_merge.rule_ids(args.standards), disabled))
    return 0


def cmd_rank(args):
    merged = read_json(args.merged)
    print_json(reviewer_merge.rank(merged["findings"], read_json(args.verdicts),
                                   None if args.all else reviewer_merge.SHOW_CAP))
    return 0


HANDLERS = {"log-run": cmd_log_run, "acted-on": cmd_acted_on, "scope": cmd_scope,
            "merge": cmd_merge, "rank": cmd_rank}


def build_parser():
    parser = argparse.ArgumentParser(prog="reviewer.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    subs = {}
    for name in SUBCOMMANDS:
        subs[name] = sub.add_parser(name)
        subs[name].add_argument("--repo", type=Path, default=Path.cwd())
    subs["log-run"].add_argument("--run", required=True)
    subs["log-run"].add_argument("--findings", required=True)
    subs["acted-on"].add_argument("--run-id", required=True)
    subs["scope"].add_argument("--ref")
    subs["scope"].add_argument("--full", action="store_true")
    subs["merge"].add_argument("--scope", required=True)
    subs["merge"].add_argument("--standards", required=True)
    subs["merge"].add_argument("--finder", action="append", default=[], metavar="LENS=FILE")
    subs["rank"].add_argument("--merged", required=True)
    subs["rank"].add_argument("--verdicts", required=True)
    subs["rank"].add_argument("--all", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    handler = HANDLERS.get(args.cmd)
    if handler is None:
        print("not implemented", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
