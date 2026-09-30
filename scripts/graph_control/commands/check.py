"""check --reuse: the Stop hook's memoized test verdict for the current tree. Never executes anything.

The key is computed exactly as hooks/scripts/configured_check.py computes it:
the tree identity, test.argv and the SHA-256 of the graph-checks.json bytes.
Only test.argv is read here, not the full schema: the hook stores a verdict only
after validating those same bytes, so a config it rejected can never match.
"""

import hashlib
import json
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

NAME = "check"
HELP = "replay the memoized test verdict for the current tree (--reuse); never runs the suite"
CONFIG = ".claude/graph-checks.json"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("root", type=Path, help="Git worktree root holding .claude/graph-checks.json")
    parser.add_argument("--reuse", action="store_true", required=True,
                        help="read the tree-keyed memo; the only mode, since graph-control runs no project commands")


def run(args: Namespace) -> dict[str, Any]:
    from ..common import require
    from .. import memo

    require(not memo.disabled(), f"memo disabled ({memo.DISABLE} is set)")
    path = args.root / CONFIG
    require(path.is_file(), f"no {CONFIG} in {args.root}")
    raw = path.read_bytes()
    data = json.loads(raw)
    test = data.get("test") if isinstance(data, dict) else None
    require(isinstance(test, dict), f"{CONFIG} has no test block")
    argv = test.get("argv")
    require(isinstance(argv, list) and bool(argv) and all(isinstance(a, str) and a for a in argv),
            "test.argv must be a nonempty array of nonempty strings")
    hit = memo.lookup(args.root, memo.memo_key(args.root, argv, hashlib.sha256(raw).hexdigest()))
    require(hit is not None, "no memo for the current tree")
    return {"verdict": hit["status"], "observed_at": hit["observed_at"], "exit_code": hit["exit_code"]}
