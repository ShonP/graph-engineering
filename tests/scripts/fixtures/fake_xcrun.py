#!/usr/bin/env python3
"""SYNTHETIC stand-in for `xcrun simctl`, `osascript`, `pgrep` and `open`.

Installed under those names in a test's bin directory (first on PATH), so the
simulator lifecycle scripts run without Xcode. State lives in $FAKE_SIM_STATE
(the `simctl list -j` shape plus a `gui` flag for Simulator.app); every call is
appended to $FAKE_SIM_LOG as one line, `<tool> <args...>`.
"""

import datetime
import json
import os
import sys
from pathlib import Path

STATE = Path(os.environ["FAKE_SIM_STATE"])
LOG = Path(os.environ["FAKE_SIM_LOG"])


def load():
    return json.loads(STATE.read_text())


def save(state):
    STATE.write_text(json.dumps(state))


def devices(state):
    return [d for group in state["devices"].values() for d in group]


def simctl(args):
    state = load()
    if args[:2] == ["list", "devices"]:
        rest = args[2:]
        out = {}
        for runtime, group in state["devices"].items():
            keep = [d for d in group if not ("booted" in rest and d["state"] != "Booted")
                    and not ("available" in rest and not d.get("isAvailable", True))]
            out[runtime] = keep
        print(json.dumps({"devices": out}))
        return 0
    if args and args[0] in ("boot", "shutdown") and len(args) == 2:
        for d in devices(state):
            if d["udid"] == args[1]:
                if args[0] == "boot":
                    if d["state"] == "Booted":
                        print("Unable to boot device in current state: Booted", file=sys.stderr)
                        return 149
                    d["state"] = "Booted"
                    d["lastBootedAt"] = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    d["state"] = "Shutdown"
                save(state)
                return 0
        print(f"Invalid device: {args[1]}", file=sys.stderr)
        return 148
    print(f"fake simctl: unsupported {args}", file=sys.stderr)
    return 64


def main():
    tool = Path(sys.argv[0]).name
    args = sys.argv[1:]
    with LOG.open("a") as log:
        log.write(" ".join([tool, *args]) + "\n")
    if tool == "xcrun":
        return simctl(args[1:]) if args[:1] == ["simctl"] else 64
    if tool == "osascript":
        state = load()
        if 'quit app "Simulator"' in " ".join(args):
            state["gui"] = False
            save(state)
        return 0
    if tool == "pgrep":
        return 0 if load().get("gui") else 1
    if tool == "open":
        state = load()
        state["gui"] = True
        save(state)
        return 0
    return 64


if __name__ == "__main__":
    sys.exit(main())
