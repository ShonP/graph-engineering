"""waves: dispatch waves from a plan's topological levels, capped at --max-width.

A level wider than the cap splits into consecutive sub-waves in plan order.
Tasks in one level never have overlapping writable_paths, because plan
validation rejects unordered overlaps. An invalid plan is BLOCKED with the
validation message.
"""

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from typing import Any

NAME = "waves"
HELP = "topological task waves from plan.json, split to at most --max-width tasks each"
DEFAULT_WIDTH = 4  # the engine's concurrent-opus sub-cap


def positive(value: str) -> int:
    if not value.isdecimal() or int(value) < 1:
        raise ArgumentTypeError("expected a positive integer")
    return int(value)


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("plan", type=Path, help="the run's plan.json")
    parser.add_argument("--max-width", type=positive, default=DEFAULT_WIDTH,
                        help=f"most tasks per wave (default {DEFAULT_WIDTH})")


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load
    from ..plan import Plan

    width = args.max_width
    levels = Plan.parse(load(args.plan)).levels()
    return {"waves": [level[start:start + width] for level in levels for start in range(0, len(level), width)],
            "max_width": width}
