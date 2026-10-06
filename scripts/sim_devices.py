"""Which simulators the wrappers may boot and shut down, and which boot of one they own.

Dedicated devices: the wrappers never use the owner's simulators. By default
they reuse, or `simctl create`, a device named `graph-sim-<runtime>-<n>` (the
newest iPhone type on the newest available iOS runtime), so the owner's Xcode
or XcodeBuildMCP never lands on a device a wrapper will shut down. A device
with any other name is booted or shut down only when `--device` names it and
`--allow-foreign` is passed; the reaper never touches one.

Boot binding: a marker claims one boot, the device's lastBootedAt when the
wrapper booted it. A device booted again since (the owner's `simctl shutdown
all` then Xcode, a Mac reboot) is not the wrappers' to close, whatever its
marker says. A device listing without lastBootedAt binds to nothing, so the
default on such a host is to leave devices running, never to close one.
"""

import datetime
import json
import os
import re

import sim_leases as leases
import sim_lifecycle as sims

PREFIX = "graph-sim-"
DELETE_DAYS = 7.0


def dedicated(device: dict) -> bool:
    return str(device.get("name", "")).startswith(PREFIX)


def bound(device: dict) -> bool:
    """A wrapper booted this device and nothing booted it again since."""
    marker = sims.read_marker(device["udid"])
    stamp = device.get("lastBootedAt")
    return marker is not None and stamp is not None and marker.get("booted_at") == stamp


def booted_at(udid: str) -> str | None:
    return (sims.device(udid) or {}).get("lastBootedAt")


def newest_ios_runtime() -> dict | None:
    result = sims.simctl("list", "runtimes", "-j")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "simctl list runtimes failed")
    runtimes = [r for r in json.loads(result.stdout).get("runtimes", [])
                if r.get("isAvailable") and ".iOS-" in r.get("identifier", "")]
    return max(runtimes, key=lambda r: sims.runtime_version(r["identifier"]), default=None)


def suffix(name: str) -> int:
    found = re.search(r"-(\d+)$", name)
    return int(found.group(1)) if found else 0


def create(runtime: dict) -> dict | None:
    """A new graph-sim device of the runtime's newest iPhone type (simctl lists them newest first)."""
    device_type = next((t["identifier"] for t in runtime.get("supportedDeviceTypes", [])
                        if t.get("productFamily") == "iPhone"), None)
    if device_type is None:
        return None
    taken = {d["name"] for d in sims.devices() if dedicated(d)}
    stem, n = f"{PREFIX}{runtime['identifier'].rsplit('.', 1)[-1]}-", 1
    while f"{stem}{n}" in taken:
        n += 1
    result = sims.simctl("create", f"{stem}{n}", device_type, runtime["identifier"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "simctl create failed")
    return {"udid": result.stdout.strip(), "name": f"{stem}{n}", "state": "Shutdown",
            "runtime": runtime["identifier"]}


def pick(idle: float) -> dict | None:
    """The first graph-sim device on the newest iOS runtime no live lease holds, else a new one.
    Call under the lock, so two acquires never both create."""
    runtime = newest_ios_runtime()
    if runtime is None:
        return None
    ours = sorted((d for d in sims.devices("available") if dedicated(d) and d["runtime"] == runtime["identifier"]),
                  key=lambda d: suffix(d["name"]))
    return next((d for d in ours if not leases.live_on(d["udid"], idle)), None) or create(runtime)


def resolve(wanted: str | None, allow_foreign: bool, idle: float) -> tuple[dict | None, str]:
    """(device, why not). Raises RuntimeError when simctl fails."""
    if not wanted:
        device = pick(idle)
        return device, "" if device else "no available iOS runtime with an iPhone device type"
    device = next((d for d in sims.devices("available") if wanted in (d["udid"], d["name"])), None)
    if device is None:
        return None, f"no available simulator matches {wanted}"
    if not dedicated(device) and not allow_foreign:
        return None, (f"{wanted} is not a dedicated {PREFIX}* device, and agents never touch other devices; "
                      "omit --device to get a dedicated one, or pass --allow-foreign when the owner named it")
    return device, ""


def rebind(udid: str, before: str | None) -> None:
    """After the wrapper's own step: when the step rebooted the device (the marker still names the
    boot the step started on), the new boot is the wrappers' too. Call under the lock."""
    marker = sims.read_marker(udid)
    now = booted_at(udid)
    if before is not None and marker and marker.get("booted_at") == before and now not in (None, before):
        sims.marker_path(udid).write_text(json.dumps(dict(marker, booted_at=now)))


def delete_days() -> float:
    try:
        return float(os.environ.get("GRAPH_SIM_DELETE_DAYS") or DELETE_DAYS)
    except ValueError:
        return DELETE_DAYS


def stale(device: dict, idle: float) -> bool:
    """A shut-down graph-sim device no lease holds, last booted more than delete_days() ago."""
    if not dedicated(device) or device.get("state") != "Shutdown" or leases.live_on(device["udid"], idle):
        return False
    try:
        last = datetime.datetime.fromisoformat(device["lastBootedAt"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return False
    return sims.now() - last > delete_days() * 86400
