"""The three safety invariants of the simulator wrappers (findings F7, F8). SYNTHETIC fixture.

1. Nothing ever shuts down a device whose name does not start with graph-sim-.
   --allow-foreign runs steps on one, but writes no marker for it and never
   shuts it down, whoever booted it.
2. A graph-sim device is the wrappers' to close only for the boot a wrapper made
   itself (lastBootedAt recorded right after its own `simctl boot`). A boot
   anyone else made, a step's own reboot included, is never adopted: it is
   logged and left running.
3. `run --lease` on an expired or released lease exits 2 without renewing it,
   and acquire never hands out a device that holds an unreleased lease; it
   releases one only when no holder runs and the idle window has passed.
"""

import json
import unittest

from sim_fixture import A, B, O, SimFixture

OUTSIDE_BOOT = "2026-10-06T10:00:00Z"


class ForeignDevices(SimFixture):
    def shutdowns(self, udid):
        return [c for c in self.calls() if c == f"xcrun simctl shutdown {udid}"]

    def test_one_shot_with_allow_foreign_runs_but_never_marks_or_shuts_down(self):
        result = self.session("--device", O, "--allow-foreign", "--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(O), "Booted", "a foreign device is left running")
        self.assertEqual(self.shutdowns(O), [])
        self.assertNotIn(f"{O}.json", self.files(), "no owned marker for a foreign device")

    def test_leased_steps_with_allow_foreign_never_shut_down(self):
        self.write_state({A: "Shutdown", B: "Shutdown", O: "Booted"}, booted_at=OUTSIDE_BOOT)
        _, lease = self.acquire("--device", O, "--allow-foreign")
        step = self.session("run", "--lease", lease, "--", "true")
        self.assertEqual(step.returncode, 0, step.stderr)
        self.session("release", "--lease", lease)
        self.assertEqual(self.device_state(O), "Booted")
        self.assertEqual(self.shutdowns(O), [])

    def test_a_marker_left_on_a_foreign_device_never_shuts_it_down(self):
        # A marker that even matches the current boot (an older wrapper wrote it).
        self.write_state({A: "Shutdown", B: "Shutdown", O: "Booted"}, booted_at=OUTSIDE_BOOT)
        _, lease = self.acquire("--device", O, "--allow-foreign")
        (self.tmp / "sims" / f"{O}.json").write_text(json.dumps({"udid": O, "booted_at": OUTSIDE_BOOT}))
        self.session("release", "--lease", lease)
        self.at(500)
        self.reap()
        self.assertEqual(self.device_state(O), "Booted")
        self.assertEqual(self.shutdowns(O), [])


class BootOwnership(SimFixture):
    def test_one_shot_on_an_outside_boot_with_a_stale_marker_leaves_it_running(self):
        # F7: a leaked one-shot left marker T1; the owner booted A again (T2); a later one-shot uses A.
        self.session("--device", A, "--", "sh", "-c", "kill -9 $PPID")
        self.write_state({A: "Booted"}, booted_at=OUTSIDE_BOOT)
        result = self.session("--device", A, "--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.device_state(A), "Booted")
        self.assertNotIn(f"xcrun simctl shutdown {A}", self.calls())
        self.assertIn("booted outside", result.stderr, "the wrapper says why it leaves the device running")

    def test_a_reboot_inside_a_step_is_never_adopted(self):
        _, lease = self.acquire("--device", A)
        self.set_device(A, lastBootedAt="2026-10-06T09:00:00Z")  # the step's boot then stamps a later time
        marker = self.tmp / "sims" / f"{A}.json"
        marker.write_text(json.dumps(dict(json.loads(marker.read_text()), booted_at="2026-10-06T09:00:00Z")))
        reboot = f"xcrun simctl shutdown {A} && xcrun simctl boot {A}"
        step = self.session("run", "--lease", lease, "--", "sh", "-c", reboot)
        self.assertEqual(step.returncode, 0, step.stderr)
        self.assertEqual(json.loads(marker.read_text())["booted_at"], "2026-10-06T09:00:00Z", "never rebound")
        self.session("release", "--lease", lease)
        self.assertEqual(self.device_state(A), "Booted", "a boot the wrapper did not make is left running")


class ExpiredLeases(SimFixture):
    def test_run_on_an_expired_lease_exits_2_and_does_not_renew(self):
        self.at(0)
        _, lease = self.acquire("--device", A)
        before = {f: (self.tmp / "sims" / f).read_text() for f in self.files() if f.endswith(".lease")}
        self.at(16)
        ran = self.tmp / "ran"
        result = self.session("run", "--lease", lease, "--", "touch", str(ran))
        self.assertEqual(result.returncode, 2)
        self.assertIn("lease expired, acquire again", result.stderr)
        self.assertFalse(ran.exists(), "the step never ran")
        after = {f: (self.tmp / "sims" / f).read_text() for f in self.files() if f.endswith(".lease")}
        self.assertEqual(after, before, "not renewed")

    def test_a_second_agent_never_shares_a_device_with_a_lease_holder(self):
        self.at(0)
        first, lease = self.acquire()
        self.at(16)
        second, _ = self.acquire()
        step = self.session("run", "--lease", lease, "--", "true")
        self.assertFalse(first == second and step.returncode == 0, "two agents share one graph-sim device")
        self.assertEqual(step.returncode, 2)

    def test_acquire_skips_a_dead_one_shots_device_inside_the_idle_window(self):
        self.at(0)
        self.session("--device", A, "--", "sh", "-c", "kill -9 $PPID")
        udid, _ = self.acquire()
        self.assertNotEqual(udid, A, "the dead holder's lease is not released before the window passes")
        self.at(16)
        udid, _ = self.acquire()
        self.assertEqual(udid, A, "past the window with no holder running, acquire releases it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
