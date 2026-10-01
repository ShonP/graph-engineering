"""digest: a markdown change digest (at most 60 lines) of the working tree against a base.

For the merge exhibit and the PR body. Read-only and git only: graph_control
executes no project tools. Reads the profile's `digest.exclude`, `risk:` and
`uxEvidence.path`; with `--plan`, groups a small diff by task.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path

from . import Output

NAME = "digest"
HELP = "markdown change digest against --base: stat by task when small, size, surfaces, hotspots, ux evidence"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path, help="the Git checkout to inspect")
    parser.add_argument("--base", required=True, help="revision the working tree is compared to")
    parser.add_argument("--plan", type=Path, help="the run's plan.json; groups a small diff by task")
    parser.add_argument("--profile", type=Path, help="the repo's .claude/graph-profile.yaml")


def run(args: Namespace) -> Output:
    from ..common import load
    from ..digest import digest  # imports wcmatch
    from ..preflight import read_profile  # imports PyYAML

    profile = {} if args.profile is None else read_profile(args.profile)
    return Output(digest(args.root, args.base, profile, None if args.plan is None else load(args.plan)))
