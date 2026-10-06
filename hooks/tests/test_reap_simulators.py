#!/usr/bin/env python3
"""Stop / SubagentStop hook reap-simulators.sh: start the reaper, never wait for it.

Stdlib only. Run from any directory:

    python3 hooks/tests/test_reap_simulators.py

Drives the hook the way Claude Code does (the event's JSON on stdin) with the
SYNTHETIC xcrun/osascript/pgrep/open from tests/scripts/fixtures/fake_xcrun.py
first on PATH, a throwaway GRAPH_SIM_DIR and a device booted long ago with no
owner. FAKE_SIM_DELAY makes every fake call slow, so a hook that waited for the
reaper would blow the 1 s budget.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent
SCRIPT = HOOKS / "scripts" / "reap-simulators.sh"
FAKE = HOOKS.parent / "tests" / "scripts" / "fixtures" / "fake_xcrun.py"
UDID = "AAAAAAAA-0000-4000-8000-000000000001"
EVENT = json.dumps({"hook_event_name": "SubagentStop", "session_id": "s", "stop_hook_active": False})


class ReapHook(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for tool in ("xcrun", "osascript", "pgrep", "open"):
            (bin_dir / tool).symlink_to(FAKE)
        self.state = self.tmp / "state.json"
        self.state.write_text(json.dumps({"gui": True, "devices": {"com.apple.CoreSimulator.SimRuntime.iOS-26-5": [
            {"udid": UDID, "name": "iPhone 17", "state": "Booted", "isAvailable": True,
             "lastBootedAt": "2026-01-01T00:00:00Z"}]}}))
        self.log = self.tmp / "calls.log"
        self.log.write_text("")
        self.env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
                        FAKE_SIM_STATE=str(self.state), FAKE_SIM_LOG=str(self.log), FAKE_SIM_DELAY="0.5",
                        GRAPH_SIM_DIR=str(self.tmp / "sims"), GRAPH_SIM_GRACE_MIN="30")
        self.env.pop("GRAPH_SIM_REAPER", None)

    def fire(self, env=None):
        started = time.monotonic()
        result = subprocess.run(["bash", str(SCRIPT)], input=EVENT, env=env or self.env,
                                capture_output=True, text=True, timeout=10)
        return result, time.monotonic() - started

    def device_state(self):
        return json.loads(self.state.read_text())["devices"]["com.apple.CoreSimulator.SimRuntime.iOS-26-5"][0]["state"]

    def test_returns_inside_budget_and_the_reaper_finishes_in_the_background(self):
        result, elapsed = self.fire()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "", "a background hook prints nothing into the session")
        self.assertLess(elapsed, 1.0)
        deadline = time.monotonic() + 15
        while self.device_state() != "Shutdown":
            self.assertLess(time.monotonic(), deadline, "the detached reaper never ran")
            time.sleep(0.1)
        log = (self.tmp / "sims" / "reaper.log").read_text()
        self.assertIn(f"shut down {UDID}", log)

    def test_kill_switch_starts_nothing(self):
        result, _ = self.fire(dict(self.env, GRAPH_SIM_REAPER="off"))
        self.assertEqual(result.returncode, 0)
        time.sleep(1.5)
        self.assertEqual(self.log.read_text(), "")
        self.assertEqual(self.device_state(), "Booted")

    def test_no_xcrun_on_path_starts_nothing(self):
        env = dict(self.env, PATH="/nonexistent")
        result = subprocess.run(["/bin/bash", str(SCRIPT)], input=EVENT, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        time.sleep(1.5)
        self.assertEqual(self.log.read_text(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
