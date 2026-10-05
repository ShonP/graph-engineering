#!/usr/bin/env python3
"""wait-run.sh --full: a per-dispatch budget of full-suite runs (AC-WR-1, AC-WR-2).

Stdlib only. Run from any directory:

    python3 hooks/tests/test_wait_count.py

Drives hooks/scripts/wait-run.sh as an agent would, with a temp
GRAPH_WAIT_RUN_DIR so no real cache is touched. Every job is a synthetic
`python3 -c` one-liner; tearDown kills whatever a failed case left running.
"""

import fcntl
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent
SCRIPT = HOOKS / "scripts" / "wait-run.sh"
sys.path.insert(0, str(HOOKS / "scripts"))

import wait_count  # noqa: E402

RUN_ID = "x-t4"
OK = [sys.executable, "-c", "import sys; sys.exit(0)"]
SLEEP_2 = [sys.executable, "-c", "import time; time.sleep(2)"]
LINE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ full (\d+)( reason=.+)?$")


def refusal(n, run_id=RUN_ID):
    return f'wait-run: refused: full-suite run {n} for {run_id} needs --reason "<why>"'


class Base(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name).resolve()
        self.counts = self.work / "cache" / "wait-run"
        self.logs = []
        self.addCleanup(self.kill_jobs)

    def kill_jobs(self):
        for log in self.logs:
            try:
                os.killpg(int(Path(f"{log}.pid").read_text()), signal.SIGKILL)
            except (OSError, ValueError):
                pass

    def env(self, run_id=RUN_ID):
        env = {k: v for k, v in os.environ.items() if k != "GRAPH_RUN_ID"}
        env["GRAPH_WAIT_RUN_DIR"] = str(self.counts)
        if run_id is not None:
            env["GRAPH_RUN_ID"] = run_id
        return env

    def log(self, name="suite.log"):
        path = self.work / name
        self.logs.append(path)
        return path

    def wait_run(self, *args, log=None, run_id=RUN_ID, timeout=30):
        argv = ["bash", str(SCRIPT), "--log", str(log or self.log()), *args]
        return subprocess.run(argv, cwd=self.work, env=self.env(run_id), capture_output=True,
                              text=True, timeout=timeout, check=False)

    def counter(self, run_id=RUN_ID):
        return self.counts / f"{run_id}.full"

    def numbers(self, run_id=RUN_ID):
        path = self.counter(run_id)
        if not path.exists():
            return []
        found = []
        for line in path.read_text(encoding="utf-8").splitlines():
            match = LINE.match(line)
            self.assertIsNotNone(match, line)
            found.append(int(match.group(1)))
        return found


