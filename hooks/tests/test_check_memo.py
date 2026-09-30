"""The Stop hook's tree-keyed memo, end to end through test-before-stop.sh on real Git repos.

The suite counts its runs in a file outside the tree, so counting never moves
the tree the memo is keyed by.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

HOOKS = Path(__file__).resolve().parents[1] / 'scripts'
MEMO = 'GRAPH_CHECKS_NO_MEMO'
GIT_VARS = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR')
STAMP = r'\d{4}-\d\d-\d\dT[\d:.]+\+00:00'


class CheckMemo(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'repo'
        self.root.mkdir()
        self.count = self.root.parent / 'count'
        for args in (['init', '-q'], ['config', 'user.name', 'Hook fixture'],
                     ['config', 'user.email', 'fixture@example.invalid'], ['config', 'commit.gpgsign', 'false']):
            self.git(*args)
        (self.root / 'tracked').write_text('baseline\n')
        self.git('add', 'tracked')
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'baseline')

    def env(self, **extra):
        env = {key: value for key, value in os.environ.items() if key not in (MEMO, *GIT_VARS)}
        return {**env, 'CLAUDE_PROJECT_DIR': str(self.root), **extra}

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True, text=True,
                              env=self.env())

    def configure(self, script, timeout=10, root=None, **blocks):
        argv = ['sh', '-c', f'echo run >> "{self.count}"; {script}']
        root = root or self.root
        (root / '.claude').mkdir(exist_ok=True)
        (root / '.claude/graph-checks.json').write_text(json.dumps(
            {'version': 1, 'test': {'argv': argv, 'timeout_seconds': timeout}, **blocks}))
        return argv

    def stop(self, **env):
        return subprocess.run(['bash', str(HOOKS / 'test-before-stop.sh')],
                              input=json.dumps({'cwd': str(self.root), 'stop_hook_active': False}),
                              env=self.env(**env), capture_output=True, text=True, timeout=20)

    def runs(self):
        return len(self.count.read_text().splitlines()) if self.count.exists() else 0

    def test_unchanged_tree_replays_a_pass_without_running(self):  # AC-W2-MM-01
        self.configure('exit 0')
        self.assertEqual([self.stop().returncode, self.stop().returncode, self.runs()], [0, 0, 1])

    def test_unchanged_tree_replays_a_failure_with_its_tail(self):  # AC-W2-MM-01, AC-W2-MM-03
        argv = self.configure('echo boom-detail >&2; exit 3')
        first, second = self.stop(), self.stop()
        self.assertEqual((first.returncode, second.returncode, self.runs()), (2, 2, 1))
        head = second.stderr.splitlines()[0]
        self.assertRegex(head, re.escape(f'Tests failed: {" ".join(argv)} in {self.root} (exit 3) ')
                         + rf'\(replayed: tree unchanged since {STAMP}\)\. Fix them, then finish\.')
        self.assertIn('checks-state.json', second.stderr)
        self.assertIn('boom-detail', second.stderr)
        self.assertNotIn('replayed', first.stderr)

    def test_a_timeout_replays_as_not_verified(self):  # AC-W2-MM-03
        self.configure('sleep 5', timeout=1)
        self.assertEqual(self.stop().stderr.strip(), 'tests not verified: sh did not finish within 1 s')
        started = time.monotonic()
        replay = self.stop()
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(replay.returncode, 0)
        self.assertRegex(replay.stderr.strip(), rf'^tests not verified \(timed out at {STAMP}; tree unchanged\)$')
        self.assertEqual(self.runs(), 1)

    def test_tracked_untracked_and_config_changes_rerun(self):  # AC-W2-MM-02
        self.configure('exit 0')
        self.stop()
        (self.root / 'tracked').write_text('edited\n')
        self.stop()
        (self.root / 'untracked').write_text('new\n')
        self.stop()
        self.configure('exit 0', timeout=11)
        self.stop()
        self.assertEqual(self.runs(), 4)
        self.stop()
        self.assertEqual(self.runs(), 4)

    def test_bypass_env_runs_every_time_and_stores_nothing(self):  # AC-W2-MM-04, DoD both flag states
        self.configure('exit 0')
        for _ in range(2):
            self.assertEqual(self.stop(**{MEMO: '1'}).returncode, 0)
        self.assertEqual(self.runs(), 2)
        self.stop()
        self.stop()
        self.assertEqual(self.runs(), 3)

    def test_a_non_git_root_runs_without_a_memo(self):  # AC-W2-MM-04
        plain = self.root.parent / 'plain'
        plain.mkdir()
        self.configure('exit 0', root=plain)
        for _ in range(2):
            result = subprocess.run([sys.executable, str(HOOKS / 'configured_check.py'), 'test', str(plain)],
                                    env=self.env(), capture_output=True, text=True, timeout=20)
            self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual(self.runs(), 2)

    def test_a_failed_precheck_is_never_stored(self):
        ready = self.root.parent / 'ready'
        self.configure('exit 0', precheck={'argv': ['test', '-f', str(ready)]})
        self.assertIn('tests not verified', self.stop().stderr)
        ready.write_text('')
        self.stop()
        self.assertEqual(self.runs(), 1)

    def test_a_missing_runner_is_never_stored(self):
        (self.root / '.claude').mkdir()
        (self.root / '.claude/graph-checks.json').write_text(
            json.dumps({'version': 1, 'test': {'argv': ['graph-nonexistent-runner']}}))
        for _ in range(2):
            result = self.stop()
            self.assertEqual(result.returncode, 2)
            self.assertIn('not found', result.stderr)
            self.assertNotIn('replayed', result.stderr)

    def test_a_tree_that_moves_during_the_run_is_not_stored(self):
        self.configure('echo moved > tracked; exit 0')
        self.stop()
        self.git('checkout', '--', 'tracked')
        self.stop()
        self.assertEqual(self.runs(), 2)

    def test_the_memo_leaves_the_tree_clean(self):  # AC-W2-MM-05, end to end
        self.configure('exit 1')
        status = self.git('status', '--porcelain').stdout
        self.stop()
        self.assertEqual(self.git('status', '--porcelain').stdout, status)
        self.assertTrue((self.root / '.git/graph-engineering/checks-state.json').is_file())

    def test_the_hook_runs_without_site_packages(self):
        self.configure('exit 0')
        for _ in range(2):
            result = subprocess.run([sys.executable, '-S', str(HOOKS / 'configured_check.py'), 'test', str(self.root)],
                                    env=self.env(), capture_output=True, text=True, timeout=20)
            self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual(self.runs(), 1)


if __name__ == '__main__':
    unittest.main()
