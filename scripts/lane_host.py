"""Host headroom probes for lane_run.py's elastic slots. Stdlib only.

An elastic slot (a slot above the lane's declared count) is granted only while
the 1-minute load average per core is below a ceiling and available memory is
at or above a floor. Every probe that cannot read the host returns None, and
None refuses the extra slot: the lane falls back to its declared slots, which
is today's behaviour. The ceiling idea is GNU make's `--max-load` and GNU
parallel's `--load`, per core so one value fits hosts of any size; the floor is
GNU parallel's `--memfree`.

Available memory: Linux `MemAvailable` from /proc/meminfo (the kernel's own
estimate, page cache included); macOS `kern.memorystatus_level` (the free
percentage `memory_pressure` prints) times `hw.memsize`. Anything else: None.
"""

import os
import subprocess
import sys
from typing import Callable

GB = 10**9
PROBE_TIMEOUT_S = 2


def load_per_core() -> float | None:
    try:
        one_minute = os.getloadavg()[0]
    except OSError:
        return None
    cores = os.cpu_count()
    return one_minute / cores if cores else None


def parse_meminfo(text: str) -> int | None:
    for line in text.splitlines():
        name, _, value = line.partition(":")
        if name == "MemAvailable":
            fields = value.split()
            return int(fields[0]) * 1024 if fields and fields[0].isdigit() else None
    return None


def parse_darwin(text: str) -> int | None:
    """`sysctl -n kern.memorystatus_level hw.memsize` output: a percentage, then bytes."""
    fields = text.split()
    if len(fields) != 2 or not all(field.isdigit() for field in fields):
        return None
    percent, total = int(fields[0]), int(fields[1])
    return total * percent // 100 if percent <= 100 else None


def available_bytes() -> int | None:
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="ascii") as meminfo:
                return parse_meminfo(meminfo.read())
        if sys.platform == "darwin":
            done = subprocess.run(["sysctl", "-n", "kern.memorystatus_level", "hw.memsize"],
                                  capture_output=True, text=True, timeout=PROBE_TIMEOUT_S, check=True)
            return parse_darwin(done.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None


def headroom(max_load: float, min_free_bytes: int,
             load: Callable[[], float | None] = load_per_core,
             free: Callable[[], int | None] = available_bytes) -> tuple[bool, str]:
    """(granted, a note for the acquire line) for one elastic slot, read now."""
    per_core = load()
    if per_core is None:
        return False, "load unreadable"
    if per_core >= max_load:
        return False, f"load {per_core:.2f} per core at or above {max_load:.2f}"
    available = free()
    if available is None:
        return False, "free memory unreadable"
    if available < min_free_bytes:
        return False, f"{available / GB:.1f} GB free below {min_free_bytes / GB:.1f}"
    return True, f"load {per_core:.2f} per core, {available / GB:.1f} GB free"
