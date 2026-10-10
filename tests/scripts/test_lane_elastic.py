"""lane-run.sh elastic slots: extra slots only while the host has headroom (AC-LN-EL-01..06).

Slot selection is tested in-process against a throwaway GRAPH_LANES_DIR, with the
host probes injected, so no case depends on this machine's real load. A second
open file description is a second flock holder even inside one process, which is
how a slot is "held by someone else" here. Probe outputs are SYNTHETIC fixtures.
"""

import fcntl
import os
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

GB = 10**9
MEMINFO = "MemTotal:       16000000 kB\nMemFree:          500000 kB\nMemAvailable:    6000000 kB\n"


def roomy():
    return True, "load 0.10 per core, 8.0 GB free"


def tight():
    return False, "load 0.95 per core above 0.70"


class Slots(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name) / "lanes"
        patcher = mock.patch.dict(os.environ, {"GRAPH_LANES_DIR": str(self.dir)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def hold(self, slot, lane="t"):
        self.dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.dir / f"{lane}.{slot}.lock", os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(os.close, fd)

    def acquire(self, **kwargs):
        held = lane_run.acquire("t", wait_seconds=0, **{"slots": 1, **kwargs})
        if held is not None:
            self.addCleanup(os.close, held[0])
        return held

    def test_elastic_slot_is_taken_when_the_host_has_headroom_ac_ln_el_01(self):
        self.hold(1)
        held = self.acquire(elastic=1, headroom=roomy)
        self.assertIsNotNone(held)
        self.assertEqual(held[1], 2)
        self.assertEqual(held[3], "load 0.10 per core, 8.0 GB free")

    def test_no_elastic_slot_while_the_host_is_loaded_ac_ln_el_02(self):
        self.hold(1)
        self.assertIsNone(self.acquire(elastic=2, headroom=tight))
        self.assertFalse((self.dir / "t.2.lock").exists(), "a refused elastic slot is never opened")

    def test_declared_slots_are_used_before_probing_ac_ln_el_03(self):
        probe = mock.Mock(side_effect=roomy)
        held = self.acquire(elastic=1, headroom=probe)
        self.assertEqual((held[1], held[3]), (1, None))
        probe.assert_not_called()

    def test_without_elastic_the_lane_never_probes_or_grows_ac_ln_el_03(self):
        self.hold(1)
        probe = mock.Mock(side_effect=roomy)
        self.assertIsNone(self.acquire(headroom=probe))
        probe.assert_not_called()

    def test_elastic_slots_are_capped_ac_ln_el_01(self):
        self.hold(1)
        self.hold(2)
        self.assertIsNone(self.acquire(elastic=1, headroom=roomy))


class Headroom(unittest.TestCase):
    def check(self, load, free, max_load=0.7, min_free=4 * GB):
        return lane_host.headroom(max_load, min_free, load=lambda: load, free=lambda: free)

    def test_granted_below_the_load_ceiling_and_above_the_memory_floor_ac_ln_el_04(self):
        ok, note = self.check(0.5, 8 * GB)
        self.assertTrue(ok)
        self.assertEqual(note, "load 0.50 per core, 8.0 GB free")

    def test_refused_at_or_above_the_load_ceiling_ac_ln_el_04(self):
        self.assertFalse(self.check(0.7, 8 * GB)[0])
        self.assertFalse(self.check(1.2, 8 * GB)[0])

    def test_refused_below_the_memory_floor_ac_ln_el_04(self):
        self.assertFalse(self.check(0.1, 4 * GB - 1)[0])
        self.assertTrue(self.check(0.1, 4 * GB)[0])

    def test_unreadable_load_or_memory_refuses_the_extra_slot_ac_ln_el_05(self):
        ok, note = self.check(None, 8 * GB)
        self.assertEqual((ok, note), (False, "load unreadable"))
        ok, note = self.check(0.1, None)
        self.assertEqual((ok, note), (False, "free memory unreadable"))

    def test_load_is_per_core_ac_ln_el_04(self):
        with mock.patch.object(os, "getloadavg", return_value=(3.0, 1.0, 1.0)), \
                mock.patch.object(os, "cpu_count", return_value=4):
            self.assertEqual(lane_host.load_per_core(), 0.75)

    def test_load_probe_failures_read_as_none_ac_ln_el_05(self):
        with mock.patch.object(os, "getloadavg", side_effect=OSError):
            self.assertIsNone(lane_host.load_per_core())
        with mock.patch.object(os, "getloadavg", return_value=(1.0, 1.0, 1.0)), \
                mock.patch.object(os, "cpu_count", return_value=None):
            self.assertIsNone(lane_host.load_per_core())

    def test_linux_meminfo_reads_mem_available(self):
        self.assertEqual(lane_host.parse_meminfo(MEMINFO), 6000000 * 1024)
        self.assertIsNone(lane_host.parse_meminfo("MemTotal: 1 kB\n"))

    def test_darwin_reads_the_kernel_free_percentage(self):
        self.assertEqual(lane_host.parse_darwin("73\n34359738368\n"), 34359738368 * 73 // 100)
        for text in ("", "x\n1\n", "73\n", "101\n100\n"):
            with self.subTest(text=text):
                self.assertIsNone(lane_host.parse_darwin(text))

    def test_memory_probe_failure_reads_as_none_ac_ln_el_05(self):
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(subprocess, "run", side_effect=OSError):
            self.assertIsNone(lane_host.available_bytes())
        with mock.patch.object(sys, "platform", "sunos5"):
            self.assertIsNone(lane_host.available_bytes())


class Cli(unittest.TestCase):
    def test_elastic_flags_parse_and_default_off_ac_ln_el_06(self):
        args, _ = lane_run.parse(["t", "--", "true"])
        self.assertEqual((args.elastic, args.max_load, args.min_free_gb), (0, 0.7, 2.0))
        args, _ = lane_run.parse(["t", "--slots", "2", "--elastic", "2", "--max-load", "0.5",
                                  "--min-free-gb", "8", "--", "true"])
        self.assertEqual((args.slots, args.elastic, args.max_load, args.min_free_gb), (2, 2, 0.5, 8.0))

    def test_bad_elastic_flags_exit_2_ac_ln_el_06(self):
        for argv in (["--elastic", "-1"], ["--elastic", "x"], ["--max-load", "0"], ["--max-load", "nan"],
                     ["--min-free-gb", "-1"], ["--slots", "60", "--elastic", "5"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised, \
                    mock.patch.object(sys, "stderr"):
                lane_run.parse(["t", *argv, "--", "true"])
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
