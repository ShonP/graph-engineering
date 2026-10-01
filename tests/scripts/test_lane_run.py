"""lane-run.sh: host lanes held by an inherited fcntl lock (AC-W3-LN-01..03).

Every case runs the public wrapper against a throwaway GRAPH_LANES_DIR. The
jobs are SYNTHETIC marker jobs: a Python one-liner that touches `<name>.started`,
sleeps, then writes `<start> <end>` epoch seconds to `<name>`, so ordering is
read from the jobs' own clocks rather than from the harness.
"""

import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

LANE_RUN = Path(__file__).resolve().parents[2] / "scripts" / "lane-run.sh"
ACQUIRED = re.compile(r"^lane t slot (\d+) acquired after (\d+) s$", re.M)
JOB = ("import sys, time; path = sys.argv[1]; start = time.time(); open(path + '.started', 'w').close(); "
       "time.sleep(float(sys.argv[2])); open(path, 'w').write(f'{start} {time.time()}')")


class Lanes(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.env = dict(os.environ, GRAPH_LANES_DIR=str(self.tmp / "lanes"))

    def start(self, *args, session=False, env=None):
        process = subprocess.Popen(["bash", str(LANE_RUN), *args], env=env or self.env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=session)
        self.addCleanup(self.reap, process, session)
        return process

    @staticmethod
    def reap(process, session):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL) if session else process.kill()
        process.communicate()

    def run_lane(self, *args, env=None):
        process = self.start(*args, env=env)
        out, err = process.communicate(timeout=30)
        return process.returncode, out, err

    def job(self, name, seconds):
        return [sys.executable, "-c", JOB, str(self.tmp / name), str(seconds)]

    def wait_started(self, name, timeout=10):
        deadline = time.monotonic() + timeout
        while not (self.tmp / f"{name}.started").exists():
            self.assertLess(time.monotonic(), deadline, f"job {name} never started")
            time.sleep(0.05)

    def times(self, name):
        start, end = (self.tmp / name).read_text().split()
        return float(start), float(end)


class Serializes(Lanes):
    def test_second_job_starts_after_the_first_ends_ac_w3_ln_01(self):
        first = self.start("t", "--slots", "1", "--", *self.job("a", 5))
        self.wait_started("a")
        second = self.start("t", "--slots", "1", "--", *self.job("b", 5))
        _, first_err = first.communicate(timeout=30)
        _, second_err = second.communicate(timeout=30)
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        self.assertGreaterEqual(self.times("b")[0], self.times("a")[1])
        self.assertEqual(ACQUIRED.findall(first_err), [("1", "0")])
        (slot, waited), = ACQUIRED.findall(second_err)
        self.assertEqual(slot, "1")
        self.assertGreaterEqual(int(waited), 3)

    def test_killed_holder_releases_the_lane_within_two_seconds_ac_w3_ln_02(self):
        # The holder forks its job as a child, as a real agent command does; a killed
        # agent loses its whole process group, so the kill goes to the group.
        holder = self.start("t", "--slots", "1", "--", "sh", "-c", '"$@"; echo after', "sh",
                            *self.job("a", 60), session=True)
        self.wait_started("a")
        waiter = self.start("t", "--slots", "1", "--wait-seconds", "30", "--", *self.job("b", 0))
        time.sleep(1.5)
        self.assertIsNone(waiter.poll(), "the waiter must be blocked while the holder runs")
        killed_at = time.time()
        os.killpg(holder.pid, signal.SIGKILL)
        holder.communicate(timeout=10)
        _, err = waiter.communicate(timeout=10)
        self.assertEqual(waiter.returncode, 0)
        self.assertLess(self.times("b")[0] - killed_at, 2.0)
        self.assertEqual(len(ACQUIRED.findall(err)), 1)


class Slots(Lanes):
    def test_two_slots_overlap_and_a_third_job_waits_ac_w3_ln_03(self):
        first = self.start("t", "--slots", "2", "--", *self.job("a", 3))
        self.wait_started("a")
        second = self.start("t", "--slots", "2", "--", *self.job("b", 3))
        self.wait_started("b")
        third = self.start("t", "--slots", "2", "--", *self.job("c", 0))
        errors = [process.communicate(timeout=30)[1] for process in (first, second, third)]
        self.assertEqual([process.returncode for process in (first, second, third)], [0, 0, 0])
        (a_start, a_end), (b_start, b_end), (c_start, _) = self.times("a"), self.times("b"), self.times("c")
        self.assertLess(b_start, a_end, "two slots must let two jobs overlap")
        self.assertGreaterEqual(c_start, min(a_end, b_end), "the third job must wait for a free slot")
        self.assertEqual([ACQUIRED.findall(err)[0][0] for err in errors[:2]], ["1", "2"])

    def test_busy_lane_exits_75_after_the_wait_ac_w3_ln_03(self):
        holder = self.start("t", "--slots", "1", "--", *self.job("a", 10))
        self.wait_started("a")
        started = time.monotonic()
        code, _, err = self.run_lane("t", "--slots", "1", "--wait-seconds", "1", "--", *self.job("b", 0))
        self.assertEqual(code, 75)
        self.assertEqual(err.strip(), "lane t busy after 1 s")
        self.assertLess(time.monotonic() - started, 5)
        self.assertFalse((self.tmp / "b.started").exists(), "a busy lane must not run the command")
        holder.kill()

    def test_invalid_lane_name_exits_2_ac_w3_ln_03(self):
        for name in ("Bad", "a/b", "..", "", "x y", "../escape"):
            with self.subTest(name=name):
                code, _, _ = self.run_lane(name, "--", *self.job("never", 0))
                self.assertEqual(code, 2)
                self.assertFalse((self.tmp / "never.started").exists())
        self.assertFalse((self.tmp / "escape.1.lock").exists())


class Contract(Lanes):
    def test_exit_code_and_stdout_are_the_commands(self):
        code, out, err = self.run_lane("build_1", "--", "sh", "-c", "echo out; exit 7")
        self.assertEqual((code, out), (7, "out\n"))
        self.assertEqual(err, "lane build_1 slot 1 acquired after 0 s\n")
        self.assertTrue((self.tmp / "lanes" / "build_1.1.lock").is_file())

    def test_missing_command_exits_127(self):
        code, _, err = self.run_lane("t", "--", "graph-engineering-no-such-command")
        self.assertEqual(code, 127)
        self.assertIn("graph-engineering-no-such-command", err)

    def test_usage_errors_exit_2(self):
        for args in (["t"], ["t", "--"], ["t", "--slots", "0", "--", "true"], ["t", "--slots", "x", "--", "true"],
                     ["t", "--wait-seconds", "-1", "--", "true"], ["t", "--bogus", "--", "true"]):
            with self.subTest(args=args):
                self.assertEqual(self.run_lane(*args)[0], 2)

    def test_lock_dir_falls_back_to_xdg_cache_home(self):
        env = {key: value for key, value in self.env.items() if key != "GRAPH_LANES_DIR"}
        env["XDG_CACHE_HOME"] = str(self.tmp / "xdg")
        self.assertEqual(self.run_lane("t", "--", "true", env=env)[0], 0)
        self.assertTrue((self.tmp / "xdg" / "graph-engineering" / "lanes" / "t.1.lock").is_file())


if __name__ == "__main__":
    unittest.main()
