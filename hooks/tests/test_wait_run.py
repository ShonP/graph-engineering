#!/usr/bin/env python3
"""wait-run.sh: a bounded blocking wait for long suites (AC-W3-WR-01..06).

Stdlib only. Run from any directory:

    python3 hooks/tests/test_wait_run.py

Drives hooks/scripts/wait-run.sh as an agent would, from a working directory
unrelated to the plugin. Every job is a synthetic `sh -c` one-liner writing into
a temp dir; tearDown kills whatever a failed case left running.
"""

import os
import re
import select
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent
PLUGIN = HOOKS.parent
SCRIPT = HOOKS / "scripts" / "wait-run.sh"
REFUSAL = "a job for this log is still running; call again without a command to attach"


def line_re(log, code, state, block=270):
    return re.compile(rf"^wait-run: exit={code} state={state} elapsed=\d+s max_block={block}s log={re.escape(str(log))}$")


def descendants(root):
    """Every live pid under root, found through ppid links (a tree kill's view)."""
    table = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True, check=True).stdout
    children = {}
    for row in table.splitlines():
        pid, ppid = (int(field) for field in row.split())
        children.setdefault(ppid, []).append(pid)
    found, todo = [], [root]
    while todo:
        for pid in children.get(todo.pop(), []):
            found.append(pid)
            todo.append(pid)
    return found


def wait_for(path, seconds):
    deadline = time.monotonic() + seconds
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    return path.exists()


class Base(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name).resolve()
        self.log = self.work / "suite.log"
        self.addCleanup(self.kill_job)

    def kill_job(self):
        try:
            os.killpg(int(Path(f"{self.log}.pid").read_text()), signal.SIGKILL)
        except (OSError, ValueError):
            pass

    def run_wait(self, *args, log=None, timeout=30):
        argv = ["bash", str(SCRIPT), "--log", str(log or self.log), *args]
        return subprocess.run(argv, cwd=self.work, capture_output=True, text=True, timeout=timeout, check=False)

    def assert_summary(self, result, code, state, block=270):
        first = result.stdout.splitlines()[0] if result.stdout else ""
        self.assertRegex(first, line_re(self.log, code, state, block), result.stdout + result.stderr)


