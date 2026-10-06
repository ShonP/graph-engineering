"""Shared fixture for the simulator lifecycle tests (not a test module itself).

Every case runs the public scripts with a SYNTHETIC xcrun/osascript/pgrep/open
(tests/scripts/fixtures/fake_xcrun.py) first on PATH and a throwaway
GRAPH_SIM_DIR, so no Xcode is needed and no real simulator is touched. The
devices are synthetic too: two dedicated graph-sim iPhones (A, B) and one owner
device (O) on a fake iOS runtime, plus an older runtime with none. Time is
simulated through GRAPH_SIM_CLOCK (epoch seconds the scripts read as now).
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "scripts" / "sim-session.sh"
REAPER = ROOT / "scripts" / "sim-reaper.sh"
FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_xcrun.py"
RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-26-5"
OLDER_RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-18-6"
PRO = "com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro"
# A and B are the wrappers' dedicated devices; O is the owner's own (Xcode's), never the wrappers'.
A = "AAAAAAAA-0000-4000-8000-000000000001"
B = "BBBBBBBB-0000-4000-8000-000000000002"
O = "CCCCCCCC-0000-4000-8000-000000000003"
NAMES = {A: "graph-sim-iOS-26-5-1", B: "graph-sim-iOS-26-5-2", O: "iPhone 17"}
OLD = "2026-01-01T00:00:00Z"
# Newest first, as `simctl list runtimes -j` orders supportedDeviceTypes.
IPHONES = [{"identifier": PRO, "name": "iPhone 17 Pro", "productFamily": "iPhone"},
           {"identifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17", "name": "iPhone 17", "productFamily": "iPhone"},
           {"identifier": "com.apple.CoreSimulator.SimDeviceType.iPad-Pro-13", "name": "iPad Pro 13", "productFamily": "iPad"}]
RUNTIMES = [{"identifier": OLDER_RUNTIME, "platform": "iOS", "version": "18.6", "isAvailable": True,
             "supportedDeviceTypes": IPHONES[1:]},
            {"identifier": RUNTIME, "platform": "iOS", "version": "26.5", "isAvailable": True,
             "supportedDeviceTypes": IPHONES},
            {"identifier": "com.apple.CoreSimulator.SimRuntime.watchOS-26-5", "platform": "watchOS",
             "version": "26.5", "isAvailable": True, "supportedDeviceTypes": []}]
T0 = 1_790_000_000  # a fixed simulated "now", in epoch seconds
# Holds the device until <file> appears; a plain wait, no network.
HOLD = "import os, sys, time\nwhile not os.path.exists(sys.argv[1]): time.sleep(0.05)\n"


class SimFixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for tool in ("xcrun", "osascript", "pgrep", "open"):
            (bin_dir / tool).symlink_to(FAKE)
        FAKE.chmod(0o755)
        self.state = self.tmp / "state.json"
        self.log = self.tmp / "calls.log"
        self.log.write_text("")
        self.write_state({A: "Shutdown", B: "Shutdown"})
        self.env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
                        FAKE_SIM_STATE=str(self.state), FAKE_SIM_LOG=str(self.log),
                        GRAPH_SIM_DIR=str(self.tmp / "sims"))
        for name in ("GRAPH_SIM_IDLE_MIN", "GRAPH_SIM_CLOCK"):
            self.env.pop(name, None)

    def at(self, minutes):
        """Move the simulated clock to T0 + minutes."""
        self.env["GRAPH_SIM_CLOCK"] = str(T0 + minutes * 60)

    def write_state(self, states, gui=False, booted_at=None):
        """A, B and O in the given states (O Shutdown unless named); devices the scripts created
        through `simctl create` stay as they are."""
        created = [d for d in self.all_devices() if d["udid"] not in NAMES] if self.state.exists() else []
        states = {O: "Shutdown", **states}
        devices = [{"udid": u, "name": NAMES[u], "state": s, "isAvailable": True, "deviceTypeIdentifier": PRO,
                    **({"lastBootedAt": booted_at or OLD} if s == "Booted" else {})} for u, s in states.items()]
        self.state.write_text(json.dumps({"devices": {RUNTIME: devices + created, OLDER_RUNTIME: []},
                                          "runtimes": RUNTIMES, "gui": gui}))

    def all_devices(self):
        return [d for group in json.loads(self.state.read_text())["devices"].values() for d in group]

    def device(self, udid):
        return next((d for d in self.all_devices() if d["udid"] == udid), None)

    def set_device(self, udid, **fields):
        """Change fields of one synthetic device in place (lastBootedAt, state)."""
        state = json.loads(self.state.read_text())
        for group in state["devices"].values():
            for d in group:
                if d["udid"] == udid:
                    d.update(fields)
        self.state.write_text(json.dumps(state))

    def device_state(self, udid):
        return self.device(udid)["state"]

    def gui(self):
        return json.loads(self.state.read_text())["gui"]

    def calls(self):
        return self.log.read_text().splitlines()

    def files(self):
        sims = self.tmp / "sims"
        return sorted(p.name for p in sims.iterdir() if p.name != ".lock") if sims.exists() else []

    def session(self, *args, timeout=30):
        return subprocess.run(["bash", str(SESSION), *args], env=self.env, capture_output=True, text=True, timeout=timeout)

    def acquire(self, *args):
        """`sim-session.sh acquire`; returns (udid, lease id)."""
        result = self.session("acquire", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        return values["SIM_UDID"], values["SIM_LEASE"]

    def start_holder(self, device, release, *prefix):
        """A one-shot (or, with prefix `run --lease <id>`, a leased) wrapper holding the device until release."""
        argv = [*prefix] if prefix else ["--device", device]
        process = subprocess.Popen(["bash", str(SESSION), *argv, "--", sys.executable, "-c", HOLD, str(release)],
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        before, deadline = self.held(), time.monotonic() + 10
        while self.held() <= before:  # the holder is recorded after the boot, under the lock
            self.assertLess(time.monotonic(), deadline, "holder never leased the device")
            time.sleep(0.05)
        return process

    def held(self):
        """How many running holder processes the leases name."""
        count = 0
        for path in (self.tmp / "sims").glob("*.lease"):
            try:
                count += len(json.loads(path.read_text()).get("holders") or [])
            except (OSError, ValueError, TypeError):
                pass
        return count

    def mark_dead_owner(self, udid):
        """A marker for the device's current boot with no live lease: the wrapper that booted udid was killed."""
        sims = self.tmp / "sims"
        sims.mkdir(exist_ok=True)
        (sims / f"{udid}.json").write_text(json.dumps({"udid": udid, "pid": 999999, "owner": "test",
                                                       "booted_at": self.device(udid).get("lastBootedAt")}))

    def start_build(self, *destination):
        """A SYNTHETIC `xcodebuild` process with the given destination on its command line."""
        fake = self.tmp / "xcodebuild"
        fake.write_text(HOLD)
        release = self.tmp / f"release-build-{len(list(self.tmp.glob('release-build-*')))}"
        build = subprocess.Popen([sys.executable, str(fake), str(release), *destination])
        self.addCleanup(lambda: build.poll() is None and build.kill())
        return build, release

    def reap(self, *args):
        return subprocess.run(["bash", str(REAPER), *args], env=self.env, capture_output=True, text=True, timeout=30)
