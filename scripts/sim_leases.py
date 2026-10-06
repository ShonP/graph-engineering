"""Leases: who holds a wrapper's simulator, and when they last used it.

One file per holder, `<udid>.<id>.lease` in sim_lifecycle.state_dir():

  id            16 hex chars, the handle `run --lease` and `release --lease` take
  udid, label   the device and who asked for it
  kind          "oneshot" (`sim-session.sh -- cmd`) or "lease" (`acquire`)
  idle_min      the idle window, GRAPH_SIM_IDLE_MIN at acquire (default 15)
  acquired_at, last_used_at
                epoch seconds from sim_lifecycle.now(); every `run` renews
                last_used_at before and after its command
  holders       [{pid, started}], one per sim-session process running a
                command on the device (concurrent `run --lease` steps each
                hold a slot); the start time, read under LC_ALL=C TZ=UTC so
                every session reads it alike, makes a recycled pid read as dead

A lease is live while any holder process runs. An acquired lease also stays
live until it has sat unused since last_used_at for its idle window, or the
reader's if longer (the reaper's --idle-minutes); a oneshot lease dies with
its process. Release
deletes the file. Writes go through a temp file and a rename, so a reader never
sees half a lease. Reading never deletes anything; only prune() and forget() do.
"""

import json
import os
import re
import secrets
from pathlib import Path

import sim_lifecycle as sims

LEASE_ID = re.compile(r"[0-9a-f]{16}")


def valid_id(lease_id: str | None) -> bool:
    return bool(LEASE_ID.fullmatch(lease_id or ""))


def path(udid: str, lease_id: str) -> Path:
    return sims.state_dir() / f"{udid}.{lease_id}.lease"


def read(file: Path) -> dict | None:
    try:
        lease = json.loads(file.read_text())
    except (OSError, ValueError):
        return None
    return lease if isinstance(lease, dict) else None


def find(lease_id: str) -> dict | None:
    """The lease with this id, or None when it is malformed, released or reaped."""
    if not valid_id(lease_id):
        return None
    return next((lease for file in sims.state_dir().glob(f"*.{lease_id}.lease") if (lease := read(file))), None)


def write(lease: dict) -> None:
    target = path(lease["udid"], lease["id"])
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(lease))
    os.replace(temp, target)


def holder() -> dict:
    return {"pid": os.getpid(), "started": sims.start_time(os.getpid())}


def alive(held: object) -> bool:
    if not isinstance(held, dict) or held.get("started") is None:
        return False
    try:
        return sims.start_time(int(held["pid"])) == held["started"]
    except (KeyError, TypeError, ValueError):
        return False


def holders(lease: dict) -> list[dict]:
    """The holders still running, this process excluded."""
    found = lease.get("holders")
    mine = os.getpid()
    return [h for h in found if alive(h) and h.get("pid") != mine] if isinstance(found, list) else []


def create(udid: str, label: str, kind: str, held: bool) -> dict:
    stamp = sims.now()
    lease = {"id": secrets.token_hex(8), "udid": udid, "label": label, "kind": kind,
             "idle_min": sims.idle_minutes(), "acquired_at": stamp, "last_used_at": stamp,
             "holders": [holder()] if held else []}
    write(lease)
    return lease


def renew(lease: dict, held: bool) -> dict:
    """last_used_at = now; held adds this process to the holders running a command on the
    device, otherwise it leaves them. Other steps on the same lease keep their slots."""
    lease = dict(lease, last_used_at=sims.now(), holders=holders(lease) + ([holder()] if held else []))
    write(lease)
    return lease


def live(lease: dict, idle: float) -> bool:
    """Held by a running step, or an acquired lease used within its window: the longer of the
    one recorded at acquire and `idle`, so no session's setting cuts another's lease short."""
    found = lease.get("holders")
    if isinstance(found, list) and any(alive(h) for h in found):
        return True
    if lease.get("kind") != "lease":
        return False
    try:
        window = max(idle, float(lease.get("idle_min") or 0))
        return sims.now() - float(lease["last_used_at"]) < window * 60
    except (KeyError, TypeError, ValueError):
        return False


def expired(lease: dict | None, idle: float) -> bool:
    """No holder process runs and the lease sat unused past its window, whatever its kind. A
    lease that cannot be read is never expired: nothing proves its holder gone."""
    found = (lease or {}).get("holders")
    if lease is None or (isinstance(found, list) and any(alive(h) for h in found)):
        return False
    try:
        window = max(idle, float(lease.get("idle_min") or 0))
        return sims.now() - float(lease["last_used_at"]) >= window * 60
    except (KeyError, TypeError, ValueError):
        return False


def free(udid: str, idle: float) -> bool:
    """Release udid's expired leases; True when none is left, so acquire may hand the device out."""
    left = False
    for file, lease in on(udid):
        if expired(lease, idle):
            file.unlink(missing_ok=True)
        else:
            left = True
    return not left


def on(udid: str) -> list[tuple[Path, dict | None]]:
    return [(file, read(file)) for file in sims.state_dir().glob(f"{udid}.*.lease")]


def live_on(udid: str, idle: float) -> list[dict]:
    return [lease for _, lease in on(udid) if lease and live(lease, idle)]


def prune(udid: str, idle: float) -> None:
    """Delete the leases on udid that no longer hold it."""
    for file, lease in on(udid):
        if not (lease and live(lease, idle)):
            file.unlink(missing_ok=True)


def forget(udid: str) -> None:
    sims.marker_path(udid).unlink(missing_ok=True)
    for file, _ in on(udid):
        file.unlink(missing_ok=True)