class Acceptance(Base):
    def test_ac01_success_is_complete_and_one_line(self):
        result = self.run_wait("--", "sh", "-c", "echo hello; exit 0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_summary(result, 0, "complete")
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
        self.assertIn("hello", self.log.read_text())
        self.assertEqual(Path(f"{self.log}.exit").read_text().strip(), "0")

    def test_ac02_failure_returns_code_and_last_20_lines(self):
        job = "i=1; while [ $i -le 30 ]; do echo line$i; i=$((i+1)); done; exit 3"
        result = self.run_wait("--", "sh", "-c", job)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assert_summary(result, 3, "complete")
        tail = result.stdout.splitlines()[1:]
        self.assertEqual(tail, [f"line{i}" for i in range(11, 31)])

    def test_ac02_tail_is_capped_at_2000_chars(self):
        result = self.run_wait("--", "sh", "-c", "i=0; while [ $i -lt 20 ]; do printf '%0300d\\n' $i; i=$((i+1)); done; exit 1")
        self.assertEqual(result.returncode, 1)
        tail = result.stdout.split("\n", 1)[1]
        self.assertLessEqual(len(tail.rstrip("\n")), 2000)
        self.assertTrue(tail.rstrip().endswith("19"), tail[-40:])

    def test_ac03_partial_then_attach_completes(self):
        started = time.monotonic()
        first = self.run_wait("--max-block", "1", "--", "sh", "-c", "sleep 3; echo finished; exit 0")
        self.assertLess(time.monotonic() - started, 2.5, "the call blocked past --max-block")
        self.assertEqual(first.returncode, 75, first.stderr)
        self.assert_summary(first, "running", "partial", block=1)
        self.assertEqual(len(first.stdout.splitlines()), 1)
        attach = self.run_wait("--max-block", "10")
        self.assertEqual(attach.returncode, 0, attach.stderr)
        self.assert_summary(attach, 0, "complete", block=10)
        self.assertIn("finished", self.log.read_text())

    def test_ac04_argv_while_running_is_refused(self):
        self.assertEqual(self.run_wait("--max-block", "0", "--", "sh", "-c", "sleep 3").returncode, 75)
        again = self.run_wait("--max-block", "0", "--", "sh", "-c", "exit 0")
        self.assertEqual(again.returncode, 2)
        self.assertIn(REFUSAL, again.stdout + again.stderr)
        self.assertNotIn("state=", again.stdout)

    def test_ac04_max_block_above_590_is_clamped(self):
        result = self.run_wait("--max-block", "900", "--", "sh", "-c", "exit 0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_summary(result, 0, "complete", block=590)

    def test_ac05_job_survives_the_caller_being_killed(self):
        argv = ["bash", str(SCRIPT), "--log", str(self.log), "--max-block", "30", "--",
                "sh", "-c", "sleep 2; echo survived; exit 4"]
        caller = subprocess.Popen(argv, cwd=self.work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  start_new_session=True)
        try:
            self.assertTrue(wait_for(Path(f"{self.log}.pid"), 10), "no .pid written")
            for pid in descendants(caller.pid):  # a tree kill, then a group kill
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            os.killpg(caller.pid, signal.SIGKILL)
        finally:
            caller.wait(timeout=10)
        self.assertLess(caller.returncode, 0, "the caller was not killed")
        self.assertFalse(Path(f"{self.log}.exit").exists(), "the job finished before the kill")
        self.assertTrue(wait_for(Path(f"{self.log}.exit"), 15), "the job died with its caller")
        self.assertEqual(Path(f"{self.log}.exit").read_text().strip(), "4")
        self.assertIn("survived", self.log.read_text())

    def test_ac06_both_implementer_agents_name_wait_run(self):
        for name in ("implementer.md", "implementer-simple.md"):
            text = (PLUGIN / "agents" / name).read_text(encoding="utf-8")
            self.assertTrue("hooks/scripts/wait-run.sh" in text, name + " does not name wait-run")


class Edges(Base):
    def test_rerun_replaces_the_previous_exit(self):
        self.assertEqual(self.run_wait("--", "sh", "-c", "exit 0").returncode, 0)
        result = self.run_wait("--", "sh", "-c", "exit 5")
        self.assertEqual(result.returncode, 5)
        self.assert_summary(result, 5, "complete")

    def test_signal_death_reports_128_plus_n(self):
        result = self.run_wait("--", "sh", "-c", "kill -TERM $$")
        self.assertEqual(result.returncode, 143)
        self.assert_summary(result, 143, "complete")

    def test_missing_program_completes_with_127_and_says_why(self):
        result = self.run_wait("--", str(self.work / "no-such-tool"))
        self.assertEqual(result.returncode, 127)
        self.assertIn("no-such-tool", result.stdout)

    def test_header_script_file_shape_runs_a_non_executable_file(self):
        # A file made with the Write tool is 0644: exec'd bare it is 127, so the header
        # teaches passing it through its interpreter.
        header = SCRIPT.read_text(encoding="utf-8").split("\nset ", 1)[0]
        self.assertIn("`bash <absolute path>`", header)
        job = self.work / "suite.sh"
        job.write_text("set -o pipefail\necho piped | cat\n")
        job.chmod(0o644)
        bare = self.run_wait("--", str(job))
        self.assertEqual(bare.returncode, 127, bare.stdout)
        result = self.run_wait("--", "bash", str(job))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("piped", self.log.read_text())

    def test_job_holds_no_descriptor_of_the_caller(self):
        # A harness waits for EOF on the pipes it handed the shell; an orphan
        # holding one open would hang the call for the job's whole life.
        read_end, write_end = os.pipe()
        argv = ["bash", str(SCRIPT), "--log", str(self.log), "--max-block", "0", "--", "sh", "-c", "sleep 3"]
        with subprocess.Popen(argv, cwd=self.work, stdout=subprocess.DEVNULL, pass_fds=(write_end,)) as caller:
            os.close(write_end)
            self.assertEqual(caller.wait(timeout=10), 75)
        ready, _, _ = select.select([read_end], [], [], 2)
        self.assertTrue(ready and os.read(read_end, 1) == b"", "an extra descriptor stayed open in the job")
        os.close(read_end)

    def test_attach_without_a_job_is_an_error(self):
        result = self.run_wait()
        self.assertEqual(result.returncode, 2)
        self.assertIn("no job for this log", result.stderr)

    def test_attach_to_a_lost_job_is_an_error_not_a_hang(self):
        self.assertEqual(self.run_wait("--max-block", "0", "--", "sh", "-c", "sleep 30").returncode, 75)
        self.kill_job()
        started = time.monotonic()
        result = self.run_wait("--max-block", "20")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(result.returncode, 2)
        self.assertIn("ended without an exit code", result.stderr)

    def test_relative_log_and_negative_block_are_usage_errors(self):
        self.assertEqual(self.run_wait("--", "true", log="suite.log").returncode, 2)
        self.assertEqual(self.run_wait("--max-block", "-1", "--", "true").returncode, 2)
        self.assertFalse(self.log.exists())

    def test_log_is_private_to_the_owner(self):
        self.assertEqual(self.run_wait("--", "true").returncode, 0)
        for path in (self.log, Path(f"{self.log}.pid"), Path(f"{self.log}.exit")):
            self.assertEqual(path.stat().st_mode & 0o077, 0, path.name)

    def test_a_planted_symlink_is_never_truncated(self):
        target = self.work / "precious.txt"
        target.write_text("keep me\n")
        self.log.symlink_to(target)
        result = self.run_wait("--", "true")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(target.read_text(), "keep me\n")

    def test_scripts_are_generic_and_dash_free(self):
        for path in (SCRIPT, HOOKS / "scripts" / "wait_run.py"):
            body = path.read_text(encoding="utf-8")
            self.assertNotIn(chr(0x2014), body, path.name)
            # Consumer names: scripts/check-private-names.py, from a list outside the repo.
        self.assertTrue(os.access(SCRIPT, os.X_OK), "wait-run.sh is not executable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
