"""Run a command with an iOS simulator booted headless, and close it afterwards.

    sim_session.py [--device <name|udid>] [--keep-gui] [--label L] -- <argv...>

Boots the device with `xcrun simctl boot` (no Simulator.app window), exports
SIM_UDID to argv, runs it, and on exit, SIGINT, SIGTERM or SIGHUP: drops this
wrapper's lease, shuts the device down when a wrapper booted it, no live
wrapper still holds it and no running xcodebuild/XCTest/simctl names it (by
udid or `name=`; then the marker stays and the reaper closes it later; the
shell that launched this wrapper never counts), then quits Simulator.app when
no device is booted. A
device someone else booted (no marker) is used and left running. Pass
`id=$SIM_UDID` to `xcodebuild -destination` so it reuses the booted device
instead of booting one of its own.

--device: a udid or an exact device name; default $SIM_DEVICE, else the first
iPhone on the newest runtime. --keep-gui: also show Simulator.app while argv
runs (a recording that needs the window); cleanup is unchanged.
--label: the owner written to the marker (default $GRAPH_RUN_ID or sim-session).

Exit: argv's own (128+N when signal N ended it), 127 when argv cannot start,
2 usage or an unknown device, 1 when the boot fails.
"""

import argparse
import os
import signal
import subprocess
import sys

import sim_lifecycle as sims


def parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(prog="sim-session.sh",
                                     usage="sim-session.sh [--device <name|udid>] [--keep-gui] [--label L] -- <argv...>")
    parser.add_argument("--device", default=os.environ.get("SIM_DEVICE"))
    parser.add_argument("--keep-gui", action="store_true")
    parser.add_argument("--label", default=os.environ.get("GRAPH_RUN_ID") or "sim-session")
    if "--" not in argv:
        parser.error("missing `--` before the command")
    split = argv.index("--")
    args, command = parser.parse_args(argv[:split]), argv[split + 1:]
    if not command:
        parser.error("no command after `--`")
    return args, command


def resolve(wanted: str | None) -> dict | None:
    available = sims.devices("available")
    if wanted:
        return next((d for d in available if wanted in (d["udid"], d["name"])), None)
    return next((d for d in available if d["name"].startswith("iPhone") and ".iOS-" in d["runtime"]), None)


def acquire(device: dict, label: str) -> bool:
    udid = device["udid"]
    with sims.locked():
        current = next((d for d in sims.devices() if d["udid"] == udid), device)
        if current["state"] != "Booted":
            boot = sims.simctl("boot", udid)
            if boot.returncode:
                print(f"sim-session: boot {udid} failed: {boot.stderr.strip()}", file=sys.stderr)
                return False
            sims.write_marker(udid, device["name"], label)
        sims.write_lease(udid)
    return True


def release(udid: str, name: str) -> None:
    """Drop this lease; the last holder shuts a wrapper-booted device down unless a process
    outside any wrapper still names it, in which case the marker stays for the reaper."""
    with sims.locked():
        (sims.state_dir() / f"{udid}.{os.getpid()}.lease").unlink(missing_ok=True)
        if sims.marker_path(udid).exists() and not sims.live_leases(udid) and not sims.referenced(udid, name):
            sims.simctl("shutdown", udid)
            sims.forget(udid)
        sims.quit_gui_if_idle()


def run(command: list[str], udid: str) -> int:
    try:
        child = subprocess.Popen(command, env=dict(os.environ, SIM_UDID=udid))
    except OSError as error:
        print(f"sim-session: cannot run {command[0]}: {error}", file=sys.stderr)
        return 127

    def forward(signum, _frame):
        if child.poll() is None:
            child.send_signal(signum)

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, forward)
    code = child.wait()
    return 128 - code if code < 0 else code


def main(argv: list[str]) -> int:
    args, command = parse(argv)
    try:
        device = resolve(args.device)
    except RuntimeError as error:
        print(f"sim-session: {error}", file=sys.stderr)
        return 1
    if device is None:
        print(f"sim-session: no available simulator matches {args.device or 'an iPhone'}", file=sys.stderr)
        return 2
    udid = device["udid"]
    if not acquire(device, args.label):
        return 1
    try:
        if args.keep_gui:
            subprocess.run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", udid], check=False)
        return run(command, udid)
    finally:
        release(udid, device["name"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
