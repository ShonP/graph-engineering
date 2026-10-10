"""Run a command inside a host lane: a counted set of slots held by fcntl locks.

    lane_run.py <lane> [--slots N] [--elastic E [--max-load L] [--min-free-gb G]]
                [--max-load5 L5] [--wait-seconds S] -- <argv...>

Serializes host-bound work (a simulator build, a shared local database, a
cluster) across parallel agents and worktrees. Slot k of lane L is the file
`<dir>/<L>.<k>.lock`, where <dir> is ${GRAPH_LANES_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/graph-engineering/lanes}.
The first free slot is taken with flock(LOCK_EX | LOCK_NB), retried every
second for up to S seconds (default 3600).

Two host-load controls, read by scripts/lane_host.py, answer different
questions and compose:

- `--max-load5 L5` (per call, off by default) asks "is the host quiet enough
  for this command at all?". The 5-minute load average, as `uptime` prints it,
  is polled every 15 s until it is at most L5, and only then is any slot taken,
  declared or elastic, so a load wait never holds a slot another caller could
  use. Load is read again once the slot is held; over L5, the slot is released
  and the wait starts over.
- `--elastic E` (per lane, off unless E > 0) asks "may the lane grow past N?".
  When every declared slot is held, slots N+1..N+E may be taken, one probe per
  pass, only while the 1-minute load average per core is below L (default 0.7)
  and available memory is at least G GB (default 2). The probe gates admission
  only: a job already in an elastic slot keeps it when load rises later.

An elastic slot therefore needs both: the load5 gate passed (before and after
taking it) and the headroom probe granted. An unreadable probe never grants
more than the lane without its flag: an unreadable headroom refuses the extra
slot (the lane falls back to N), an unreadable load5 skips the load5 gate.
Load and slot waits share the one --wait-seconds deadline; past it the exit is
75 with `lane <lane>: load5 <x> > <L5> after S s` or `lane <lane> busy after S s`.

There is no release step. The locked descriptor is made inheritable and the
process execs argv, so the lock belongs to the command and every child that
inherits it; the kernel drops it when the last of them exits. A killed agent
therefore never leaves a stale lock, while a child that outlives its parent
keeps the slot, because the lane's work is still running. flock(1) is absent
on macOS, so the lock is taken here rather than shelled out.

Observability: `lane <lane> slot <k> acquired after <s> s` on stderr, with
` (elastic: <load and memory read>)` appended for a slot above N, and
`lane <lane>: waiting for load5 <x> <= <L5>` when a load wait starts.
Exit codes: argv's own once it runs; 2 usage or an invalid lane name; 75
(EX_TEMPFAIL) busy or over load after S s; 126 or 127 when argv cannot be
executed; 73 (EX_CANTCREAT) when the lock directory cannot be used; 130
when interrupted while waiting.
"""

import argparse
import fcntl
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane_host  # noqa: E402

LANE = re.compile(r"[a-z0-9_-]+")
MAX_SLOTS = 64
BUSY = 75
CANTCREAT = 73
LOAD_POLL_SECONDS = 15.0

Headroom = Callable[[], tuple[bool, str]]


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


def positive_float(low: float, inclusive: bool):
    def parse(value: str) -> float:
        number = float(value)
        if not math.isfinite(number) or number < low or (number == low and not inclusive):
            raise ValueError(value)
        return number
    parse.__name__ = f"number {'>=' if inclusive else '>'} {low:g}"
    return parse


def parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    usage = ("lane-run.sh <lane> [--slots N] [--elastic E [--max-load L] [--min-free-gb G]] "
             "[--max-load5 L5] [--wait-seconds S] -- <argv...>")
    parser = argparse.ArgumentParser(prog="lane-run.sh", usage=usage, description="Run a command holding a host lane slot.")
    parser.add_argument("lane", help="lane name, [a-z0-9_-]+")
    parser.add_argument("--slots", type=bounded(1, MAX_SLOTS), default=1, help="concurrent holders (default 1)")
    parser.add_argument("--elastic", type=bounded(0, MAX_SLOTS), default=0,
                        help="extra slots above N, granted only while the host has headroom (default 0, off)")
    parser.add_argument("--max-load", type=positive_float(0, inclusive=False), default=0.7,
                        help="elastic only: 1-minute load average per core must be below L (default 0.7)")
    parser.add_argument("--min-free-gb", type=positive_float(0, inclusive=True), default=2.0,
                        help="elastic only: available memory must be at least G GB (default 2)")
    parser.add_argument("--max-load5", type=positive_float(0, inclusive=False), default=None,
                        help="wait, holding no slot, until the 5-minute load average is at most L5")
    parser.add_argument("--wait-seconds", type=bounded(0), default=3600, help="give up after S s (default 3600)")
    if "--" not in argv:
        parser.error("missing `--` before the command")
    split = argv.index("--")
    args, command = parser.parse_args(argv[:split]), argv[split + 1:]
    if not LANE.fullmatch(args.lane):
        parser.error(f"invalid lane name {args.lane!r}: use [a-z0-9_-]+")
    if not command:
        parser.error("no command after `--`")
    if args.slots + args.elastic > MAX_SLOTS:
        parser.error(f"--slots plus --elastic must be at most {MAX_SLOTS}")
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


