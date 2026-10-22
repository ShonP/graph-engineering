"""worktree-ready: declarative check of a task worktree after bootstrap, against SYNTHETIC temp repos."""

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import helpers

import importlib.util

if importlib.util.find_spec("yaml") is None:
    raise unittest.SkipTest("needs PyYAML: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

from graph_control.cli import main  # noqa: E402


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}}
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                          check=True, capture_output=True, text=True, env=env).stdout.strip()


class WorktreeReady(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.main = self.root / "main"
        self.main.mkdir()
        git(self.main, "init", "-q")
        git(self.main, "config", "user.email", "t@example.invalid")
        git(self.main, "config", "user.name", "T")
        git(self.main, "config", "commit.gpgsign", "false")
        (self.main / "a.txt").write_text("a\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-q", "-m", "base")
        self.linked = self.root / "linked"
        git(self.main, "worktree", "add", "-q", "-b", "task", str(self.linked))

    def profile(self, **keys):
        path = self.root / "profile.yaml"
        path.write_text(json.dumps(keys))
        return path

    def call(self, worktree, profile, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["worktree-ready", str(worktree), "--profile", str(profile), *extra])
        return code, json.loads(out.getvalue())

    def test_failed_bootstrap_shows_last_twenty_log_lines(self):
        log = self.root / "boot.log"
        log.write_text("".join(f"line {n}\n" for n in range(1, 51)))
        code, result = self.call(self.linked, self.profile(bootstrap=["pnpm install"]),
                                 "--bootstrap-exit", "1", "--bootstrap-log", str(log))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "BLOCKED")
        tail = "\n".join(f"line {n}" for n in range(31, 51))
        self.assertEqual(result["reason"], f"NEEDS_SETUP: bootstrap exited 1; last 20 lines:\n{tail}")

    def test_failed_bootstrap_without_readable_log(self):
        code, result = self.call(self.linked, self.profile(bootstrap=["x"]), "--bootstrap-exit", "3",
                                 "--bootstrap-log", str(self.root / "absent.log"))
        self.assertEqual(code, 1)
        self.assertEqual(result["reason"], "NEEDS_SETUP: bootstrap exited 3; no log")
        code, result = self.call(self.linked, self.profile(bootstrap=["x"]), "--bootstrap-exit", "3")
        self.assertEqual(result["reason"], "NEEDS_SETUP: bootstrap exited 3; no log")

    def test_ready_path_missing_then_present(self):
        profile = self.profile(bootstrap_ready=["node_modules"])
        code, result = self.call(self.linked, profile, "--bootstrap-exit", "0")
        self.assertEqual(code, 1)
        self.assertEqual(result["reason"], "NEEDS_SETUP: missing after bootstrap: node_modules")
        (self.linked / "node_modules").mkdir()
        code, result = self.call(self.linked, profile, "--bootstrap-exit", "0")
        self.assertEqual(code, 0)
        self.assertEqual(result, {"status": "PASS", "noop": False, "ready": ["node_modules"]})

    def test_missing_entries_are_all_named(self):
        (self.linked / "b").mkdir()
        code, result = self.call(self.linked, self.profile(bootstrap_ready=["a1", "b", "c1"]))
        self.assertEqual(result["reason"], "NEEDS_SETUP: missing after bootstrap: a1, c1")

    def test_noop_without_keys_even_outside_git(self):
        plain = self.root / "plain"
        plain.mkdir()
        for keys in ({}, {"bootstrap": [], "bootstrap_ready": []}):
            code, result = self.call(plain, self.profile(**keys), "--bootstrap-exit", "1")
            self.assertEqual((code, result), (0, {"status": "PASS", "noop": True}))

    def test_main_checkout_is_refused(self):
        code, result = self.call(self.main, self.profile(bootstrap=["pnpm install"]))
        self.assertEqual(code, 1)
        self.assertEqual(result["reason"], f"NEEDS_SETUP: {self.main} is the main checkout; "
                                           "bootstrap runs only in a task worktree")

    def test_not_a_git_dir(self):
        plain = self.root / "plain"
        plain.mkdir()
        code, result = self.call(plain, self.profile(bootstrap=["x"]))
        self.assertEqual(code, 1)
        self.assertTrue(result["reason"].startswith("NEEDS_SETUP: "))

    def test_unsafe_ready_entries_are_refused(self):
        for entry in ("/abs", "../x", "a/../b"):
            code, result = self.call(self.linked, self.profile(bootstrap_ready=[entry]))
            self.assertEqual(code, 1)
            self.assertEqual(result["reason"],
                             f"NEEDS_SETUP: bootstrap_ready {entry} must be a relative path inside the worktree")

    def test_bootstrap_without_exit_status_is_blocked(self):
        code, result = self.call(self.linked, self.profile(bootstrap=["pnpm install"]))
        self.assertEqual((code, result), (1, {"status": "BLOCKED", "reason":
                                              "NEEDS_SETUP: bootstrap is set but no --bootstrap-exit was given"}))

    def test_ready_paths_alone_need_no_exit_status(self):
        (self.linked / "node_modules").mkdir()
        code, result = self.call(self.linked, self.profile(bootstrap_ready=["node_modules"]))
        self.assertEqual((code, result), (0, {"status": "PASS", "noop": False, "ready": ["node_modules"]}))

    def test_malformed_settings_name_the_key(self):
        commands = "NEEDS_SETUP: bootstrap must be a list of command strings"
        paths = "NEEDS_SETUP: bootstrap_ready must be a list of relative paths"
        for keys, reason in (({"bootstrap": "pnpm install"}, commands), ({"bootstrap": [5]}, commands),
                             ({"bootstrap": [""]}, commands), ({"bootstrap": {"a": "b"}}, commands),
                             ({"bootstrap_ready": "node_modules"}, paths), ({"bootstrap_ready": [5]}, paths),
                             ({"bootstrap_ready": [""]}, paths)):
            code, result = self.call(self.linked, self.profile(**keys), "--bootstrap-exit", "0")
            self.assertEqual((code, result), (1, {"status": "BLOCKED", "reason": reason}), keys)

    def test_bootstrap_command_is_never_executed(self):
        marker = self.root / "ran"
        code, result = self.call(self.linked, self.profile(bootstrap=[f"touch {marker}"]), "--bootstrap-exit", "0")
        self.assertEqual((code, result), (0, {"status": "PASS", "noop": False, "ready": []}))
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
