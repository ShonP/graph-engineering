"""Exercise configured gates against real temporary Git worktrees."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HOOKS = Path(__file__).resolve().parents[1] / 'scripts'

class ConfiguredChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'repo'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Hook fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'tracked').write_text('baseline')
        self.git('add', 'tracked')
        self.git('commit', '-qm', 'baseline')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True, text=True)

    def configure(self, root, argv):
        (root / '.claude').mkdir(exist_ok=True)
        (root / '.claude/graph-checks.json').write_text(json.dumps({'version': 1, 'test': {'argv': argv, 'timeout_seconds': 10}}))

    def stop(self, cwd):
        return subprocess.run(['bash', str(HOOKS / 'test-before-stop.sh')], input=json.dumps({'cwd': str(cwd), 'stop_hook_active': False}), env=dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root)), capture_output=True, text=True, timeout=20)

    def test_make_gate_failure_is_not_silently_skipped(self):
        self.configure(self.root, ['make', 'check'])
        (self.root / 'Makefile').write_text('check:\n\t@echo meaningful-test-failure\n\t@exit 1\n')
        result = self.stop(self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn('meaningful-test-failure', result.stderr)

    def test_missing_configured_runner_blocks(self):
        self.configure(self.root, ['graph-nonexistent-test-runner'])
        result = self.stop(self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn('not found', result.stderr)

    def test_malformed_configuration_blocks(self):
        self.configure(self.root, ['true'])
        (self.root / '.claude/graph-checks.json').write_text('{')
        self.assertEqual(self.stop(self.root).returncode, 2)

    def test_linked_candidate_checks_itself(self):
        candidate = self.root.parent / 'candidate'
        self.git('worktree', 'add', '-qb', 'candidate', str(candidate))
        self.configure(self.root, ['sh', '-c', 'echo parent-ran > parent-marker'])
        self.configure(candidate, ['sh', '-c', 'echo candidate-failed >&2; exit 1'])
        result = self.stop(candidate)
        self.assertEqual(result.returncode, 2)
        self.assertIn('candidate-failed', result.stderr)
        self.assertFalse((self.root / 'parent-marker').exists())

    def test_nested_linked_candidate_checks_itself(self):
        candidate = self.root / '.worktrees' / 'candidate'
        self.git('worktree', 'add', '-qb', 'nested', str(candidate))
        self.configure(self.root, ['sh', '-c', 'echo parent-ran > parent-marker'])
        self.configure(candidate, ['sh', '-c', 'echo nested-failed >&2; exit 1'])
        result = self.stop(candidate)
        self.assertEqual(result.returncode, 2)
        self.assertIn('nested-failed', result.stderr)
        self.assertFalse((self.root / 'parent-marker').exists())

    def test_unrelated_repository_blocks_without_running_bound_gate(self):
        other = self.root.parent / 'other'
        other.mkdir()
        subprocess.run(['git', '-C', str(other), 'init', '-q'], check=True)
        self.configure(self.root, ['sh', '-c', 'echo parent-ran > parent-marker'])
        result = self.stop(other)
        self.assertEqual(result.returncode, 2)
        self.assertIn('different repository', result.stderr)
        self.assertFalse((self.root / 'parent-marker').exists())

    def test_workspace_bound_checks_contained_candidate_repo(self):
        self.configure(self.root, ['sh', '-c', 'echo workspace-candidate-failed >&2; exit 1'])
        result = subprocess.run(['bash', str(HOOKS / 'test-before-stop.sh')],
            input=json.dumps({'cwd': str(self.root)}),
            env=dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root.parent)),
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('workspace-candidate-failed', result.stderr)

    def test_unsupported_python_is_visible(self):
        binaries = self.root / 'bin'
        binaries.mkdir()
        python = binaries / 'python3'
        python.write_text('#!/bin/sh\nexit 1\n')
        python.chmod(0o755)
        result = subprocess.run(['/bin/bash', '-c', 'source "$1"; PATH="$2"; ge_python_runtime',
                                 '_', str(HOOKS / 'python-runtime.sh'), str(binaries)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python 3.11+', result.stderr)
        self.assertIn('No checks ran', result.stderr)

    def test_selected_versioned_executable_is_used(self):
        binaries = self.root / 'versions'
        binaries.mkdir()
        old = binaries / 'python3'
        old.write_text('#!/bin/sh\nexit 1\n')
        old.chmod(0o755)
        selected = binaries / 'python3.12'
        selected.write_text('#!/bin/sh\nexit 0\n')
        selected.chmod(0o755)
        uv = binaries / 'uv'
        uv.write_text('#!/bin/sh\nprintf "%s\\n" "' + str(selected) + '"\n')
        uv.chmod(0o755)
        result = subprocess.run(['/bin/bash', '-c',
            'source "$1"; unset GE_PYTHON; PATH="$2:/usr/bin:/bin"; ge_python_runtime && "$GE_PYTHON" -c probe',
            '_', str(HOOKS / 'python-runtime.sh'), str(binaries)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_success_reaches_configured_command(self):
        self.configure(self.root, ['sh', '-c', 'echo exercised > marker'])
        self.assertEqual(self.stop(self.root).returncode, 0)
        self.assertEqual((self.root / 'marker').read_text().strip(), 'exercised')

if __name__ == '__main__':
    unittest.main()
