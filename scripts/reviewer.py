#!/usr/bin/env python3
"""reviewer CLI: the deterministic steps of /reviewer:review and /reviewer:stats.

Each subcommand reads/writes JSON so the orchestrator skill can pass files
between agent steps. Standard library only.
"""
import argparse
import sys
from pathlib import Path

SUBCOMMANDS = ["scope", "merge", "rank", "log-run", "acted-on",
               "tools", "context", "intent", "stats"]


def build_parser():
    parser = argparse.ArgumentParser(prog="reviewer.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in SUBCOMMANDS:
        p = sub.add_parser(name)
        p.add_argument("--repo", type=Path, default=Path.cwd())
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    handler = HANDLERS.get(args.cmd)
    if handler is None:
        print("not implemented", file=sys.stderr)
        return 1
    return handler(args)


HANDLERS = {}

if __name__ == "__main__":
    sys.exit(main())
