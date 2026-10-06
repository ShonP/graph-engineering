"""Shut down simulators nobody alive is using, then quit an idle Simulator.app.

    sim_reaper.py [--dry-run] [--keep-unowned] [--grace-minutes N]

For each booted device, in order:
  - a live sim-session lease holds it: skip (owned)
  - a running xcodebuild, XCTest or simctl names it, by udid or by a
    `name=<its name>` destination: skip (in use)
  - a sim-session marker but no live lease (its wrapper was killed): shut down
  - no marker (booted outside any wrapper: an evidence script, XcodeBuildMCP):
    shut down once it booted more than N minutes ago (default
    $GRAPH_SIM_GRACE_MIN, else 30), so a device an agent drives by separate
    simctl calls survives the session that booted it. --keep-unowned or
    GRAPH_SIM_REAP_UNOWNED=off keeps these and logs `kept ... reason=unowned`.
Then markers of devices no longer booted are removed unless a live wrapper
still holds them (a wrapped command may be rebooting the device), dead leases
are dropped, and Simulator.app is quit when it runs and no device is booted.

Idempotent and safe to run from many sessions at once (one lock). Prints one
line per action, `sim-reaper: <action> <udid> (<name>) reason=<why>`;
--dry-run prints `would ...` and changes nothing. Exit 0, or 1 when simctl
cannot list devices.
"""

import argparse
import datetime
import os
import sys

import sim_lifecycle as sims


def age_minutes(device: dict) -> float | None:
    stamp = device.get("lastBootedAt")
    if not stamp:
        return None
    try:
        booted_at = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.datetime.now(datetime.UTC) - booted_at).total_seconds() / 60


def verdict(device: dict, grace: float, keep_unowned: bool) -> str | None:
    """The reason to shut this device down, "unowned" to keep and log it, or None to keep it."""
    udid = device["udid"]
    if sims.live_leases(udid) or sims.referenced(udid, device.get("name")):
        return None
    if sims.marker_path(udid).exists():
        return "dead-owner"
    if keep_unowned:
        return "unowned"
    age = age_minutes(device)
    if age is not None and age > grace:
        return "unowned-past-grace"
    return None


def say(text: str) -> None:
    stamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    print(f"{stamp} sim-reaper: {text}", flush=True)


def reap(dry_run: bool, grace: float, keep_unowned: bool = False) -> int:
    with sims.locked():
        try:
            booted = sims.booted()
        except RuntimeError as error:
            print(f"sim-reaper: {error}", file=sys.stderr)
            return 1
        kept = []
        for device in booted:
            reason = verdict(device, grace, keep_unowned)
            label = f"{device['udid']} ({device.get('name', '?')}) reason={reason}"
            if reason in (None, "unowned"):
                kept.append(device["udid"])
                if reason:
                    say(f"kept {label}")
            elif dry_run:
                say(f"would shut down {label}")
            else:
                sims.simctl("shutdown", device["udid"])
                sims.forget(device["udid"])
                say(f"shut down {label}")
        if not dry_run:
            live = {d["udid"] for d in booted}
            for marker in sims.state_dir().glob("*.json"):
                if marker.stem not in live and not sims.live_leases(marker.stem):
                    sims.forget(marker.stem)
            for udid in {lease.name.split(".", 1)[0] for lease in sims.state_dir().glob("*.lease")} - live:
                sims.live_leases(udid)  # drops the dead ones
        if dry_run:
            if not kept and sims.gui_running():
                say("would quit Simulator.app")
        elif sims.quit_gui_if_idle():
            say("quit Simulator.app")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="sim-reaper.sh")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-unowned", action="store_true",
                        default=os.environ.get("GRAPH_SIM_REAP_UNOWNED", "on") == "off")
    parser.add_argument("--grace-minutes", type=float,
                        default=float(os.environ.get("GRAPH_SIM_GRACE_MIN") or 30))
    args = parser.parse_args(argv)
    return reap(args.dry_run, args.grace_minutes, args.keep_unowned)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
