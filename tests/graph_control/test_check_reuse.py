"""graph-control check <root> --reuse: replays the Stop hook's memo verdict and never executes."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_memo import git, repo
from graph_control import cli, memo
from graph_control.commands import iter_commands

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "scripts" / "configured_check.py"


def invoke(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["check", *argv])
    return code, json.loads(out.getvalue())


class CheckReuse(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = repo(self.temp.name)
        self.marker = self.root.parent / "executed"
        self.configure({"argv": ["sh", "-c", f'echo ran >> "{self.marker}"; echo red >&2; exit 4']})
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(memo.DISABLE, None)

    def configure(self, test):
        (self.root / ".claude").mkdir(exist_ok=True)
        (self.root / ".claude/graph-checks.json").write_text(json.dumps({"version": 1, "test": test}))

    def hook(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return subprocess.run([sys.executable, str(HOOK), "test", str(self.root)], env=env,
                              capture_output=True, text=True, timeout=20)

    def test_replays_the_verdict_the_hook_stored(self):  # AC-W2-MM-06
        self.assertEqual(self.hook().returncode, 2)
        code, result = invoke(str(self.root), "--reuse")
        self.assertEqual(code, 0, result)
        self.assertEqual((result["status"], result["verdict"], result["exit_code"]), ("PASS", "fail", 4))
        self.assertEqual(result["observed_at"], memo.lookup(self.root, next(iter(self.entries())))["observed_at"])
        self.assertEqual(self.marker.read_text().splitlines(), ["ran"])

    def entries(self):
        return json.loads(memo.memo_path(self.root).read_text())["entries"]

    def test_a_changed_tree_is_blocked_and_nothing_runs(self):  # AC-W2-MM-06
        self.hook()
        (self.root / "tracked.txt").write_text("edited\n")
        self.assertEqual(invoke(str(self.root), "--reuse"),
                         (1, {"status": "BLOCKED", "reason": "no memo for the current tree"}))
        self.assertEqual(self.marker.read_text().splitlines(), ["ran"])

    def test_no_memo_yet_is_blocked_without_executing(self):
        self.assertEqual(invoke(str(self.root), "--reuse")[1]["reason"], "no memo for the current tree")
        self.assertFalse(self.marker.exists())

    def test_the_kill_switch_also_stops_reuse(self):
        self.hook()
        os.environ[memo.DISABLE] = "1"
        code, result = invoke(str(self.root), "--reuse")
        self.assertEqual((code, result["status"]), (1, "BLOCKED"))
        self.assertIn(memo.DISABLE, result["reason"])

    def test_missing_or_unusable_config_is_blocked(self):
        for name, text in (("missing", None), ("no test block", '{"version": 1}'), ("not JSON", "{"),
                           ("bad argv", '{"version": 1, "test": {"argv": "make"}}')):
            with self.subTest(name):
                path = self.root / ".claude/graph-checks.json"
                path.unlink(missing_ok=True)
                if text is not None:
                    path.write_text(text)
                self.assertEqual(invoke(str(self.root), "--reuse")[:1], (1,))

    def test_a_package_config_replays_from_its_own_directory(self):
        """A monorepo package's config: the hook and check --reuse compute the same key from that directory."""
        package = self.root / "pkg"
        (package / ".claude").mkdir(parents=True)
        (package / ".claude/graph-checks.json").write_text(
            (self.root / ".claude/graph-checks.json").read_text())
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        ran = subprocess.run([sys.executable, str(HOOK), "test", str(self.root), str(package)], env=env,
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(ran.returncode, 2, ran.stderr)
        self.assertIn(f" in {package} (exit 4)", ran.stderr)
        code, result = invoke(str(package), "--reuse")
        self.assertEqual((code, result["verdict"]), (0, "fail"), result)
        self.assertEqual(invoke(str(self.root), "--reuse")[1]["reason"], "no memo for the current tree")

    def test_a_non_git_root_is_blocked(self):
        plain = Path(self.temp.name) / "plain"
        (plain / ".claude").mkdir(parents=True)
        (plain / ".claude/graph-checks.json").write_text('{"version": 1, "test": {"argv": ["true"]}}')
        self.assertEqual(invoke(str(plain), "--reuse")[1]["status"], "BLOCKED")

    def test_reuse_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            cli.main(["check", str(self.root)])
        self.assertEqual(caught.exception.code, 2)

    def test_the_plugin_package_ships_check(self):
        self.assertIn("check", [module.NAME for module in iter_commands()])
        self.assertEqual(git(self.root, "status", "--porcelain").stdout, "?? .claude/\n")


if __name__ == "__main__":
    unittest.main()
