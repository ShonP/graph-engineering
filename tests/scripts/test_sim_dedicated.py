"""The wrappers use dedicated `graph-sim-*` devices, never the owner's (F6).

By default sim-session.sh reuses an idle graph-sim device on the newest iOS
runtime, or creates one (newest iPhone type). A device with any other name is
used only when --device names it AND --allow-foreign is passed, and nothing
ever shuts it down (test_sim_invariants.py). Idle graph-sim devices last
booted over 7 days ago are deleted. SYNTHETIC fixture throughout.
"""

import json
import unittest

from sim_fixture import A, B, NAMES, O, OLD, PRO, RUNTIME, SimFixture


class Dedicated(SimFixture):
    def created(self):
        return [c for c in self.calls() if c.startswith("xcrun simctl create")]

    def test_default_reuses_an_idle_dedicated_device(self):
        udid, _ = self.acquire()
        self.assertEqual(udid, A)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.device_state(O), "Shutdown", "the owner's device is never booted")

    def test_default_creates_a_dedicated_device_when_every_one_is_leased(self):
        self.acquire()
        self.acquire()
        udid, _ = self.acquire()
        self.assertNotIn(udid, (A, B, O))
        self.assertEqual(self.created(), [f"xcrun simctl create graph-sim-iOS-26-5-3 {PRO} {RUNTIME}"])
        self.assertEqual(self.device(udid)["name"], "graph-sim-iOS-26-5-3")
        self.assertEqual(self.device_state(udid), "Booted")

    def test_default_creates_the_first_dedicated_device_on_a_fresh_host(self):
        state = json.loads(self.state.read_text())
        state["devices"][RUNTIME] = [d for d in state["devices"][RUNTIME] if d["udid"] == O]
        self.state.write_text(json.dumps(state))
        udid, lease = self.acquire()
        self.assertEqual(self.created(), [f"xcrun simctl create graph-sim-iOS-26-5-1 {PRO} {RUNTIME}"])
        self.session("release", "--lease", lease)
        self.assertEqual(self.device_state(udid), "Shutdown")
        self.assertEqual(self.device_state(O), "Shutdown")

    def test_the_owners_booted_device_is_never_used_or_shut_down(self):
        # The owner's Xcode runs on O. Agents acquire, step and release; the reaper runs a year later.
        self.write_state({A: "Shutdown", B: "Shutdown", O: "Booted"}, gui=True)
        udid, lease = self.acquire()
        self.assertEqual(udid, A)
        self.session("release", "--lease", lease)
        self.at(60 * 24 * 365)
        result = self.reap("--idle-minutes", "0")
        self.assertEqual(self.device_state(O), "Booted")
        self.assertIn(f"kept {O} ({NAMES[O]}) reason=foreign", result.stdout)
        self.assertFalse(any(O in c for c in self.calls() if "shutdown" in c or "boot" in c))

    def test_naming_a_dedicated_device_needs_no_flag(self):
        udid, _ = self.acquire("--device", NAMES[B])
        self.assertEqual(udid, B)

    def test_a_foreign_device_is_refused_without_allow_foreign(self):
        result = self.session("--device", NAMES[O], "--", "true")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--allow-foreign", result.stderr)
        self.assertFalse(any(c.startswith("xcrun simctl boot") for c in self.calls()))

    def test_reaper_never_touches_a_foreign_device_even_one_the_wrapper_booted(self):
        self.session("--device", O, "--allow-foreign", "--", "sh", "-c", "kill -9 $PPID")
        self.assertEqual(self.device_state(O), "Booted", "precondition: a leaked foreign device")
        result = self.reap()
        self.assertEqual(self.device_state(O), "Booted")
        self.assertIn(f"kept {O} ({NAMES[O]}) reason=foreign", result.stdout)

    def test_reaper_deletes_idle_dedicated_devices_last_booted_over_seven_days_ago(self):
        self.set_device(A, lastBootedAt=OLD)  # Shutdown, months idle
        self.set_device(O, lastBootedAt=OLD)  # the owner's: never deleted
        self.at(0)
        dry = self.reap("--dry-run")
        self.assertIn(f"would delete {A}", dry.stdout)
        self.assertIsNotNone(self.device(A))
        result = self.reap()
        self.assertIn(f"deleted {A} ({NAMES[A]})", result.stdout)
        self.assertIsNone(self.device(A))
        self.assertIsNotNone(self.device(B), "never booted: no age to judge")
        self.assertIsNotNone(self.device(O))

    def test_reaper_keeps_a_dedicated_device_booted_within_seven_days(self):
        self.set_device(A, lastBootedAt="2026-09-20T00:00:00Z")  # one day before the clock
        self.at(0)
        self.reap()
        self.assertIsNotNone(self.device(A))


if __name__ == "__main__":
    unittest.main(verbosity=2)
