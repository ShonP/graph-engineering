"""findings: validate findings.json / qa-findings.json and count or route their open findings.

`--counts` prints the open blocking, important and nit totals across every file;
without it, each file's verdict, open counts and open finding ids by route. A
missing or invalid file is BLOCKED (exit 1): an absent file is not zero findings.
`--classes` with `--task` and `--round` appends one round file's open blocking and
important finding classes to classes.md, once each, after the file validates.
"""

import re
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

NAME = "findings"
HELP = "validate findings files; --counts sums open findings by severity"
TASK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("paths", nargs="+", type=Path, help="findings.json or qa-findings.json files")
    parser.add_argument("--counts", action="store_true", help="print open blocking/important/nit totals")
    parser.add_argument("--classes", type=Path, help="classes.md to append this round's finding classes to")
    parser.add_argument("--task", help="task id of the round for --classes, or qa")
    parser.add_argument("--round", type=int, help="round number for --classes, from 1")


def class_rows(args: Namespace) -> list[str]:
    from ..common import require
    from ..findings import class_lines, read

    require(len(args.paths) == 1, "--classes takes exactly one findings file")
    require(args.task is not None and TASK.fullmatch(args.task) is not None,
            "--classes needs --task <task id or qa>")
    require(args.round is not None and args.round >= 1, "--classes needs --round <n>, n >= 1")
    return class_lines(read(args.paths[0]), args.task, args.round)


def run(args: Namespace) -> dict[str, Any]:
    from ..common import require
    from ..findings import append_classes, counts, read_all

    require(args.classes is not None or (args.task is None and args.round is None),
            "--task and --round need --classes")
    rows = None if args.classes is None else class_rows(args)
    if args.counts:
        result = counts(args.paths)
    else:
        result = {"files": [{"path": str(path), "verdict": findings.verdict, "open": findings.counts(),
                             "routes": findings.routes()} for path, findings in read_all(args.paths)]}
    if rows is not None:
        result["classes_appended"] = append_classes(args.classes, rows)
    return result
