"""Shared state for sim_session.py and sim_reaper.py: who owns which simulator.

Many agents, sessions and workflows share one Mac, so a simulator is shut down
only by the last live holder of a device a wrapper booted, or by the reaper
once nothing alive owns it. State lives in
${GRAPH_SIM_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/graph-engineering/sims}:

  <udid>.json         marker: a wrapper booted this device (pid, started_at,
                      owner label). No marker means someone else booted it,
                      and no wrapper ever shuts it down.
  <udid>.<pid>.lease  one per wrapper holding the device: its pid and the
                      process start time, so a recycled pid reads as dead.
  .lock               fcntl lock around every boot, lease and shutdown step.

Stdlib only. `xcrun`, `osascript` and `pgrep` are looked up on PATH, which is
how the tests substitute fakes.
"""

import contextlib
import datetime
import fcntl
import json
import os
import re
import subprocess
from pathlib import Path

TOOLS = ("xcodebuild", "xctest", "XCTest", "simctl")


def state_dir() -> Path:
    base = os.environ.get("GRAPH_SIM_DIR") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "graph-engineering", "sims")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


@contextlib.contextmanager
def locked():
    with open(state_dir() / ".lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def simctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["xcrun", "simctl", *args], capture_output=True, text=True, check=False)


def runtime_version(runtime: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", runtime.rsplit(".", 1)[-1]))


def devices(*filters: str) -> list[dict]:
    """Devices from `simctl list devices <filters> -j`, newest runtime first, each with its runtime."""
    result = simctl("list", "devices", *filters, "-j")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "simctl list failed")
    found = []
    groups = json.loads(result.stdout).get("devices", {})
    for runtime in sorted(groups, key=runtime_version, reverse=True):
        found += [dict(d, runtime=runtime) for d in groups[runtime]]
    return found


def booted() -> list[dict]:
    return devices("booted")


def start_time(pid: int) -> str | None:
    result = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, check=False)
    return result.stdout.strip() or None


def marker_path(udid: str) -> Path:
    return state_dir() / f"{udid}.json"


def write_marker(udid: str, name: str, owner: str) -> None:
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    marker_path(udid).write_text(json.dumps({"udid": udid, "name": name, "pid": os.getpid(),
                                             "started_at": now, "owner": owner}))


def write_lease(udid: str) -> Path:
    path = state_dir() / f"{udid}.{os.getpid()}.lease"
    path.write_text(json.dumps({"pid": os.getpid(), "started": start_time(os.getpid())}))
    return path


def live_leases(udid: str) -> list[Path]:
    """Leases on udid whose process is still the one that wrote them; dead ones are deleted."""
    live = []
    for path in state_dir().glob(f"{udid}.*.lease"):
        try:
            lease = json.loads(path.read_text())
            alive = start_time(int(lease["pid"])) == lease["started"] and lease["started"] is not None
        except (OSError, ValueError, KeyError, TypeError):
            alive = False
        if alive:
            live.append(path)
        else:
            path.unlink(missing_ok=True)
    return live


def forget(udid: str) -> None:
    marker_path(udid).unlink(missing_ok=True)
    for path in state_dir().glob(f"{udid}.*.lease"):
        path.unlink(missing_ok=True)


def processes() -> dict[str, tuple[str, str]]:
    """pid -> (ppid, command) for every running process."""
    result = subprocess.run(["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True, check=False)
    table = {}
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2:
            table[parts[0]] = (parts[1], parts[2] if len(parts) == 3 else "")
    return table


def lineage(table: dict[str, tuple[str, str]]) -> set[str]:
    """This process and its ancestors: the shell that launched a wrapper waits on it and
    may name the device on its own command line, but it is not another user of the device."""
    chain, pid = set(), str(os.getpid())
    while pid in table and pid not in chain:
        chain.add(pid)
        pid = table[pid][0]
    return chain | {str(os.getpid())}


def referenced(udid: str, name: str | None = None) -> bool:
    """A running xcodebuild, XCTest or simctl process outside this process's lineage names this
    device on its command line: by udid, or with `name`, by a `name=<name>` destination (a prefix
    match keeps more, never less)."""
    table = processes()
    mine = lineage(table)
    needles = [udid] + ([f"name={name}"] if name else [])
    return any(pid not in mine and any(n in command for n in needles) and any(tool in command for tool in TOOLS)
               for pid, (_, command) in table.items())


def gui_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Simulator"], capture_output=True, check=False).returncode == 0


def quit_gui_if_idle(dry_run: bool = False) -> bool:
    """Quit Simulator.app when it runs and no device is booted. True when it was (or would be) quit."""
    if booted() or not gui_running():
        return False
    if not dry_run:
        subprocess.run(["osascript", "-e", 'quit app "Simulator"'], capture_output=True, check=False)
    return True
