"""Run a command inside a host lane: a counted set of slots held by fcntl locks.

    lane_run.py <lane> [--slots N] [--wait-seconds S] [--max-load5 L] -- <argv...>

Serializes host-bound work (a simulator build, a shared local database, a
cluster) across parallel agents and worktrees. Slot k of lane L is the file
`<dir>/<L>.<k>.lock`, where <dir> is ${GRAPH_LANES_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/graph-engineering/lanes}.
The first free slot is taken with flock(LOCK_EX | LOCK_NB), retried every
second for up to S seconds (default 3600).

`--max-load5 L` admits by host load: the 5-minute load average is polled every
15 s until it is at most L, and only then is a slot taken, so a load wait never
holds a slot another caller could use. Load is read again once the slot is
held; over L, the slot is released and the wait starts over. Load and slot
waits share the one --wait-seconds deadline; past it the exit is 75 with
`lane <lane>: load5 <x> > <L> after S s`.

There is no release step. The locked descriptor is made inheritable and the
process execs argv, so the lock belongs to the command and every child that
inherits it; the kernel drops it when the last of them exits. A killed agent
therefore never leaves a stale lock, while a child that outlives its parent
keeps the slot, because the lane's work is still running. flock(1) is absent
on macOS, so the lock is taken here rather than shelled out.

Observability: `lane <lane> slot <k> acquired after <s> s` on stderr, and
`lane <lane>: waiting for load5 <x> <= <L>` when a load wait starts.
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
LOAD_POLL_SECONDS = 15.0


class Busy(Exception):
    """No slot within the deadline, or host load stayed over the cap; the message is the stderr line."""


def bounded(low: int, high: int | None = None):
    def parse(value: str) -> int:
        number = int(value)
        if number < low or (high is not None and number > high):
            raise ValueError(value)
        return number
    parse.__name__ = f"integer in [{low}, {high if high is not None else 'inf'}]"
    return parse


def positive(value: str) -> float:
    number = float(value)
    if not number > 0:
        raise ValueError(value)
    return number


positive.__name__ = "number above 0"


def parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    usage = "lane-run.sh <lane> [--slots N] [--wait-seconds S] [--max-load5 L] -- <argv...>"
    parser = argparse.ArgumentParser(prog="lane-run.sh", usage=usage, description="Run a command holding a host lane slot.")
    parser.add_argument("lane", help="lane name, [a-z0-9_-]+")
    parser.add_argument("--slots", type=bounded(1, MAX_SLOTS), default=1, help="concurrent holders (default 1)")
    parser.add_argument("--wait-seconds", type=bounded(0), default=3600, help="give up after S s (default 3600)")
    parser.add_argument("--max-load5", type=positive, default=None,
                        help="wait, holding no slot, until the 5-minute load average is at most L")
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


def acquire(lane: str, slots: int, deadline: float, clock=time.monotonic, sleep=time.sleep) -> tuple[int, int] | None:
    """(fd, slot) for the first free slot, or None once the clock passes the deadline."""
    directory = lanes_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    while True:
        for slot in range(1, slots + 1):
            fd = try_slot(directory / f"{lane}.{slot}.lock")
            if fd is not None:
                return fd, slot
        remaining = deadline - clock()
        if remaining <= 0:
            return None
        sleep(min(1.0, remaining))


def read_load5() -> float:
    return os.getloadavg()[1]


def admit(lane: str, slots: int, wait_seconds: int, max_load5: float | None,
          load5=read_load5, clock=time.monotonic, sleep=time.sleep) -> tuple[int, int, float]:
    """(fd, slot, waited seconds) once a slot is held with load5 at most max_load5; Busy past the deadline."""
    started = clock()
    deadline = started + wait_seconds

    def over_load(load: float) -> Busy:
        return Busy(f"lane {lane}: load5 {load:.1f} > {max_load5:g} after {wait_seconds} s")

    def wait_for_load() -> None:
        announced = False
        while (load := load5()) > max_load5:
            remaining = deadline - clock()
            if remaining <= 0:
                raise over_load(load)
            if not announced:
                print(f"lane {lane}: waiting for load5 {load:.1f} <= {max_load5:g}", file=sys.stderr, flush=True)
                announced = True
            sleep(min(LOAD_POLL_SECONDS, remaining))

    while True:
        if max_load5 is not None:
            wait_for_load()
        held = acquire(lane, slots, deadline, clock, sleep)
        if held is None:
            raise Busy(f"lane {lane} busy after {wait_seconds} s")
        fd, slot = held
        if max_load5 is None or (load := load5()) <= max_load5:
            return fd, slot, clock() - started
        os.close(fd)
        remaining = deadline - clock()
        if remaining <= 0:
            raise over_load(load)
        sleep(min(LOAD_POLL_SECONDS, remaining))


def main(argv: list[str]) -> int:
    args, command = parse(argv)
    try:
        fd, slot, waited = admit(args.lane, args.slots, args.wait_seconds, args.max_load5)
    except KeyboardInterrupt:
        return 130
    except Busy as busy:
        print(busy, file=sys.stderr)
        return BUSY
    except OSError as error:
        print(f"lane {args.lane}: cannot lock under {lanes_dir()}: {error.strerror}", file=sys.stderr)
        return CANTCREAT
    print(f"lane {args.lane} slot {slot} acquired after {round(waited)} s", file=sys.stderr, flush=True)
    os.set_inheritable(fd, True)
    try:
        os.execvp(command[0], command)
    except OSError as error:
        print(f"lane {args.lane}: {command[0]}: {error.strerror}", file=sys.stderr)
        return 127 if isinstance(error, FileNotFoundError) else 126


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
