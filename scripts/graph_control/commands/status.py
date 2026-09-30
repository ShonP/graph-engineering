"""status: live subagents, open decisions and token cost of the current Claude Code session.

The same view as `python3 -m graph_control.status`, which a status line should call
directly (stdlib only, no uv start). Reads transcripts; prints no prompt or response text.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path

from . import Output

NAME = "status"
HELP = "RUNNING / NEEDS YOU / COST for this session; --line for one status-line row"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--line", action="store_true", help="one status-line row; empty when nothing is live")
    parser.add_argument("--root", type=Path, help="project dir the session started in (default: the cwd)")


def run(args: Namespace) -> Output:
    from ..status import render  # keeps discovery free of the status module's imports

    return Output(render(args.line, args.root))
