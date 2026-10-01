"""status: live subagents, open decisions and token cost of the current Claude Code session.

The same view as `python3 -m graph_control.status`, which a status line should call
directly (stdlib only, no uv start). Reads transcripts; prints no prompt or response text.
"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from . import Output

NAME = "status"
HELP = "RUNNING / NEEDS YOU / COST for this session; --line for one status-line row"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--line", action="store_true", help="one status-line row; empty when nothing is live")
    parser.add_argument("--root", type=Path, help="project dir the session started in (default: the cwd)")
    parser.add_argument("--session", help="session id to read (default: the status-line stdin with --line, "
                        "else the newest session of --root)")


def run(args: Namespace) -> Output:
    from ..session import read_hint, session_id  # keeps discovery free of the status module's imports
    from ..status import render

    session = None if args.session is None else session_id(args.session)  # ValueError prints BLOCKED
    hint = read_hint(sys.stdin) if args.line and session is None else None
    return Output(render(args.line, args.root, session=session, hint=hint))
