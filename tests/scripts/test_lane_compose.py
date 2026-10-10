"""lane-run.sh: --max-load5 and --elastic compose into one admission (AC-LN-COMPOSE-01..05).

`--max-load5` gates every slot, declared or elastic, before and after it is taken;
`--elastic` decides only whether the lane may grow past its declared slots. Load
series, clocks and headroom readings are SYNTHETIC fixtures injected in-process,
so no case depends on this machine's real load.
"""

import fcntl
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lane_host  # noqa: E402
import lane_run  # noqa: E402


def roomy():
    return True, "load 0.10 per core, 8.0 GB free"


def tight():
    return False, "load 0.95 per core at or above 0.70"


class Host:
    """A clock that moves only on sleep, a scripted load5 series (last value repeats), and a record
    of whether elastic slot 2 was free at each load5 read."""

    def __init__(self, directory, loads):
        self.directory, self.loads = directory, list(loads)
        self.now, self.free_at_read = 0.0, []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def load5(self):
        probe = lane_run.try_slot(self.directory / "t.2.lock")
        self.free_at_read.append(probe is not None)
        if probe is not None:
            os.close(probe)
        return self.loads.pop(0) if len(self.loads) > 1 else self.loads[0]


class Compose(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name) / "lanes"
        self.dir.mkdir()
        patcher = mock.patch.dict(os.environ, {"GRAPH_LANES_DIR": str(self.dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.hold(1)

    def hold(self, slot):
        fd = os.open(self.dir / f"t.{slot}.lock", os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(os.close, fd)

    def admit(self, loads, headroom=roomy, wait_seconds=60, max_load5=40):
        host = Host(self.dir, loads)
        try:
            fd, slot, waited = lane_run.admit("t", 1, wait_seconds, max_load5, load5=host.load5,
                                              clock=host.clock, sleep=host.sleep, elastic=1, headroom=headroom)
        except lane_run.Busy as busy:
            return host, str(busy)
        self.addCleanup(os.close, fd)
        return host, (slot, waited)

    def test_load5_gate_comes_before_an_elastic_slot_ac_ln_compose_01(self):
        host, (slot, waited) = self.admit([90, 70, 30, 30])
        self.assertEqual(slot, 2, "the declared slot is held, so the admitted slot is elastic")
        self.assertEqual(host.free_at_read[:3], [True, True, True], "a load5 wait never holds an elastic slot")
        self.assertGreater(waited, 0)

    def test_an_elastic_slot_is_given_back_when_load5_rises_after_taking_it_ac_ln_compose_02(self):
        host, (slot, _) = self.admit([30, 90, 90, 30, 30])
        self.assertEqual(slot, 2)
        self.assertEqual(host.free_at_read[1], False, "the post-acquire read happens while slot 2 is held")
        self.assertEqual(host.free_at_read[2], True, "slot 2 is released while load5 is over the cap")

    def test_quiet_load5_does_not_grant_an_elastic_slot_without_headroom_ac_ln_compose_03(self):
        host, message = self.admit([1], headroom=tight)
        self.assertEqual(message, "lane t busy after 60 s")
        self.assertLessEqual(host.now, 60)
        self.assertTrue(all(host.free_at_read))

    def test_unreadable_load5_skips_the_gate_not_the_headroom_ac_ln_compose_04(self):
        host, (slot, waited) = self.admit([None])
        self.assertEqual((slot, waited), (2, 0))
        host, message = self.admit([None], headroom=tight, wait_seconds=5)
        self.assertEqual(message, "lane t busy after 5 s")

    def test_load5_probe_failure_reads_as_none_ac_ln_compose_04(self):
        with mock.patch.object(os, "getloadavg", side_effect=OSError):
            self.assertIsNone(lane_host.load5())
        with mock.patch.object(os, "getloadavg", return_value=(1.0, 2.5, 3.0)):
            self.assertEqual(lane_host.load5(), 2.5)


class Cli(unittest.TestCase):
    def test_both_flags_on_one_call_take_an_elastic_slot_and_say_so_ac_ln_compose_05(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "lanes"
            directory.mkdir()
            fd = os.open(directory / "t.1.lock", os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                done = subprocess.run(
                    ["bash", str(SCRIPTS / "lane-run.sh"), "t", "--elastic", "1", "--max-load", "100000",
                     "--min-free-gb", "0", "--max-load5", "100000", "--wait-seconds", "0", "--", "true"],
                    env=dict(os.environ, GRAPH_LANES_DIR=str(directory)), capture_output=True, text=True, timeout=30)
            finally:
                os.close(fd)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stderr, re.compile(r"^lane t slot 2 acquired after 0 s \(elastic: load .+\)$", re.M))


if __name__ == "__main__":
    unittest.main()
