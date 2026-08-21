"""Sub-commands of the ``kardex`` command line interface.

Every module here exposes an ``add_parser(subparsers)`` function that
registers its command group and wires each action to a handler through
``set_defaults(func=...)``.
"""
from . import env, log, vault
from .common import CommandError

#: Command groups registered by :func:`navconfig.cli.build_parser`, in the
#: order they should appear in ``kardex --help``.
COMMANDS = (env, vault, log)

__all__ = ("COMMANDS", "CommandError", "env", "log", "vault")
