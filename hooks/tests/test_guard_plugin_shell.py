"""guard-plugin-shell.sh: the hook wrapper around plugin_shell.py (fast path, kill switch, fail open).

fixtures/plugin-shell/trigger.json carries the one REAL witness (run 01a111fa,
tasks/goal.md:16-17, the same command as test_plugin_shell.TRIGGER). Every other
fixture and payload is SYNTHETIC, shaped like the PreToolUse(Bash) stdin of CLI
2.1.289+. Trigger-shaped commands are only ever fed to the hook on stdin.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
HOOKS = PLUGIN / 'hooks'
HOOK = HOOKS / 'scripts' / 'guard-plugin-shell.sh'
FIXTURES = HOOKS / 'tests' / 'fixtures' / 'plugin-shell'
PYTHON_DIR = str(Path(sys.executable).parent)
sys.path.insert(0, str(HOOKS / 'tests'))

from test_plugin_shell import GROUP_C, GROUP_V, TRIGGER, TRIGGER_LITERAL_PATH, bash_payload

import plugin_shell

REASON = (
    f'Call plugin scripts by their literal absolute path under {PLUGIN}, never through a shell '
    'variable, and pass argv straight through instead of wrapping it in bash -c or sh -c; for a '
    'pipeline, set -o pipefail or an && chain, Write a script file under .graph/<run>/ and pass it '
    'through bash, as -- bash /abs/path/check.sh (a Write-created file is not executable). Claude '
    'Code cannot check a $VAR command or a shell -c script, so it stops even bypass-mode runs on a '
    'safety prompt. To switch this guard off, set GRAPH_SHELL_GUARD=off.'
)


def fixture(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


def run_hook(stdin, path=None, guard=None):
    env = {'PATH': path or f'{PYTHON_DIR}:/usr/bin:/bin', 'HOME': tempfile.gettempdir()}
    if guard is not None:
        env['GRAPH_SHELL_GUARD'] = guard
    return subprocess.run(['/bin/bash', str(HOOK)], input=stdin, env=env, capture_output=True,
                          text=True, timeout=30, check=False)


class EndToEnd(unittest.TestCase):
    """AC-GUARD-E2E: the real hook on the trigger fixture, every switch and failure."""

    def assert_deny(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(list(decision), ['hookSpecificOutput'])
        out = decision['hookSpecificOutput']
        self.assertEqual(sorted(out), ['hookEventName', 'permissionDecision',
                                       'permissionDecisionReason'])
        self.assertEqual(out['hookEventName'], 'PreToolUse')
        self.assertEqual(out['permissionDecision'], 'deny')
        self.assertEqual(out['permissionDecisionReason'], REASON)

    def assert_silent(self, result):
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    def test_guard_unset_denies(self):
        self.assert_deny(run_hook(fixture('trigger.json')))

    def test_guard_on_denies(self):
        self.assert_deny(run_hook(fixture('trigger.json'), guard='on'))

    def test_guard_off_is_silent(self):
        self.assert_silent(run_hook(fixture('trigger.json'), guard='off'))

    def test_no_supported_python_fails_open(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assert_silent(run_hook(fixture('trigger.json'), path=empty))

    def test_off_with_malformed_json_is_silent(self):
        self.assert_silent(run_hook(fixture('malformed.json'), guard='off'))

    def test_malformed_json_with_guard_on_fails_open(self):
        self.assert_silent(run_hook(fixture('malformed.json')))

    def test_read_tool_is_silent(self):
        self.assert_silent(run_hook(fixture('trigger-read.json')))

    def test_main_thread_is_denied_too(self):
        self.assert_deny(run_hook(bash_payload(TRIGGER, agent_id=None)))

    def test_hook_file_is_executable(self):
        mode = subprocess.run(['git', 'ls-files', '-s', str(HOOK)], cwd=PLUGIN,
                              capture_output=True, text=True, check=True).stdout
        self.assertTrue(mode.startswith('100755 '), mode)


STUB = '#!/bin/sh\n: > "$MARKER_DIR/started"\nexit 1\n'


class FastPath(unittest.TestCase):
    """AC-GUARD-FAST: python starts only when the payload could hold either shape."""

    def started(self, stdin):
        with tempfile.TemporaryDirectory() as work:
            stubs = Path(work)
            for name in ('python3', 'uv'):
                (stubs / name).write_text(STUB.replace('$MARKER_DIR', work))
                (stubs / name).chmod(0o755)
            result = run_hook(stdin, path=f'{work}:/bin')
            self.assertEqual((result.returncode, result.stdout), (0, ''))
            return (stubs / 'started').exists()

    def test_clean_command_never_starts_python(self):
        self.assertFalse(self.started(fixture('clean-ls.json')))

    def test_trigger_reaches_python(self):
        self.assertTrue(self.started(fixture('trigger.json')), 'control: the stub is on the path')

    def test_every_denied_shape_reaches_python(self):
        shell_c_spellings = [
            "/abs/hooks/scripts/wait-run.sh --log /x -- bash\t-c 'a | b'",
            "/abs/hooks/scripts/wait-run.sh --log /x -- 'bash' -c 'a | b'",
            "/abs/hooks/scripts/wait-run.sh --log /x -- \"sh\" '-c' 'a | b'",
            "/abs/hooks/scripts/wait-run.sh --log /x -- dash -x -c 'a | b'",
        ]
        for command in [TRIGGER, TRIGGER_LITERAL_PATH, *GROUP_V, *GROUP_C, *shell_c_spellings]:
            with self.subTest(command):
                self.assertIsNotNone(plugin_shell.find_violation(command))
                self.assertTrue(self.started(bash_payload(command)))

    def test_allowed_plugin_calls_skip_python(self):
        commands = [
            '/abs/hooks/scripts/wait-run.sh --log /x -- make test',
            '/abs/hooks/scripts/wait-run.sh --full --log /x -- bash scripts/run-all-tests.sh',
            '/abs/scripts/lane-run.sh xcodebuild --slots 1 -- xcodebuild -scheme App test',
        ]
        self.assertFalse(self.started(fixture('literal-bash-script.json')))
        for command in commands:
            with self.subTest(command):
                self.assertFalse(self.started(bash_payload(command)))


class Readme(unittest.TestCase):
    """AC-GUARD-REG (README half): the flag registry entry and the literal-path rule."""

    @classmethod
    def setUpClass(cls):
        cls.text = (HOOKS / 'README.md').read_text(encoding='utf-8')

    def section(self, heading):
        match = re.search(rf'^## {re.escape(heading)}\n(.*?)(?=^## )', self.text, re.M | re.S)
        self.assertIsNotNone(match, heading)
        return match.group(1)

    def test_guard_section_states_the_flag_and_failure_mode(self):
        body = self.section('Plugin-script shell guard')
        for needle in ('guard-plugin-shell.sh', 'GRAPH_SHELL_GUARD=off', 'fails open',
                       'main thread', 'CLAUDE_CODE_DISABLE_INLINE_SHELL_RM_PROMPT',
                       'never sets it', 'Owner', 'Default', 'removal date', '2.1.291', 'F6'):
            with self.subTest(needle):
                self.assertIn(needle, body)

    def test_guard_section_follows_the_sleep_loop_guard(self):
        headings = re.findall(r'^## (.+)$', self.text, re.M)
        at = headings.index('Sleep-loop guard')
        self.assertEqual(headings[at + 1], 'Plugin-script shell guard')

    def test_sleep_loop_parsing_points_at_the_shell_guard(self):
        self.assertIn('plugin-script shell guard', self.section('Sleep-loop guard'))

    def test_wait_run_section_teaches_the_literal_path(self):
        body = self.section('wait-run: a bounded wait for long suites')
        self.assertIn('<plugin root>/hooks/scripts/wait-run.sh --log', body)
        self.assertIn('literal absolute path', body)
        self.assertIn('never through a shell variable', body)
        self.assertIn('-- bash /abs/path/check.sh', body)

    def test_turning_hooks_off_lists_the_switch(self):
        self.assertIn('GRAPH_SHELL_GUARD=off', self.section('Turning hooks off'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
