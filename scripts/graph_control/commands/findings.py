"""findings: validate findings.json / qa-findings.json and count or route their open findings.

`--counts` prints the open blocking, important and nit totals across every file;
without it, each file's verdict, open counts and open finding ids by route. A
missing or invalid file is BLOCKED (exit 1): an absent file is not zero findings.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

NAME = "findings"
HELP = "validate findings files; --counts sums open findings by severity"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("paths", nargs="+", type=Path, help="findings.json or qa-findings.json files")
    parser.add_argument("--counts", action="store_true", help="print open blocking/important/nit totals")


def run(args: Namespace) -> dict[str, Any]:
    from ..findings import counts, read_all

    if args.counts:
        return counts(args.paths)
    return {"files": [{"path": str(path), "verdict": findings.verdict, "open": findings.counts(),
                       "routes": findings.routes()} for path, findings in read_all(args.paths)]}
