"""Exercise configured gates against real temporary Git worktrees."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HOOKS = Path(__file__).resolve().parents[1] / 'scripts'
TEMPLATE = Path(__file__).resolve().parents[2] / 'templates' / 'graph-checks.json'
sys.path.insert(0, str(HOOKS))
from checks_config import load  # noqa: E402

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

    def configure(self, root, argv, timeout=10, **blocks):
        test = {'test': {'argv': argv, 'timeout_seconds': timeout}} if argv else {}
        (root / '.claude').mkdir(exist_ok=True)
        (root / '.claude/graph-checks.json').write_text(json.dumps({'version': 1, **test, **blocks}))

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

    def hook(self, script, payload, project_dir, path=None):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
        if path is not None:
            env.pop('GE_PYTHON', None)
            env['PATH'] = path
        return subprocess.run(['bash', str(HOOKS / script)], input=json.dumps(payload), env=env,
                              capture_output=True, text=True, timeout=20)

    def edit(self, project_dir, file):
        file.write_text('x = 1\n')
        result = self.hook('lint-touched-file.sh', {'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
                                                    'tool_input': {'file_path': str(file)}}, project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['hookSpecificOutput']['additionalContext'] if result.stdout else ''

    def test_workspace_lint_uses_contained_repo_config(self):  # AC-W1-STOP-06, lint side
        self.configure(self.root, None, lint={'argv': ['sh', '-c', 'echo ws-finding; exit 1', 'lint', '{file}'],
                                              'extensions': ['.py']})
        context = self.edit(self.root.parent, self.root / 'a.py')
        self.assertTrue(context.startswith('Lint on a.py reported problems (exit 1).'), context)
        self.assertIn('ws-finding', context)

    def test_lint_config_only_on_the_worktree_branch(self):
        candidate = self.root.parent / 'candidate'
        self.git('worktree', 'add', '-qb', 'candidate', str(candidate))
        self.configure(candidate, None, lint={'argv': ['sh', '-c', 'echo wt-finding; exit 1', 'lint', '{file}'],
                                              'extensions': ['.py']})
        context = self.edit(self.root, candidate / 'a.py')
        self.assertIn('wt-finding', context)

    def fake_old_python(self):
        binaries = self.root.parent / 'old-python'
        binaries.mkdir(exist_ok=True)
        python = binaries / 'python3'
        python.write_text('#!/bin/sh\nexit 1\n')
        python.chmod(0o755)
        return f'{binaries}:/usr/bin:/bin'

    def test_missing_runtime_is_silent_without_opt_in(self):
        (self.root / 'go.mod').write_text('module example.invalid/cli\n')
        result = self.hook('test-before-stop.sh', {'cwd': str(self.root), 'stop_hook_active': False},
                           self.root, path=self.fake_old_python())
        self.assertEqual((result.returncode, result.stderr), (0, ''))

    def test_missing_runtime_is_visible_to_an_opted_in_workspace_repo(self):
        self.configure(self.root, ['true'])
        result = self.hook('test-before-stop.sh', {'cwd': str(self.root), 'stop_hook_active': False},
                           self.root.parent, path=self.fake_old_python())
        self.assertEqual(result.returncode, 2)
        self.assertIn('Python 3.11+', result.stderr)

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

    def test_unrelated_repository_without_opt_in_is_silent(self):
        other = self.root.parent / 'other'
        other.mkdir()
        subprocess.run(['git', '-C', str(other), 'init', '-q'], check=True)
        result = self.stop(other)
        self.assertEqual((result.returncode, result.stderr), (0, ''))

    def test_config_without_test_block_is_silent(self):
        self.configure(self.root, None, lint={'argv': ['sh', '-c', 'touch marker', 'lint', '{file}'], 'extensions': ['.py']})
        self.assertEqual((self.stop(self.root).returncode, (self.root / 'marker').exists()), (0, False))

    def test_failed_precheck_leaves_tests_unverified(self):  # AC-W1-STOP-04
        for argv in (['false'], ['graph-nonexistent-precheck'], ['sleep', '5']):
            with self.subTest(precheck=argv):
                self.configure(self.root, ['sh', '-c', 'touch marker; exit 1'], precheck={'argv': argv, 'timeout_seconds': 1})
                started = time.monotonic()
                result = self.stop(self.root)
                self.assertLess(time.monotonic() - started, 3)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'precheck {argv[0]} failed (exit ', result.stderr)
                self.assertIn('tests not verified', result.stderr)
                self.assertFalse((self.root / 'marker').exists())

    def test_passing_precheck_runs_tests(self):
        self.configure(self.root, ['sh', '-c', 'echo still-red >&2; exit 1'], precheck={'argv': ['true']})
        result = self.stop(self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn('still-red', result.stderr)

    def test_timeout_kills_the_process_group_without_blocking(self):  # AC-W1-STOP-05
        self.configure(self.root, ['sh', '-c', '(sleep 5; touch marker) & wait'], timeout=1)
        started = time.monotonic()
        result = self.stop(self.root)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.strip(), 'tests not verified: sh did not finish within 1 s')
        time.sleep(6)
        self.assertFalse((self.root / 'marker').exists())

    def test_failure_names_argv_and_keeps_a_bounded_tail(self):
        lines = 'for i in $(seq 1 50); do echo line-$i; done; exit 3'
        wide = 'for i in 1 2 3 4 5 6 7 8 9; do printf "%01000d\\n" $i; done; exit 1'
        self.configure(self.root, ['sh', '-c', lines])
        head, _, tail = self.stop(self.root).stderr.partition('\n')
        self.assertEqual(head, f'Tests failed: sh -c {lines} in {self.root} (exit 3). '
                               'Fix them, then finish. This check runs once per prompt.')
        self.assertEqual(tail.split(), [f'line-{i}' for i in range(31, 51)])
        self.configure(self.root, ['sh', '-c', wide])
        tail = self.stop(self.root).stderr.partition('\n')[2]
        self.assertLessEqual(len(tail.encode()), 4000)
        self.assertIn('9'.zfill(1000), tail)

    def lint(self, argv, name='a.py', timeout=30):
        self.configure(self.root, None, lint={'argv': argv, 'extensions': ['.py'], 'timeout_seconds': timeout})
        (self.root / name).write_text('x = 1\n')
        result = subprocess.run([sys.executable, str(HOOKS / 'configured_check.py'), 'lint', str(self.root), str(self.root / name)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['hookSpecificOutput']['additionalContext'] if result.stdout else ''

    def test_lint_timeout_is_reported_not_blocking(self):
        started = time.monotonic()
        self.assertEqual(self.lint(['sh', '-c', 'sleep 5', 'lint', '{file}'], timeout=1), 'lint not verified: sh did not finish within 1 s.')
        self.assertLess(time.monotonic() - started, 3)

    def test_lint_output_is_bounded(self):
        context = self.lint(['sh', '-c', 'for i in $(seq 1 90); do echo finding-$i; done; exit 1', 'lint', '{file}'])
        self.assertTrue(context.startswith('Lint on a.py reported problems (exit 1). This is information, not a block.'), context)
        self.assertEqual([line for line in context.splitlines() if line.startswith('finding-')], [f'finding-{i}' for i in range(31, 91)])
        self.assertEqual(self.lint(['true', '{file}']), '')


class Schema(unittest.TestCase):  # AC-W1-CFG-01
    def load(self, data):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'graph-checks.json'
            path.write_text(data if isinstance(data, str) else json.dumps(data))
            return load(path)

    def test_rejects_invalid_shapes(self):
        lint = {'argv': ['ruff', 'check', '{file}'], 'extensions': ['.py']}
        invalid = {
            'not JSON': '{', 'no version': {'test': {'argv': ['make']}}, 'version 2': {'version': 2},
            'bool version': {'version': True}, 'unknown top key': {'version': 1, 'tests': {'argv': ['make']}},
            'unknown block key': {'version': 1, 'test': {'argv': ['make'], 'shell': True}},
            'block not an object': {'version': 1, 'test': ['make']}, 'empty argv': {'version': 1, 'test': {'argv': []}},
            'empty argv element': {'version': 1, 'test': {'argv': ['make', '']}},
            'NUL in argv': {'version': 1, 'test': {'argv': ['make\x00']}},
            '{file} in test argv': {'version': 1, 'test': {'argv': ['pytest', '{file}']}},
            '{file} inside a precheck element': {'version': 1, 'precheck': {'argv': ['x', '--f={file}']}},
            'lint without {file}': {'version': 1, 'lint': {**lint, 'argv': ['ruff', 'check']}},
            'two {file} elements': {'version': 1, 'lint': {**lint, 'argv': ['ruff', '{file}', '{file}']}},
            'lint without extensions': {'version': 1, 'lint': {'argv': lint['argv']}},
            'empty extensions': {'version': 1, 'lint': {**lint, 'extensions': []}},
            'extension without dot': {'version': 1, 'lint': {**lint, 'extensions': ['py']}},
            'timeout 0': {'version': 1, 'test': {'argv': ['make'], 'timeout_seconds': 0}},
            'timeout 601': {'version': 1, 'test': {'argv': ['make'], 'timeout_seconds': 601}},
            'precheck timeout 61': {'version': 1, 'precheck': {'argv': ['true'], 'timeout_seconds': 61}},
            'lint timeout 121': {'version': 1, 'lint': {**lint, 'timeout_seconds': 121}},
            'bool timeout': {'version': 1, 'test': {'argv': ['make'], 'timeout_seconds': True}},
        }
        for reason, data in invalid.items():
            with self.subTest(reason), self.assertRaises(ValueError) as caught:
                self.load(data)
            self.assertNotIn('\n', str(caught.exception))

    def test_defaults_and_optional_blocks(self):
        config = self.load({'version': 1, 'test': {'argv': ['make']}, 'precheck': {'argv': ['true']},
                            'lint': {'argv': ['ruff', '{file}'], 'extensions': ['.py']}})
        self.assertEqual((config.test.timeout, config.precheck.timeout, config.lint.timeout), (600, 10, 60))
        self.assertEqual(self.load({'version': 1}).test, None)

    def test_template_loads(self):
        config = load(TEMPLATE)
        self.assertTrue(config.test and config.precheck and config.lint)
        self.assertIn('{file}', config.lint.argv)

if __name__ == '__main__':
    unittest.main()
