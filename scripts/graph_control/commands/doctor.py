"""doctor: read-only findings on a repo's graph-engineering setup and the executing plugin.

Backs /graph-doctor (all checks) and the SessionStart hook (--quick: only the
checks that start no process). Prints {"status": "PASS", "findings": [...]};
each finding has level (error, warn or info), id, message and fix.
"""

from argparse import ArgumentParser, Namespace
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..common import require

NAME = "doctor"
HELP = "read-only profile and plugin health findings as JSON; --quick runs the no-subprocess subset"
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path, help="repo root that holds .claude/graph-profile.yaml")
    parser.add_argument("--quick", action="store_true", help="only the checks that start no process")


def run(args: Namespace) -> dict[str, Any]:
    from ..doctor import diagnose  # imports PyYAML

    require(args.root.is_dir(), f"--root is not a directory: {args.root}")
    return {"findings": [asdict(finding) for finding in diagnose(args.root.resolve(), PLUGIN_ROOT, args.quick)]}
