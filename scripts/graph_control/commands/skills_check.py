"""skills-check: a dispatch's REQUIRED skills against the child's `skills_loaded:` line.

Stdlib only and reads nothing: the engine passes both lists. Exit 0 with PASS
when every required skill is proven loaded; exit 1 with
{"status": "SKILLS_MISSING", "missing": [...]} otherwise; exit 2 with
{"status": "BLOCKED", "reason": ...} when either list holds a malformed name, so
the engine can tell a skipped skill from a receipt it could not read.
"""

import json
from argparse import ArgumentParser, Namespace
from typing import Any

from . import Output

NAME = "skills-check"
HELP = ("compare a dispatch's REQUIRED skills with the child's skills_loaded line; "
        "exit 1 naming the missing, 2 on a malformed line")


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--required", required=True, help="comma-separated REQUIRED skills the dispatch named")
    parser.add_argument("--loaded", required=True,
                        help="the child's skills_loaded value, comma-separated; empty when the line is absent")


def _print(status: str, exit_code: int, **fields: Any) -> Output:
    return Output(json.dumps({"status": status, **fields}, sort_keys=True) + "\n", exit_code)


def run(args: Namespace) -> dict[str, Any] | Output:
    from ..common import Invalid
    from ..skills import missing, names

    try:
        required, loaded = names(args.required), names(args.loaded)
    except Invalid as error:
        return _print("BLOCKED", 2, reason=str(error))
    gone = missing(required, loaded)
    if gone:
        return _print("SKILLS_MISSING", 1, missing=gone)
    return {"required": len(required), "missing": []}
