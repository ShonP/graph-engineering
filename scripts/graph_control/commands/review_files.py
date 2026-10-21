from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

NAME = "review-files"
HELP = "the review findings files merge gate (b) and the retro fast path read, by review.cadence"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("run", type=Path, help="the run directory, .graph/<run>")
    parser.add_argument("--profile", required=True, type=Path, help="the repo's .claude/graph-profile.yaml")
    parser.add_argument("--plan", type=Path, help="the run's plan.json; default <run>/plan.json")


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load
    from ..preflight import read_profile
    from ..review_files import review_files

    plan = load(args.plan or args.run / "plan.json")
    return review_files(args.run, read_profile(args.profile), plan)
