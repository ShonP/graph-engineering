"""sim-session.sh acquire / run --lease / release: hold one simulator across many tool calls.

Multi-step qa captures, reads the PNG, then decides the next step, so one
device has to outlive each command. A lease names the device and records when
it was last used; the reaper shuts a wrapper-booted device down only when every
lease on it is released or idle past GRAPH_SIM_IDLE_MIN (default 15) and no
running xcodebuild/XCTest/simctl names it. Time is simulated (GRAPH_SIM_CLOCK).
"""

import unittest

from sim_fixture import A, B, SimFixture


class Lease(SimFixture):
    def test_acquire_boots_headless_and_prints_the_udid_and_a_lease(self):
        udid, lease = self.acquire("--device", "iPhone 17", "--label", "qa-notice")
        self.assertEqual(udid, A)
        self.assertRegex(lease, r"^[0-9a-f]{16}$")
        self.assertEqual(self.device_state(A), "Booted", "the device outlives the acquire call")
        self.assertFalse(any(c.startswith("open") for c in self.calls()), "headless")
        self.assertIn(f"{A}.json", self.files(), "a wrapper booted it, so it carries the marker")

    def test_run_exports_the_leased_udid_and_leaves_the_device_booted(self):
        _, lease = self.acquire("--device", A)
        out = self.tmp / "udid.txt"
        result = self.session("run", "--lease", lease, "--", "sh", "-c", f'printf %s "$SIM_UDID" > {out}; exit 4')
        self.assertEqual(result.returncode, 4, "the step's own exit code")
        self.assertEqual(out.read_text(), A)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertNotIn(f"xcrun simctl shutdown {A}", self.calls())

    def test_steps_20_minutes_apart_inside_the_idle_window_are_never_reaped(self):
        # F1: the device is far older than any boot-age grace, but every step renews the lease.
        self.env["GRAPH_SIM_IDLE_MIN"] = "30"
        self.at(0)
        _, lease = self.acquire("--device", A)
        for minute in (20, 40, 60, 80):
            self.at(minute - 1)
            self.reap()
            self.assertEqual(self.device_state(A), "Booted", f"reaped before the step at minute {minute}")
            self.at(minute)
            step = self.session("run", "--lease", lease, "--", "true")
            self.assertEqual(step.returncode, 0, step.stderr)
        self.at(80 + 29)
        self.reap()
        self.assertEqual(self.device_state(A), "Booted")

    def test_a_lease_idle_past_the_window_is_reaped(self):
        self.write_state({A: "Shutdown", B: "Shutdown"}, gui=True)
        self.at(0)
        _, lease = self.acquire("--device", A)
        self.at(14)
        self.reap()
        self.assertEqual(self.device_state(A), "Booted", "14 idle minutes is inside the default 15")
        self.at(16)
        result = self.reap()
        self.assertEqual(self.device_state(A), "Shutdown")
        self.assertIn(f"shut down {A} (iPhone 17) reason=idle", result.stdout)
        self.assertEqual(self.files(), [], "marker and lease removed")
        self.assertFalse(self.gui(), "nothing booted, so Simulator.app is quit")
        late = self.session("run", "--lease", lease, "--", "true")
        self.assertEqual(late.returncode, 2, "a reaped lease is gone; acquire again")
        self.assertIn("acquire", late.stderr)

    def test_a_running_step_holds_the_device_past_the_window(self):
        self.at(0)
        _, lease = self.acquire("--device", A)
        release = self.tmp / "release"
        step = self.start_holder(A, release, "run", "--lease", lease)
        self.at(600)
        self.reap()
        self.assertEqual(self.device_state(A), "Booted", "a long xcodebuild step is still running")
        release.touch()
        step.communicate(timeout=15)

    def test_release_with_two_leases_keeps_the_device_for_the_other(self):
        self.write_state({A: "Shutdown", B: "Shutdown"}, gui=True)
        _, first = self.acquire("--device", A)
        _, second = self.acquire("--device", A)
        self.assertNotEqual(first, second)
        self.assertEqual(self.session("release", "--lease", first).returncode, 0)
        self.assertEqual(self.device_state(A), "Booted", "the second lease still holds it")
        self.assertEqual(self.session("release", "--lease", second).returncode, 0)
        self.assertEqual(self.device_state(A), "Shutdown")
        self.assertEqual(self.files(), [])
        self.assertFalse(self.gui())

    def test_release_never_shuts_down_a_device_it_did_not_boot(self):
        self.write_state({A: "Booted", B: "Shutdown"}, gui=True)
        _, lease = self.acquire("--device", A)
        self.assertEqual(self.session("release", "--lease", lease).returncode, 0)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertNotIn(f"xcrun simctl boot {A}", self.calls())
        self.assertTrue(self.gui())

    def test_release_twice_is_harmless(self):
        _, lease = self.acquire("--device", A)
        self.assertEqual(self.session("release", "--lease", lease).returncode, 0)
        again = self.session("release", "--lease", lease)
        self.assertEqual(again.returncode, 0, again.stderr)

    def test_a_malformed_lease_id_is_a_usage_error(self):
        # A real lease exists, so a wildcard or traversal id that reached the glob would match it.
        self.acquire("--device", A)
        for bad in ("*", "?" * 16, "../*", ""):
            with self.subTest(bad):
                result = self.session("run", "--lease", bad, "--", "true")
                self.assertEqual(result.returncode, 2)
                self.assertIn("16 hex", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
