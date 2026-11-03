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


HANDLERS = {"log-run": cmd_log_run, "acted-on": cmd_acted_on}


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
