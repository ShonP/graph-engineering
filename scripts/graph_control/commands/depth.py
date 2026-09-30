"""depth: review depth (lint | single | panel) for the working tree against a base.

Reads the profile's `risk:`, `instructionPaths`, `review.panel_lines`,
`review.seams` and `stacks`, and runs only git. Untracked files are excluded.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

NAME = "depth"
HELP = "review depth for the diff against --base: lint, single or panel, with the reasons"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path, help="the Git checkout to inspect")
    parser.add_argument("--base", required=True, help="revision the working tree is compared to")
    parser.add_argument("--profile", required=True, type=Path, help="the repo's .claude/graph-profile.yaml")


def run(args: Namespace) -> dict[str, Any]:
    from ..depth import decide  # imports wcmatch
    from ..preflight import read_profile  # imports PyYAML

    return decide(args.root, args.base, read_profile(args.profile))
