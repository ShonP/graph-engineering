"""guard-agent.sh: a no-op without a policy block, a thin uv pass-through with one.

Hook payloads here are SYNTHETIC PreToolUse(Agent) inputs. uv is a stub that
records its argv and stdin, except in the one end-to-end case that needs the
real uv and the pinned PyYAML.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
HOOK = PLUGIN / 'hooks' / 'scripts' / 'guard-agent.sh'
SYSTEM_PATH = '/usr/bin:/bin'
PAYLOAD = json.dumps({'hook_event_name': 'PreToolUse', 'tool_name': 'Agent',
                      'tool_input': {'description': 'd', 'prompt': 'p', 'subagent_type': 'general-purpose'}})
STUB = ('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$STUB_DIR/argv"\ncat > "$STUB_DIR/stdin"\n'
        'printf "%s" "$STUB_OUT"\nexit "$STUB_RC"\n')


class GuardAgentHook(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name).resolve()
        self.project = self.work / 'project'
        (self.project / '.claude').mkdir(parents=True)
        self.stubs = self.work / 'bin'
        self.stubs.mkdir()
        (self.stubs / 'uv').write_text(STUB)
        (self.stubs / 'uv').chmod(0o755)

    def profile(self, text):
        path = self.project / '.claude' / 'graph-profile.yaml'
        path.write_text(text)
        return path

    def hook(self, path=None, project=True, out='{"stub": true}', rc='0'):
        env = {'PATH': path or f'{self.stubs}:{SYSTEM_PATH}', 'HOME': str(self.work),
               'STUB_DIR': str(self.work), 'STUB_OUT': out, 'STUB_RC': rc}
        if project:
            env['CLAUDE_PROJECT_DIR'] = str(self.project)
        return subprocess.run(['bash', str(HOOK)], input=PAYLOAD, env=env, capture_output=True, text=True,
                              cwd=self.work, timeout=60)

    def assert_silent_noop(self, result):
        self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)
        self.assertFalse((self.work / 'argv').exists(), 'uv must not be invoked')

    def test_no_profile_is_a_noop(self):
        self.assert_silent_noop(self.hook())

    def test_profile_without_top_level_policy_is_a_noop(self):
        self.profile('routing: {}\n# policy: commented out\nlocalAgents:\n  policy: nested key\n')
        self.assert_silent_noop(self.hook())

    def test_no_project_dir_is_a_noop(self):
        self.profile('policy: {}\n')
        self.assert_silent_noop(self.hook(project=False))

    def test_missing_uv_is_a_noop(self):
        self.assertIsNone(shutil.which('uv', path=SYSTEM_PATH), 'fixture assumes no uv in the system PATH')
        self.profile('policy: {}\n')
        result = self.hook(path=SYSTEM_PATH)
        self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)

    def test_policy_pipes_stdin_to_graph_control_and_prints_its_stdout(self):
        profile = self.profile('policy: {}\n')
        result = self.hook()
        self.assertEqual((result.returncode, result.stdout), (0, '{"stub": true}\n'), result.stderr)
        self.assertEqual((self.work / 'argv').read_text().splitlines(), [
            'run', '--quiet', '--script', str(PLUGIN / 'scripts' / 'graph-control.py'), 'guard-agent',
            '--profile', str(profile), '--root', str(self.project)])
        self.assertEqual((self.work / 'stdin').read_text(), PAYLOAD)

    def test_failing_guard_fails_open(self):
        self.profile('policy: {}\n')
        result = self.hook(out='{"status": "BLOCKED"}', rc='1')
        self.assertEqual((result.returncode, result.stdout), (0, ''))

    @unittest.skipUnless(shutil.which('uv'), 'end-to-end case needs the real uv')
    def test_real_uv_denies_general_purpose(self):
        self.profile('policy:\n  block_types: [general-purpose]\n')
        # Full inherited PATH: a version-manager shim for uv (mise, asdf) needs it, as a real hook has it.
        env = {**os.environ, 'CLAUDE_PROJECT_DIR': str(self.project)}
        result = subprocess.run(['bash', str(HOOK)], input=PAYLOAD, env=env, capture_output=True, text=True,
                                timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)['hookSpecificOutput']
        self.assertEqual(output['permissionDecision'], 'deny')
        self.assertIn('general-purpose is blocked', output['permissionDecisionReason'])


if __name__ == '__main__':
    unittest.main()
