"""host-check: host inspection before a wave (disk, load, bare repo, base freshness, docker).

Prints {"status": "PASS", "findings": [...]} and exits 0, or, when free disk
on the volume holding --root is below the floor, {"status": "BLOCKED",
"reason": ..., "findings": [...]} and exits 1. The floor is --min-free-gb when
given, else the profile's `host.min_free_gb`, else DEFAULT_FLOOR GB. Findings share doctor's shape
(level, id, message, fix). Host inspection, not project execution: it starts
only read-only git queries on local refs and, when the profile's runtime.up or
runtime.command names docker or compose, `docker info` with a 5 s timeout.
See graph_control/host.py.
"""

import json
from argparse import ArgumentParser, Namespace
from dataclasses import asdict
from pathlib import Path

from . import Output
from ..common import require

NAME = "host-check"
HELP = "host findings before a wave: free disk (BLOCKED below the floor), load, core.bare, base freshness, docker"
DEFAULT_FLOOR = 20


def gigabytes(value: str) -> int:
    number = int(value)
    if number < 0:
        raise ValueError(value)
    return number


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path, help="the checkout to inspect; its volume is the one measured")
    parser.add_argument("--min-free-gb", type=gigabytes,
                        help="free disk below this many GB (10^9 bytes) is BLOCKED; overrides the profile's "
                             f"host.min_free_gb (default {DEFAULT_FLOOR})")
    parser.add_argument("--profile", type=Path, help="the repo's .claude/graph-profile.yaml; its runtime decides the docker probe")


def floor(flag: int | None, profile: dict | None) -> int:
    """The free-disk floor in GB: the flag, else the profile's host.min_free_gb, else DEFAULT_FLOOR."""
    if flag is not None:
        return flag
    host = profile.get("host") if isinstance(profile, dict) else None
    value = host.get("min_free_gb", DEFAULT_FLOOR) if isinstance(host, dict) else DEFAULT_FLOOR
    require(type(value) is int and value >= 0, f"host.min_free_gb must be a non-negative integer, not {value!r}")
    return value


def run(args: Namespace) -> Output:
    from ..host import blocking, inspect  # imports PyYAML through doctor
    from ..preflight import read_profile

    require(args.root.is_dir(), f"--root is not a directory: {args.root}")
    profile = None if args.profile is None else read_profile(args.profile)
    findings = inspect(args.root.resolve(), floor(args.min_free_gb, profile), profile)
    blocker = blocking(findings)
    result = {"status": "PASS" if blocker is None else "BLOCKED", "findings": [asdict(finding) for finding in findings]}
    if blocker is not None:
        result["reason"] = blocker.message
    return Output(json.dumps(result, sort_keys=True) + "\n", 0 if blocker is None else 1)
