"""worktree-ready: check a task worktree after the engine ran the profile's `bootstrap` commands.

Reads the profile's `bootstrap` and `bootstrap_ready`, the bootstrap exit status and log, and runs only
`git rev-parse`. It never executes a `bootstrap` command; a failure is a `NEEDS_SETUP:` BLOCKED reason.
"""

import subprocess
from argparse import ArgumentParser, Namespace
from pathlib import Path, PurePosixPath
from typing import Any

NAME = "worktree-ready"
HELP = "check a task worktree after bootstrap: exit status, log tail and the bootstrap_ready paths"
LOG_TAIL_LINES = 20


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("worktree", type=Path, help="the task worktree the engine bootstrapped")
    parser.add_argument("--profile", required=True, type=Path, help="the repo's .claude/graph-profile.yaml")
    parser.add_argument("--bootstrap-exit", type=int, help="exit status of the engine's bootstrap run")
    parser.add_argument("--bootstrap-log", type=Path, help="the bootstrap output log")


def _needs_setup(message: str):
    from ..common import Invalid

    return Invalid(f"NEEDS_SETUP: {message}")


def _git_path(worktree: Path, option: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(worktree), "rev-parse", "--path-format=absolute", option],
                              capture_output=True, text=True, timeout=30)
    except OSError as error:
        raise _needs_setup(str(error)) from error
    if done.returncode != 0:
        raise _needs_setup(done.stderr.strip() or f"{worktree} is not a git worktree")
    return done.stdout.strip()


def _log_tail(log: Path | None) -> str:
    try:
        lines = [] if log is None else log.read_text(errors="replace").splitlines()
    except OSError:
        lines = []
    return "; last 20 lines:\n" + "\n".join(lines[-LOG_TAIL_LINES:]) if lines else "; no log"


def _strings(profile: dict[str, Any], key: str, meaning: str) -> list[str]:
    value = profile.get(key) or []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise _needs_setup(f"{key} must be a list of {meaning}")
    return value


def run(args: Namespace) -> dict[str, Any]:
    from ..preflight import read_profile

    profile = read_profile(args.profile)
    bootstrap = _strings(profile, "bootstrap", "command strings")
    ready = _strings(profile, "bootstrap_ready", "relative paths")
    if not bootstrap and not ready:
        return {"noop": True}
    for entry in ready:
        path = PurePosixPath(entry)
        if path.is_absolute() or ".." in path.parts:
            raise _needs_setup(f"bootstrap_ready {entry} must be a relative path inside the worktree")
    if _git_path(args.worktree, "--git-dir") == _git_path(args.worktree, "--git-common-dir"):
        raise _needs_setup(f"{args.worktree} is the main checkout; bootstrap runs only in a task worktree")
    if bootstrap and args.bootstrap_exit is None:
        raise _needs_setup("bootstrap is set but no --bootstrap-exit was given")
    if args.bootstrap_exit:
        raise _needs_setup(f"bootstrap exited {args.bootstrap_exit}{_log_tail(args.bootstrap_log)}")
    missing = [entry for entry in ready if not (args.worktree / entry).exists()]
    if missing:
        raise _needs_setup(f"missing after bootstrap: {', '.join(missing)}")
    return {"noop": False, "ready": list(ready)}
