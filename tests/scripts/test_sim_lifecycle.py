"""sim-session.sh and sim-reaper.sh: close every simulator an agent opens.

Every case runs the public scripts with a SYNTHETIC xcrun/osascript/pgrep/open
(tests/scripts/fixtures/fake_xcrun.py) first on PATH and a throwaway
GRAPH_SIM_DIR, so no Xcode is needed and no real simulator is touched. The
devices are synthetic too: two iPhones on one fake iOS runtime.

The rule under test: a wrapper shuts down only a device a wrapper booted, and
only when no live wrapper still holds it; the reaper never touches a device a
live process owns; Simulator.app is quit only when nothing is booted.
"""

import signal
import subprocess
import sys
import unittest

from sim_fixture import A, B, NAMES, OLD, SESSION, SimFixture


class Session(SimFixture):
    def test_boots_headless_exports_udid_and_shuts_down_what_it_booted(self):
        out = self.tmp / "udid.txt"
        result = self.session("--device", NAMES[A], "--", "sh", "-c", f'printf %s "$SIM_UDID" > {out}')
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

    def test_shuts_down_when_the_launching_shell_names_the_device(self):
        # An agent's Bash-tool shell carries the udid and `simctl` on its own
        # command line and waits on the wrapper; it is not a separate user.
        script = f'bash {SESSION} --device {A} -- sh -c "true # xcrun simctl io {A} screenshot x.png"; true'
        result = subprocess.run(["bash", "-c", script], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Shutdown")
        self.assertEqual(list((self.tmp / "sims").glob(f"{A}*")), [])

    def test_unknown_device_is_a_usage_error(self):
        result = self.session("--device", "No Such Phone", "--", "true")
        self.assertEqual(result.returncode, 2)
        self.assertIn("No Such Phone", result.stderr)


class Reaper(SimFixture):
    def test_skips_a_device_whose_owner_is_alive(self):
        release = self.tmp / "release"
        holder = self.start_holder(A, release)
        self.at(60 * 24)  # a one-shot run's lease never idles out while its process lives
        result = self.reap("--idle-minutes", "0")
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

    def test_skips_a_dead_owners_device_an_xcodebuild_picks_by_name(self):
        self.write_state({A: "Booted", B: "Shutdown"})
        self.mark_dead_owner(A)
        build, release = self.start_build("-destination", f"platform=iOS Simulator,name={NAMES[A]}")
        self.reap()
        self.assertEqual(self.device_state(A), "Booted", "another agent's test run is still on it")
        release.touch()
        build.wait(timeout=10)

    def test_never_shuts_down_an_unmarked_device_however_old(self):
        # Booted outside any wrapper: the owner's Xcode, XcodeBuildMCP. Nothing proves it abandoned.
        self.write_state({A: "Booted", B: "Shutdown"}, gui=True, booted_at=OLD)
        self.at(60 * 24 * 365)
        result = self.reap("--idle-minutes", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertIn(f"kept {A} ({NAMES[A]}) reason=unmarked", result.stdout)
        self.assertNotIn(f"xcrun simctl shutdown {A}", self.calls())
        self.assertTrue(self.gui(), "a device is booted, so Simulator.app stays")

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
        # A leaked one-shot run (dead holder) and an idle lease: both reapable, both left on disk.
        result = self.session("--device", A, "--", "sh", "-c", "kill -9 $PPID")
        self.assertNotEqual(result.returncode, 0)
        self.at(0)
        self.acquire("--device", A)
        self.at(60)
        before = self.files()
        self.assertEqual(len([f for f in before if f.endswith(".lease")]), 2, before)
        result = self.reap("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"would shut down {A}", result.stdout)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertEqual(self.files(), before, "dry-run deletes no marker and no lease")
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
