"""A marker and its leases bind to one boot of the device (F5).

The marker records the device's lastBootedAt at boot. Once the device boots
again outside the wrapper (the owner's `simctl shutdown all` then Xcode, a Mac
reboot), that boot is not the wrappers': release and the reaper leave it
running and clean the stale marker and leases up. SYNTHETIC fixture throughout.
"""

import json
import unittest

from sim_fixture import A, B, NAMES, SimFixture

NEW_BOOT = "2026-10-06T10:00:00Z"


class BootBinding(SimFixture):
    def test_marker_records_the_boot_it_made(self):
        self.acquire("--device", A)
        marker = json.loads((self.tmp / "sims" / f"{A}.json").read_text())
        self.assertEqual(marker["booted_at"], self.device(A)["lastBootedAt"])

    def test_reaper_keeps_a_device_rebooted_after_an_external_shutdown(self):
        self.at(0)
        self.acquire("--device", A)  # never released
        self.write_state({A: "Shutdown", B: "Shutdown"})  # `xcrun simctl shutdown all`
        self.write_state({A: "Booted", B: "Shutdown"}, booted_at=NEW_BOOT)  # booted again outside the wrapper
        self.at(16)
        result = self.reap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertIn(f"kept {A} ({NAMES[A]}) reason=unmarked", result.stdout)
        self.assertNotIn(f"xcrun simctl shutdown {A}", self.calls())
        self.assertEqual([f for f in self.files() if f.startswith(A)], [], "stale marker and lease are tidied")

    def test_reaper_keeps_a_killed_one_shots_device_once_it_is_booted_again(self):
        self.session("--device", A, "--", "sh", "-c", "kill -9 $PPID")
        self.write_state({A: "Shutdown", B: "Shutdown"})  # the Mac rebooted
        self.write_state({A: "Booted", B: "Shutdown"}, booted_at=NEW_BOOT)
        result = self.reap()
        self.assertEqual(self.device_state(A), "Booted")
        self.assertIn("reason=unmarked", result.stdout)

    def test_release_leaves_a_device_someone_else_booted_again(self):
        _, lease = self.acquire("--device", A)
        self.set_device(A, lastBootedAt=NEW_BOOT)  # shut down and booted again outside the wrapper
        result = self.session("release", "--lease", lease)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertNotIn(f"xcrun simctl shutdown {A}", self.calls())
        self.assertEqual([f for f in self.files() if f.startswith(A)], [], "stale marker removed")

    def test_a_reboot_inside_the_wrappers_own_step_stays_the_wrappers(self):
        # The step itself reboots the device (capture.sh does `simctl shutdown; simctl boot`).
        reboot = f"xcrun simctl shutdown {A} && xcrun simctl boot {A}"
        _, lease = self.acquire("--device", A)
        self.set_device(A, lastBootedAt="2026-10-06T09:00:00Z")  # so the step's boot stamps a different time
        before = json.loads((self.tmp / "sims" / f"{A}.json").read_text())
        before["booted_at"] = "2026-10-06T09:00:00Z"
        (self.tmp / "sims" / f"{A}.json").write_text(json.dumps(before))
        step = self.session("run", "--lease", lease, "--", "sh", "-c", reboot)
        self.assertEqual(step.returncode, 0, step.stderr)
        self.session("release", "--lease", lease)
        self.assertEqual(self.device_state(A), "Shutdown", "the wrapper still closed what it booted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
