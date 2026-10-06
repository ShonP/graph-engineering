"""Who holds a lease, read the same way from every session on the Mac.

The reaper runs from whichever session's Stop hook fires, so it must reach the
same verdict on a holder whatever that session's locale, timezone or idle
setting; and a lease shared by concurrent steps is held until the last one
ends. SYNTHETIC devices and simulated time (GRAPH_SIM_CLOCK), see sim_fixture.
"""

import unittest

from sim_fixture import A, B, NAMES, SimFixture

ELSEWHERE = ("LANG", "LC_ALL", "LC_TIME")


class Holders(SimFixture):
    def test_a_reaper_in_another_locale_and_timezone_keeps_live_holders(self):
        # F5: the holders start in a Hebrew, Jerusalem-time session ...
        for name in ELSEWHERE:
            self.env.pop(name, None)
        self.env.update(LANG="he_IL.UTF-8", LC_TIME="he_IL.UTF-8", TZ="Asia/Jerusalem")
        self.at(0)
        _, lease = self.acquire("--device", A)
        release = self.tmp / "release"
        oneshot = self.start_holder(B, release)
        step = self.start_holder(A, release, "run", "--lease", lease)
        # ... and the reaper fires from a desktop-app, launchd or cron session with no LANG, in UTC.
        for name in ELSEWHERE:
            self.env.pop(name, None)
        self.env["TZ"] = "UTC"
        self.at(20)
        result = self.reap()
        self.assertEqual(self.device_state(B), "Booted", result.stdout)
        self.assertEqual(self.device_state(A), "Booted", result.stdout)
        self.assertIn(f"kept {B} ({NAMES[B]}) reason=leased", result.stdout)
        self.assertIn(f"kept {A} ({NAMES[A]}) reason=leased", result.stdout)
        release.touch()
        oneshot.communicate(timeout=15)
        step.communicate(timeout=15)

    def test_the_idle_window_set_at_acquire_binds_the_reaper(self):
        # F7: the reaper's own session never set GRAPH_SIM_IDLE_MIN.
        self.at(0)
        self.env["GRAPH_SIM_IDLE_MIN"] = "60"
        self.acquire("--device", A)
        self.env.pop("GRAPH_SIM_IDLE_MIN")
        self.at(30)
        self.reap()
        self.assertEqual(self.device_state(A), "Booted", "acquired with a 60-minute window")
        self.at(61)
        result = self.reap()
        self.assertEqual(self.device_state(A), "Shutdown")
        self.assertIn(f"shut down {A} ({NAMES[A]}) reason=idle", result.stdout)

    def test_a_shorter_reaper_window_never_cuts_a_lease_short(self):
        self.at(0)
        self.acquire("--device", A)
        self.at(10)
        self.reap("--idle-minutes", "5")
        self.assertEqual(self.device_state(A), "Booted", "the lease was acquired with the default 15")

    def test_concurrent_steps_hold_the_lease_until_the_last_one_ends(self):
        # F7: two `run --lease` steps on one lease; the shorter ends first.
        self.at(0)
        _, lease = self.acquire("--device", A)
        short, long_ = self.tmp / "short", self.tmp / "long"
        first = self.start_holder(A, short, "run", "--lease", lease)
        second = self.start_holder(A, long_, "run", "--lease", lease)
        short.touch()
        first.communicate(timeout=15)
        self.at(20)
        result = self.reap()
        self.assertEqual(self.device_state(A), "Booted", result.stdout)
        self.assertIn("reason=leased", result.stdout)
        long_.touch()
        second.communicate(timeout=15)
        self.at(40)
        self.reap()
        self.assertEqual(self.device_state(A), "Shutdown", "both steps ended and the lease idled out")


if __name__ == "__main__":
    unittest.main(verbosity=2)