def try_elastic(directory: Path, lane: str, slots: int, elastic: int,
                headroom: Headroom) -> tuple[int, int, str] | None:
    """(fd, slot, note) for a free slot above `slots`, probed once per pass, or None."""
    if elastic <= 0:
        return None
    granted, note = headroom()
    if not granted:
        return None
    for slot in range(slots + 1, slots + elastic + 1):
        fd = try_slot(directory / f"{lane}.{slot}.lock")
        if fd is not None:
            return fd, slot, note
    return None


def acquire(lane: str, slots: int, wait_seconds: int, elastic: int = 0, headroom: Headroom | None = None, *,
            deadline: float | None = None, clock=time.monotonic,
            sleep=time.sleep) -> tuple[int, int, float, str | None] | None:
    """(fd, slot, waited seconds, elastic note or None) for the first free slot, or None once the
    deadline (default: now plus wait_seconds) passes. Declared slots first; an elastic slot only
    when `headroom` grants it."""
    directory = lanes_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    started = clock()
    deadline = started + wait_seconds if deadline is None else deadline
    while True:
        for slot in range(1, slots + 1):
            fd = try_slot(directory / f"{lane}.{slot}.lock")
            if fd is not None:
                return fd, slot, clock() - started, None
        extra = try_elastic(directory, lane, slots, elastic, headroom) if headroom else None
        if extra is not None:
            fd, slot, note = extra
            return fd, slot, clock() - started, note
        remaining = deadline - clock()
        if remaining <= 0:
            return None
        sleep(min(1.0, remaining))


def admit(lane: str, slots: int, wait_seconds: int, max_load5: float | None,
          load5: Callable[[], float | None] = lane_host.load5, clock=time.monotonic, sleep=time.sleep,
          elastic: int = 0, headroom: Headroom | None = None) -> tuple[int, int, float]:
    """(fd, slot, waited seconds) once a slot is held with load5 at most max_load5; Busy past the
    deadline. The load5 gate wraps every slot, declared or elastic; an unreadable load5 skips it."""
    started = clock()
    deadline = started + wait_seconds

    def over(load: float | None) -> bool:
        return load is not None and load > max_load5

    def over_load(load: float) -> Busy:
        return Busy(f"lane {lane}: load5 {load:.1f} > {max_load5:g} after {wait_seconds} s")

    def wait_for_load() -> None:
        announced = False
        while over(load := load5()):
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
        held = acquire(lane, slots, wait_seconds, elastic, headroom, deadline=deadline, clock=clock, sleep=sleep)
        if held is None:
            raise Busy(f"lane {lane} busy after {wait_seconds} s")
        fd, slot, _, _ = held
        if max_load5 is None or not over(load := load5()):
            return fd, slot, clock() - started
        os.close(fd)
        remaining = deadline - clock()
        if remaining <= 0:
            raise over_load(load)
        sleep(min(LOAD_POLL_SECONDS, remaining))


def main(argv: list[str]) -> int:
    args, command = parse(argv)
    readings: list[str] = []

    def headroom() -> tuple[bool, str]:
        granted, note = lane_host.headroom(args.max_load, round(args.min_free_gb * lane_host.GB))
        readings.append(note)
        return granted, note

    try:
        fd, slot, waited = admit(args.lane, args.slots, args.wait_seconds, args.max_load5,
                                 elastic=args.elastic, headroom=headroom)
    except KeyboardInterrupt:
        return 130
    except Busy as busy:
        print(busy, file=sys.stderr)
        return BUSY
    except OSError as error:
        print(f"lane {args.lane}: cannot lock under {lanes_dir()}: {error.strerror}", file=sys.stderr)
        return CANTCREAT
    # An elastic slot is only ever taken right after a granted probe, so the last reading is its own.
    suffix = f" (elastic: {readings[-1]})" if slot > args.slots else ""
    print(f"lane {args.lane} slot {slot} acquired after {round(waited)} s{suffix}", file=sys.stderr, flush=True)
    os.set_inheritable(fd, True)
    try:
        os.execvp(command[0], command)
    except OSError as error:
        print(f"lane {args.lane}: {command[0]}: {error.strerror}", file=sys.stderr)
        return 127 if isinstance(error, FileNotFoundError) else 126


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