class Budget(Base):
    """AC-WR-1: count 0 -> 1 -> 2 -> refused -> reason accepted."""

    def test_ac_wr_1_two_free_runs_then_refusal_then_reason(self):
        for n in (1, 2):
            result = self.wait_run("--full", "--", *OK, log=self.log(f"run{n}.log"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.numbers(), list(range(1, n + 1)))

        third = self.log("run3.log")
        refused = self.wait_run("--full", "--", *OK, log=third)
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
        self.assertEqual(refused.stdout.splitlines(), [refusal(3)])
        self.assertNotIn("state=", refused.stdout)
        for suffix in ("", ".pid", ".exit"):
            self.assertFalse(Path(f"{third}{suffix}").exists(), f"a refused start wrote {suffix or 'the log'}")
        self.assertEqual(self.numbers(), [1, 2], "a refused start was counted")

        accepted = self.wait_run("--full", "--reason", "flaky\nnetwork  retry", "--", *OK, log=third)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertEqual(self.numbers(), [1, 2, 3])
        last = self.counter().read_text(encoding="utf-8").splitlines()[-1]
        self.assertTrue(last.endswith(" full 3 reason=flaky network retry"), last)

        fourth = self.wait_run("--full", "--", *OK, log=self.log("run4.log"))
        self.assertEqual(fourth.stdout.splitlines(), [refusal(4)])

    def test_runs_without_full_are_never_counted(self):
        for n in range(4):
            self.assertEqual(self.wait_run("--", *OK, log=self.log(f"run{n}.log")).returncode, 0)
        self.assertFalse(self.counter().exists())

    def test_counter_is_private_to_the_owner(self):
        self.assertEqual(self.wait_run("--full", "--", *OK).returncode, 0)
        self.assertEqual(self.counts.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.counter().stat().st_mode & 0o777, 0o600)

    def test_a_planted_counter_symlink_fails_open_and_is_never_written(self):
        self.counts.mkdir(parents=True)
        target = self.work / "precious.txt"
        target.write_text("keep me\n")
        self.counter().symlink_to(target)
        result = self.wait_run("--full", "--", *OK)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertIn("not counted", result.stderr)
        self.assertEqual(target.read_text(), "keep me\n")

    def test_an_unwritable_counter_dir_fails_open(self):
        self.counts.parent.mkdir(parents=True)
        self.counts.write_text("a file where the directory should be\n")
        for n in range(3):
            result = self.wait_run("--full", "--", *OK, log=self.log(f"run{n}.log"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("not counted", result.stderr)


class Edges(Base):
    """AC-WR-2."""

    def test_no_run_id_fails_open_with_one_note(self):
        for n in range(3):
            result = self.wait_run("--full", "--", *OK, log=self.log(f"run{n}.log"), run_id=None)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
            self.assertIn("GRAPH_RUN_ID", result.stderr)
        self.assertFalse(self.counts.exists())

    def test_unsafe_run_ids_fail_open_and_write_nothing(self):
        for run_id in ("a/b", "..", ".", "", "x" * 129, "a b", "a\nb"):
            with self.subTest(run_id=run_id):
                for n in range(3):
                    result = self.wait_run("--full", "--", *OK, log=self.log(f"run{n}.log"), run_id=run_id)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("GRAPH_RUN_ID", result.stderr)
                self.assertFalse(self.counts.exists(), run_id)
                self.assertFalse((self.work / "cache" / "a").exists())

    def test_longest_safe_id_is_counted(self):
        run_id = "A-z.0_" * 21 + "xx"
        self.assertEqual(len(run_id), 128)
        self.assertEqual(self.wait_run("--full", "--", *OK, run_id=run_id).returncode, 0)
        self.assertEqual(self.numbers(run_id), [1])

    def test_concurrent_starts_are_counted_exactly_once_each(self):
        argvs = [["bash", str(SCRIPT), "--log", str(self.log(f"c{n}.log")), "--max-block", "0", "--full", "--", *SLEEP_2]
                 for n in range(4)]
        calls = [subprocess.Popen(argv, cwd=self.work, env=self.env(), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for argv in argvs]
        results = [(call.wait(timeout=30), call.stdout.read()) for call in calls]
        for call in calls:
            call.stdout.close()
            call.stderr.close()
        self.assertEqual(sorted(code for code, _ in results), [2, 2, 75, 75], results)
        self.assertEqual(sorted(self.numbers()), [1, 2])
        refused = sorted(out.strip() for code, out in results if code == 2)
        self.assertEqual(refused, [refusal(3), refusal(3)])

    def test_concurrent_writers_never_share_a_number(self):
        barrier = threading.Barrier(16)
        path = wait_count.counter_path({"GRAPH_WAIT_RUN_DIR": str(self.counts), "GRAPH_RUN_ID": RUN_ID})
        self.counts.mkdir(parents=True, mode=0o700)

        def one():
            barrier.wait()
            wait_count.count_and_check(path, "load")

        threads = [threading.Thread(target=one) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(self.numbers(), list(range(1, 17)))

    def test_a_writer_waits_for_the_lock(self):
        path = wait_count.counter_path({"GRAPH_WAIT_RUN_DIR": str(self.counts), "GRAPH_RUN_ID": RUN_ID})
        self.counts.mkdir(parents=True, mode=0o700)
        done = threading.Event()
        with open(path, "a+", encoding="utf-8") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            writer = threading.Thread(target=lambda: (wait_count.count_and_check(path, None), done.set()))
            writer.start()
            self.assertFalse(done.wait(0.5), "count_and_check ran while another holder had the lock")
            held.write("2026-01-01T00:00:00Z full 1\n")
            held.flush()
            fcntl.flock(held, fcntl.LOCK_UN)
        writer.join(timeout=10)
        self.assertEqual(self.numbers(), [1, 2])

    def test_a_start_on_a_busy_log_is_refused_and_not_counted(self):
        log = self.log()
        self.assertEqual(self.wait_run("--max-block", "0", "--full", "--", *SLEEP_2, log=log).returncode, 75)
        again = self.wait_run("--max-block", "0", "--full", "--", *OK, log=log)
        self.assertEqual(again.returncode, 2, again.stdout + again.stderr)
        self.assertIn("still running", again.stderr)
        self.assertEqual(self.numbers(), [1])

    def test_attach_never_counts(self):
        log = self.log()
        self.assertEqual(self.wait_run("--max-block", "0", "--full", "--", *SLEEP_2, log=log).returncode, 75)
        self.assertEqual(self.wait_run("--max-block", "0", log=log).returncode, 75)
        self.assertEqual(self.wait_run("--max-block", "0", "--full", log=log).returncode, 75)
        attach = self.wait_run("--max-block", "10", "--full", "--reason", "attach", log=log)
        self.assertEqual(attach.returncode, 0, attach.stdout + attach.stderr)
        self.assertEqual(self.numbers(), [1])

    def test_empty_reason_is_a_usage_error(self):
        for reason in ("", "   "):
            with self.subTest(reason=reason):
                log = self.log()
                result = self.wait_run("--full", "--reason", reason, "--", *OK, log=log)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage", result.stderr)
                self.assertFalse(log.exists())
        self.assertFalse(self.counter().exists())

    def test_reason_without_full_is_a_usage_error(self):
        log = self.log()
        result = self.wait_run("--reason", "why", "--", *OK, log=log)
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage", result.stderr)
        self.assertFalse(log.exists())

    def test_refused_third_start_leaves_the_running_second_job_attachable(self):
        self.assertEqual(self.wait_run("--full", "--", *OK, log=self.log("first.log")).returncode, 0)
        second = self.log("second.log")
        self.assertEqual(self.wait_run("--max-block", "0", "--full", "--", *SLEEP_2, log=second).returncode, 75)
        pid = Path(f"{second}.pid").read_text()

        elsewhere = self.wait_run("--full", "--", *OK, log=self.log("third.log"))
        self.assertEqual(elsewhere.stdout.splitlines(), [refusal(3)])
        same_log = self.wait_run("--max-block", "0", "--full", "--", *OK, log=second)
        self.assertEqual(same_log.returncode, 2, same_log.stdout + same_log.stderr)
        self.assertNotIn("state=", same_log.stdout)
        self.assertEqual(Path(f"{second}.pid").read_text(), pid)
        self.assertFalse(Path(f"{second}.exit").exists())

        attach = self.wait_run("--max-block", "10", log=second)
        self.assertEqual(attach.returncode, 0, attach.stdout + attach.stderr)
        self.assertRegex(attach.stdout, rf"^wait-run: exit=0 state=complete elapsed=\d+s max_block=10s log={re.escape(str(second))}$")
        self.assertEqual(self.numbers(), [1, 2])


class Unit(unittest.TestCase):
    def test_counter_path_defaults_to_the_xdg_cache(self):
        path = wait_count.counter_path({"XDG_CACHE_HOME": "/c", "GRAPH_RUN_ID": "r-t1"})
        self.assertEqual(path, Path("/c/graph-engineering/wait-run/r-t1.full"))

    def test_counter_path_override_wins(self):
        path = wait_count.counter_path({"XDG_CACHE_HOME": "/c", "GRAPH_WAIT_RUN_DIR": "/w", "GRAPH_RUN_ID": "r"})
        self.assertEqual(path, Path("/w/r.full"))

    def test_counter_path_rejects_unsafe_ids(self):
        for run_id in (None, "", ".", "..", "a/b", "x" * 129, "a\nb"):
            env = {"GRAPH_WAIT_RUN_DIR": "/w"} | ({} if run_id is None else {"GRAPH_RUN_ID": run_id})
            self.assertIsNone(wait_count.counter_path(env), repr(run_id))

    def test_free_runs_is_two(self):
        self.assertEqual(wait_count.FREE_FULL_RUNS, 2)

    def test_counter_module_is_generic_and_dash_free(self):
        body = (HOOKS / "scripts" / "wait_count.py").read_text(encoding="utf-8")
        self.assertNotIn(chr(0x2014), body)
        self.assertNotRegex(body, r"(?i)koach|fitness")


if __name__ == "__main__":
    unittest.main(verbosity=2)
