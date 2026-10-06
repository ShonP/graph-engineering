"""sim-session.sh and sim-reaper.sh: close every simulator an agent opens.

Every case runs the public scripts with a SYNTHETIC xcrun/osascript/pgrep/open
(tests/scripts/fixtures/fake_xcrun.py) first on PATH and a throwaway
GRAPH_SIM_DIR, so no Xcode is needed and no real simulator is touched. The
devices are synthetic too: two iPhones on one fake iOS runtime.

The rule under test: a wrapper shuts down only a device a wrapper booted, and
only when no live wrapper still holds it; the reaper never touches a device a
live process owns; Simulator.app is quit only when nothing is booted.
"""

import json
import os
import signal
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
A = "AAAAAAAA-0000-4000-8000-000000000001"
B = "BBBBBBBB-0000-4000-8000-000000000002"
OLD = "2026-01-01T00:00:00Z"
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

    def write_state(self, states, gui=False, booted_at=None):
        names = {A: "iPhone 17", B: "iPhone 17 Pro"}
        devices = [{"udid": u, "name": names[u], "state": s, "isAvailable": True,
                    **({"lastBootedAt": booted_at or OLD} if s == "Booted" else {})} for u, s in states.items()]
        self.state.write_text(json.dumps({"devices": {RUNTIME: devices}, "gui": gui}))

    def device_state(self, udid):
        devices = json.loads(self.state.read_text())["devices"][RUNTIME]
        return next(d["state"] for d in devices if d["udid"] == udid)

    def gui(self):
        return json.loads(self.state.read_text())["gui"]

    def calls(self):
        return self.log.read_text().splitlines()

    def session(self, *args, timeout=30):
        return subprocess.run(["bash", str(SESSION), *args], env=self.env, capture_output=True, text=True, timeout=timeout)

    def start_holder(self, device, release):
        process = subprocess.Popen(["bash", str(SESSION), "--device", device, "--", sys.executable, "-c", HOLD, str(release)],
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        deadline = time.monotonic() + 10
        while not list((self.tmp / "sims").glob("*.lease")):  # written after the boot, under the lock
            self.assertLess(time.monotonic(), deadline, "holder never leased the device")
            time.sleep(0.05)
        return process

    def mark_dead_owner(self, udid):
        """A marker with no live lease: the wrapper that booted udid was killed."""
        sims = self.tmp / "sims"
        sims.mkdir(exist_ok=True)
        (sims / f"{udid}.json").write_text(json.dumps({"udid": udid, "pid": 999999, "owner": "test"}))

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


class Session(SimFixture):
    def test_boots_headless_exports_udid_and_shuts_down_what_it_booted(self):
        out = self.tmp / "udid.txt"
        result = self.session("--device", "iPhone 17", "--", "sh", "-c", f'printf %s "$SIM_UDID" > {out}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(out.read_text(), A)
        self.assertIn(f"xcrun simctl boot {A}", self.calls())
        self.assertIn(f"xcrun simctl shutdown {A}", self.calls())
        self.assertEqual(self.device_state(A), "Shutdown")
        self.assertFalse(any(c.startswith("open") for c in self.calls()), "headless means Simulator.app is never opened")
        self.assertEqual(list((self.tmp / "sims").glob(f"{A}*")), [], "marker and lease removed")

    def test_command_failure_still_shuts_down_and_keeps_its_exit_code(self):
        result = self.session("--device", A, "--", "sh", "-c", "exit 3")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(self.device_state(A), "Shutdown")

    def test_sigterm_still_shuts_down(self):
        release = self.tmp / "never"
        holder = self.start_holder(A, release)
        holder.send_signal(signal.SIGTERM)
        holder.communicate(timeout=15)
        self.assertEqual(self.device_state(A), "Shutdown")

    def test_never_shuts_down_a_device_it_did_not_boot(self):
        self.write_state({A: "Booted", B: "Shutdown"}, gui=True)
        result = self.session("--device", A, "--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertNotIn(f"xcrun simctl shutdown {A}", self.calls())
        self.assertNotIn(f"xcrun simctl boot {A}", self.calls())
        self.assertTrue(self.gui(), "a device is still booted, so Simulator.app stays")

    def test_shared_device_is_shut_down_by_the_last_holder_only(self):
        release = self.tmp / "release"
        holder = self.start_holder(A, release)
        reuse = self.session("--device", A, "--", "true")
        self.assertEqual(reuse.returncode, 0, reuse.stderr)
        self.assertEqual(self.device_state(A), "Booted", "the first holder is still using it")
        release.touch()
        holder.communicate(timeout=15)
        self.assertEqual(self.device_state(A), "Shutdown")

    def test_quits_simulator_app_only_when_nothing_is_booted(self):
        self.write_state({A: "Shutdown", B: "Booted"}, gui=True)
        self.session("--device", A, "--", "true")
        self.assertFalse(any(c.startswith("osascript") for c in self.calls()))
        self.assertTrue(self.gui())
        self.write_state({A: "Shutdown", B: "Shutdown"}, gui=True)
        self.session("--device", A, "--", "true")
        self.assertIn('osascript -e quit app "Simulator"', self.calls())
        self.assertFalse(self.gui())

    def test_leaves_a_device_a_running_xcodebuild_still_uses(self):
        build, release = self.start_build("-destination", f"id={A}")
        result = self.session("--device", A, "--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted", "an xcodebuild outside the wrapper still runs on it")
        self.assertTrue((self.tmp / "sims" / f"{A}.json").exists(), "the marker stays so the reaper closes it later")
        release.touch()
        build.wait(timeout=10)
        self.reap()
        self.assertEqual(self.device_state(A), "Shutdown")

    def test_unknown_device_is_a_usage_error(self):
        result = self.session("--device", "No Such Phone", "--", "true")
        self.assertEqual(result.returncode, 2)
        self.assertIn("No Such Phone", result.stderr)


class Reaper(SimFixture):
    def test_skips_a_device_whose_owner_is_alive(self):
        release = self.tmp / "release"
        holder = self.start_holder(A, release)
        result = self.reap("--grace-minutes", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted")
        release.touch()
        holder.communicate(timeout=15)

    def test_reaps_a_device_whose_owner_died(self):
        # The command SIGKILLs its wrapper, so no trap runs and the marker stays.
        result = self.session("--device", A, "--", "sh", "-c", "kill -9 $PPID")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.device_state(A), "Booted", "precondition: a leaked device")
        reaped = self.reap()
        self.assertEqual(reaped.returncode, 0, reaped.stderr)
        self.assertEqual(self.device_state(A), "Shutdown")
        self.assertIn(A, reaped.stdout)
        self.assertEqual(list((self.tmp / "sims").glob(f"{A}*")), [])

    def test_skips_a_device_a_running_xcodebuild_references(self):
        self.write_state({A: "Booted", B: "Shutdown"})
        self.mark_dead_owner(A)
        build, release = self.start_build("-destination", f"id={A}")
        self.reap()
        self.assertEqual(self.device_state(A), "Booted")
        release.touch()
        build.wait(timeout=10)

    def test_never_shuts_down_an_unmarked_device_by_default(self):
        # No marker means no wrapper booted it: an agent may drive it by name or
        # by separate simctl calls the reaper cannot see between calls.
        self.write_state({A: "Booted", B: "Shutdown"}, booted_at=OLD)
        result = self.reap("--grace-minutes", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertIn(f"kept {A} (iPhone 17) reason=unowned", result.stdout)

    def test_include_unowned_reaps_only_past_the_grace_period(self):
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.write_state({A: "Booted", B: "Shutdown"}, booted_at=now)
        self.reap("--include-unowned", "--grace-minutes", "30")
        self.assertEqual(self.device_state(A), "Booted", "inside the grace period")
        self.write_state({A: "Booted", B: "Shutdown"}, booted_at=OLD)
        self.reap("--include-unowned", "--grace-minutes", "30")
        self.assertEqual(self.device_state(A), "Shutdown")

    def test_include_unowned_skips_a_device_an_xcodebuild_picks_by_name(self):
        self.write_state({A: "Booted", B: "Shutdown"}, booted_at=OLD)
        build, release = self.start_build("-destination", "platform=iOS Simulator,name=iPhone 17")
        self.reap("--include-unowned", "--grace-minutes", "0")
        self.assertEqual(self.device_state(A), "Booted")
        release.touch()
        build.wait(timeout=10)

    def test_keeps_a_live_wrappers_claim_while_its_device_reboots(self):
        release = self.tmp / "release"
        holder = self.start_holder(A, release)
        self.write_state({A: "Shutdown", B: "Shutdown"})  # mid `simctl shutdown; simctl boot`
        self.reap()
        self.write_state({A: "Booted", B: "Shutdown"})
        release.touch()
        holder.communicate(timeout=15)
        self.assertEqual(self.device_state(A), "Shutdown", "the wrapper still closed what it booted")

    def test_dry_run_changes_nothing(self):
        self.write_state({A: "Booted", B: "Shutdown"}, gui=True)
        self.mark_dead_owner(A)
        result = self.reap("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"would shut down {A}", result.stdout)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertFalse(any("shutdown" in c or c.startswith("osascript") for c in self.calls()))

    def test_quits_simulator_app_only_when_nothing_is_booted(self):
        release = self.tmp / "release"
        holder = self.start_holder(A, release)
        self.write_state({A: "Booted", B: "Shutdown"}, gui=True, booted_at=OLD)
        self.reap()
        self.assertTrue(self.gui(), "A is still owned and booted")
        release.touch()
        holder.communicate(timeout=15)
        self.write_state({A: "Shutdown", B: "Shutdown"}, gui=True)
        self.reap()
        self.assertFalse(self.gui())


if __name__ == "__main__":
    unittest.main(verbosity=2)
