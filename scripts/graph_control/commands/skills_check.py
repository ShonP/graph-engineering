"""skills-check: a dispatch's REQUIRED skills against the child's `skills_loaded:` line.

Stdlib only and reads nothing: the engine passes both lists. Exit 0 with PASS
when every required skill is proven loaded; exit 1 with
{"status": "SKILLS_MISSING", "missing": [...]} otherwise, the missing names as
the dispatch spelled them. A malformed name is BLOCKED.
"""

import json
from argparse import ArgumentParser, Namespace
from typing import Any

from . import Output

NAME = "skills-check"
HELP = "compare a dispatch's REQUIRED skills with the child's skills_loaded line; exit 1 naming the missing"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--required", required=True, help="comma-separated REQUIRED skills the dispatch named")
    parser.add_argument("--loaded", required=True,
                        help="the child's skills_loaded value, comma-separated; empty when the line is absent")


def run(args: Namespace) -> dict[str, Any] | Output:
    from ..skills import missing, names

    required = names(args.required)
    gone = missing(required, names(args.loaded))
    if gone:
        return Output(json.dumps({"status": "SKILLS_MISSING", "missing": gone}, sort_keys=True) + "\n", 1)
    return {"required": len(required), "missing": []}
