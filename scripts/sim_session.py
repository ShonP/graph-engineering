"""Run commands on an iOS simulator booted headless, and close it when done.

    sim-session.sh [--device D] [--keep-gui] [--label L] -- <argv...>     one-shot
    sim-session.sh acquire [--device D] [--label L]                       prints SIM_UDID=, SIM_LEASE=
    sim-session.sh run --lease <id> [--keep-gui] -- <argv...>             one step, renews the lease
    sim-session.sh release --lease <id>                                   closes what acquire opened

One-shot: acquire, run argv, release, in one call; the release also runs on
SIGINT, SIGTERM and SIGHUP. Multi-step work (capture, read the PNG, decide the
next step) acquires once, runs each step with `run --lease`, and releases at
the end. `run` exports SIM_UDID, records itself as the lease's holder while
argv runs, and sets last_used_at to now before and after, so the reaper never
takes a device a step is using or used within the idle window
(GRAPH_SIM_IDLE_MIN, default 15 minutes).

Boot is `xcrun simctl boot` (no Simulator.app window) and writes the marker
that makes the device the wrappers' to close. Release drops the lease, then
shuts the device down only when a wrapper booted it, no other live lease holds
it and no running xcodebuild/XCTest/simctl names it (by udid or `name=`; the
shell that launched this wrapper never counts), then quits Simulator.app when
no device is booted. A device someone else booted is used and left running.
Pass `id=$SIM_UDID` to `xcodebuild -destination`.

--device: a udid or an exact device name; default $SIM_DEVICE, else the first
iPhone on the newest runtime. --keep-gui: also show Simulator.app (a recording
that needs the window); cleanup is unchanged. --label: the owner written to the
marker and lease (default $GRAPH_RUN_ID or sim-session).

Exit: argv's own (128+N when signal N ended it), 127 when argv cannot start,
2 usage, an unknown device or a lease that is malformed, released or reaped
(acquire again), 1 when the boot fails. Release of an unknown lease exits 0.
"""

import argparse
import os
import signal
import subprocess
import sys

import sim_leases as leases
import sim_lifecycle as sims

COMMANDS = ("acquire", "run", "release")


def parser_for(name: str, usage: str, *options: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"sim-session.sh {name}".strip(), usage=usage)
    if "device" in options:
        parser.add_argument("--device", default=os.environ.get("SIM_DEVICE"))
        parser.add_argument("--label", default=os.environ.get("GRAPH_RUN_ID") or "sim-session")
    if "lease" in options:
        parser.add_argument("--lease", required=True)
    if "gui" in options:
        parser.add_argument("--keep-gui", action="store_true")
    return parser


def parse(argv: list[str]) -> tuple[str, argparse.Namespace, list[str]]:
    name = argv[0] if argv[:1] and argv[0] in COMMANDS else ""
    rest = argv[1:] if name else argv
    usage, options = {
        "": ("sim-session.sh [--device <name|udid>] [--keep-gui] [--label L] -- <argv...>", ("device", "gui")),
        "acquire": ("sim-session.sh acquire [--device <name|udid>] [--label L]", ("device",)),
        "run": ("sim-session.sh run --lease <id> [--keep-gui] -- <argv...>", ("lease", "gui")),
        "release": ("sim-session.sh release --lease <id>", ("lease",)),
    }[name]
    parser = parser_for(name, usage, *options)
    wants_command = name in ("", "run")
    if wants_command and "--" not in rest:
        parser.error("missing `--` before the command")
    split = rest.index("--") if wants_command else len(rest)
    args, command = parser.parse_args(rest[:split]), rest[split + 1:]
    if wants_command and not command:
        parser.error("no command after `--`")
    if "lease" in options and not leases.valid_id(args.lease):
        parser.error(f"--lease must be the 16 hex characters acquire printed, not {args.lease!r}")
    return name, args, command


def resolve(wanted: str | None) -> dict | None:
    available = sims.devices("available")
    if wanted:
        return next((d for d in available if wanted in (d["udid"], d["name"])), None)
    return next((d for d in available if d["name"].startswith("iPhone") and ".iOS-" in d["runtime"]), None)


def ensure_booted(udid: str, name: str, label: str) -> bool:
    """Boot udid unless it is up, marking it as the wrappers' to close. Call under the lock."""
    current = next((d for d in sims.devices() if d["udid"] == udid), None)
    if current and current["state"] == "Booted":
        return True
    boot = sims.simctl("boot", udid)
    if boot.returncode:
        print(f"sim-session: boot {udid} failed: {boot.stderr.strip()}", file=sys.stderr)
        return False
    sims.write_marker(udid, name, label)
    return True


def settle(udid: str) -> None:
    """Shut a wrapper-booted device down once nothing holds it, then quit an idle Simulator.app.
    A device still named by a running process keeps its marker, so the reaper closes it later."""
    if (sims.marker_path(udid).exists() and not leases.live_on(udid, sims.idle_minutes())
            and not sims.referenced(udid, sims.marker_name(udid))):
        sims.simctl("shutdown", udid)
        leases.forget(udid)
    sims.quit_gui_if_idle()


def release(lease_id: str) -> int:
    with sims.locked():
        lease = leases.find(lease_id)
        if lease is None:
            print(f"sim-session: lease {lease_id} is already released", file=sys.stderr)
            return 0
        leases.path(lease["udid"], lease_id).unlink(missing_ok=True)
        settle(lease["udid"])
    return 0


def execute(command: list[str], udid: str, keep_gui: bool) -> int:
    if keep_gui:
        subprocess.run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", udid], check=False)
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


def acquire(args: argparse.Namespace, kind: str) -> dict | int:
    try:
        device = resolve(args.device)
    except RuntimeError as error:
        print(f"sim-session: {error}", file=sys.stderr)
        return 1
    if device is None:
        print(f"sim-session: no available simulator matches {args.device or 'an iPhone'}", file=sys.stderr)
        return 2
    with sims.locked():
        if not ensure_booted(device["udid"], device["name"], args.label):
            return 1
        return leases.create(device["udid"], args.label, kind, held=kind == "oneshot")


def step(args: argparse.Namespace, command: list[str]) -> int:
    with sims.locked():
        lease = leases.find(args.lease)
        if lease is None:
            print(f"sim-session: lease {args.lease} is released or was reaped after idling; acquire again",
                  file=sys.stderr)
            return 2
        name = sims.marker_name(lease["udid"]) or lease["udid"]
        if not ensure_booted(lease["udid"], name, lease.get("label") or "sim-session"):
            return 1
        lease = leases.renew(lease, held=True)
    try:
        return execute(command, lease["udid"], args.keep_gui)
    finally:
        with sims.locked():
            if (current := leases.find(args.lease)) is not None:
                leases.renew(current, held=False)


def main(argv: list[str]) -> int:
    name, args, command = parse(argv)
    if name == "release":
        return release(args.lease)
    if name == "run":
        return step(args, command)
    lease = acquire(args, "lease" if name == "acquire" else "oneshot")
    if isinstance(lease, int):
        return lease
    if name == "acquire":
        print(f"SIM_UDID={lease['udid']}\nSIM_LEASE={lease['id']}")
        return 0
    try:
        return execute(command, lease["udid"], args.keep_gui)
    finally:
        release(lease["id"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
