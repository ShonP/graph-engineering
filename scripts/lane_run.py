"""Run a command inside a host lane: a counted set of slots held by fcntl locks.

    lane_run.py <lane> [--slots N] [--wait-seconds S] -- <argv...>

Serializes host-bound work (a simulator build, a shared local database, a
cluster) across parallel agents and worktrees. Slot k of lane L is the file
`<dir>/<L>.<k>.lock`, where <dir> is ${GRAPH_LANES_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/graph-engineering/lanes}.
The first free slot is taken with flock(LOCK_EX | LOCK_NB), retried every
second for up to S seconds (default 3600).

There is no release step. The locked descriptor is made inheritable and the
process execs argv, so the lock belongs to the command and every child that
inherits it; the kernel drops it when the last of them exits. A killed agent
therefore never leaves a stale lock, while a child that outlives its parent
keeps the slot, because the lane's work is still running. flock(1) is absent
on macOS, so the lock is taken here rather than shelled out.

Observability: `lane <lane> slot <k> acquired after <s> s` on stderr.
Exit codes: argv's own once it runs; 2 usage or an invalid lane name; 75
(EX_TEMPFAIL) `lane <lane> busy after S s`; 126 or 127 when argv cannot be
executed; 73 (EX_CANTCREAT) when the lock directory cannot be used; 130
when interrupted while waiting.
"""

import argparse
import fcntl
import os
import re
import sys
import time
from pathlib import Path

LANE = re.compile(r"[a-z0-9_-]+")
MAX_SLOTS = 64
BUSY = 75
CANTCREAT = 73


def bounded(low: int, high: int | None = None):
    def parse(value: str) -> int:
        number = int(value)
        if number < low or (high is not None and number > high):
            raise ValueError(value)
        return number
    parse.__name__ = f"integer in [{low}, {high if high is not None else 'inf'}]"
    return parse


def parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    usage = "lane-run.sh <lane> [--slots N] [--wait-seconds S] -- <argv...>"
    parser = argparse.ArgumentParser(prog="lane-run.sh", usage=usage, description="Run a command holding a host lane slot.")
    parser.add_argument("lane", help="lane name, [a-z0-9_-]+")
    parser.add_argument("--slots", type=bounded(1, MAX_SLOTS), default=1, help="concurrent holders (default 1)")
    parser.add_argument("--wait-seconds", type=bounded(0), default=3600, help="give up after S s (default 3600)")
    if "--" not in argv:
        parser.error("missing `--` before the command")
    split = argv.index("--")
    args, command = parser.parse_args(argv[:split]), argv[split + 1:]
    if not LANE.fullmatch(args.lane):
        parser.error(f"invalid lane name {args.lane!r}: use [a-z0-9_-]+")
    if not command:
        parser.error("no command after `--`")
    return args, command


def lanes_dir() -> Path:
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(os.environ.get("GRAPH_LANES_DIR") or Path(cache) / "graph-engineering" / "lanes")


def try_slot(path: Path) -> int | None:
    """An open descriptor holding the exclusive lock on `path`, or None when another holder has it."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def acquire(lane: str, slots: int, wait_seconds: int) -> tuple[int, int, float] | None:
    """(fd, slot, waited seconds) for the first free slot, or None once wait_seconds have passed."""
    directory = lanes_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    started = time.monotonic()
    while True:
        for slot in range(1, slots + 1):
            fd = try_slot(directory / f"{lane}.{slot}.lock")
            if fd is not None:
                return fd, slot, time.monotonic() - started
        remaining = wait_seconds - (time.monotonic() - started)
        if remaining <= 0:
            return None
        time.sleep(min(1.0, remaining))


def main(argv: list[str]) -> int:
    args, command = parse(argv)
    try:
        held = acquire(args.lane, args.slots, args.wait_seconds)
    except KeyboardInterrupt:
        return 130
    except OSError as error:
        print(f"lane {args.lane}: cannot lock under {lanes_dir()}: {error.strerror}", file=sys.stderr)
        return CANTCREAT
    if held is None:
        print(f"lane {args.lane} busy after {args.wait_seconds} s", file=sys.stderr)
        return BUSY
    fd, slot, waited = held
    print(f"lane {args.lane} slot {slot} acquired after {round(waited)} s", file=sys.stderr, flush=True)
    os.set_inheritable(fd, True)
    try:
        os.execvp(command[0], command)
    except OSError as error:
        print(f"lane {args.lane}: {command[0]}: {error.strerror}", file=sys.stderr)
        return 127 if isinstance(error, FileNotFoundError) else 126


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
