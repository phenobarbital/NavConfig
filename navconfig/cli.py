"""``kardex`` -- the NavConfig command line interface.

The CLI is organised in command groups (``env``, ``vault``, ``log``), each
of them exposing its own actions::

    kardex env create [--split]
    kardex env new <name>
    kardex vault create
    kardex vault migrate
    kardex vault save VARIABLE:VALUE
    kardex log enable [--logstash]

Importing this module must never build the global configuration: the whole
point of ``kardex env create`` is to run on a project that does not have an
``env/`` directory yet. That is why :mod:`navconfig` resolves ``config``
lazily and why nothing here imports it.
"""
from __future__ import annotations

import argparse
import sys

from .commands import COMMANDS, CommandError
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the ``kardex`` argument parser with every command group."""
    parser = argparse.ArgumentParser(
        prog="kardex",
        description="Utilities for bootstrapping and managing NavConfig projects.",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"kardex (navconfig) {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in COMMANDS:
        command.add_parser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``kardex`` CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "func", None)
    if handler is None:  # pragma: no cover - argparse enforces a subcommand
        parser.print_help()
        return 1

    try:
        return handler(args)
    except CommandError as err:
        sys.stderr.write(f"kardex: {err}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
