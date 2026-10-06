"""Shut down the simulators the wrappers provably abandoned, then quit an idle Simulator.app.

    sim_reaper.py [--dry-run] [--idle-minutes N]

The rule: never shut down a device it cannot prove is abandoned. For each
booted device, in order:
  - not a dedicated `graph-sim-*` device (the owner's own, or one a wrapper
    used with --allow-foreign): keep, `reason=foreign`, always
  - no sim-session marker for its current boot (none at all, or one whose
    booted_at differs from the device's lastBootedAt because something
    outside the wrappers booted it again): keep, `reason=unmarked`
  - a live lease holds it (a holder process runs a command on it, or an
    acquired lease was used within its idle window: the one recorded at
    acquire, or N when longer, N defaulting to $GRAPH_SIM_IDLE_MIN, else 15):
    keep, `reason=leased`. Holder start times are read under LC_ALL=C TZ=UTC,
    so a reaper in another session's locale or timezone agrees on who lives.
  - a running xcodebuild, XCTest or simctl names it, by udid or by a
    `name=<its name>` destination: keep, `reason=in-use`
  - otherwise shut it down: `reason=idle` (an acquired lease went unused past
    the window), `dead-owner` (a one-shot wrapper was killed) or `released`
Idle is measured from each lease's last_used_at, never from boot time.

Then, unless --dry-run, leases that no longer hold anything are deleted,
markers and leases of devices no longer booted, or booted again by someone
else, are removed unless a live lease still holds them (a step may be
rebooting the device), graph-sim devices shut down and unleased whose last
boot is older than $GRAPH_SIM_DELETE_DAYS (default 7) are deleted with
`simctl delete` (`deleted <udid> (<name>)`), and Simulator.app is quit when it
runs and no device is booted. --dry-run prints `would ...` and
changes nothing, files included.

Idempotent and safe to run from many sessions at once (one lock). Prints one
line per device, `sim-reaper: <action> <udid> (<name>) reason=<why>`. Exit 0,
or 1 when simctl cannot list devices.
"""

import argparse
import datetime
import sys

import sim_devices as devices
import sim_leases as leases
import sim_lifecycle as sims


def verdict(device: dict, idle: float) -> tuple[bool, str]:
    """(shut it down, why)."""
    udid = device["udid"]
    if not devices.dedicated(device):
        return False, "foreign"
    if not devices.bound(device):
        return False, "unmarked"
    held = [lease for _, lease in leases.on(udid) if lease]
    if any(leases.live(lease, idle) for lease in held):
        return False, "leased"
    if sims.referenced(udid, device.get("name")):
        return False, "in-use"
    kinds = {lease.get("kind") for lease in held}
    return True, "idle" if "lease" in kinds else "dead-owner" if kinds else "released"


def say(text: str) -> None:
    stamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    print(f"{stamp} sim-reaper: {text}", flush=True)


def tidy(claimed: set[str], idle: float) -> None:
    """Drop leases that hold nothing, and the state of devices not booted by a wrapper's boot
    (shut down, or booted again since by someone else) that no live lease still holds."""
    state = sims.state_dir()
    known = {f.name.split(".", 1)[0] for f in state.glob("*.lease")} | {m.stem for m in state.glob("*.json")}
    for udid in known:
        if udid not in claimed and not leases.live_on(udid, idle):
            leases.forget(udid)
        else:
            leases.prune(udid, idle)


def delete_stale(dry_run: bool, idle: float) -> None:
    """Delete graph-sim devices idle (shut down, unleased) past GRAPH_SIM_DELETE_DAYS, default 7."""
    for device in sims.devices():
        if devices.stale(device, idle):
            label = f"{device['udid']} ({device.get('name', '?')}) reason=unused-{devices.delete_days():g}d"
            if dry_run:
                say(f"would delete {label}")
            else:
                sims.simctl("delete", device["udid"])
                leases.forget(device["udid"])
                say(f"deleted {label}")


def reap(dry_run: bool, idle: float) -> int:
    with sims.locked():
        try:
            booted = sims.booted()
        except RuntimeError as error:
            print(f"sim-reaper: {error}", file=sys.stderr)
            return 1
        kept = []
        for device in booted:
            shut, reason = verdict(device, idle)
            label = f"{device['udid']} ({device.get('name', '?')}) reason={reason}"
            if not shut:
                kept.append(device["udid"])
                say(f"kept {label}")
            elif dry_run:
                say(f"would shut down {label}")
            else:
                sims.simctl("shutdown", device["udid"])
                leases.forget(device["udid"])
                say(f"shut down {label}")
        if dry_run:
            delete_stale(True, idle)
            if not kept and sims.gui_running():
                say("would quit Simulator.app")
            return 0
        tidy({d["udid"] for d in booted if d["udid"] in kept and devices.bound(d)}, idle)
        delete_stale(False, idle)
        if sims.quit_gui_if_idle():
            say("quit Simulator.app")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="sim-reaper.sh")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--idle-minutes", type=float, default=sims.idle_minutes())
    args = parser.parse_args(argv)
    return reap(args.dry_run, args.idle_minutes)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
