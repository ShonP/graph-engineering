"""guard-poll-loop.sh: deny shell loops that sleep, only inside implementer subagents.

Every payload here is SYNTHETIC, shaped like the PreToolUse(Bash) stdin observed
on CLI 2.1.289: a subagent call carries agent_id and agent_type, the main thread
carries neither, and a `claude --agent X` main session carries agent_type only.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
HOOK = PLUGIN / 'hooks' / 'scripts' / 'guard-poll-loop.sh'
PYTHON_DIR = str(Path(sys.executable).parent)
SUBAGENT_ID = 'a1b2c3d4e5f6a7b8c'

UNTIL = 'cd /w && until grep -q done log.txt; do sleep 10; done'
WHILE = 'while true\ndo\n  sleep 5\ndone'
FOR = 'for i in $(seq 30); do curl -s localhost:8080 && break; sleep 2; done'
HEREDOC = "cat > wait.sh <<'EOF'\nuntil test -f ready; do sleep 1; done\nEOF"


def payload(command, agent_type=None, agent_id=SUBAGENT_ID):
    body = {'session_id': 's', 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
            'tool_input': {'command': command, 'description': 'd'}}
    if agent_id is not None:
        body['agent_id'] = agent_id
    if agent_type is not None:
        body['agent_type'] = agent_type
    return json.dumps(body)


def run_hook(stdin, path=None, guard=None):
    env = {'PATH': path or f'{PYTHON_DIR}:/usr/bin:/bin', 'HOME': tempfile.gettempdir()}
    if guard is not None:
        env['GRAPH_POLL_GUARD'] = guard
    return subprocess.run(['/bin/bash', str(HOOK)], input=stdin, env=env, capture_output=True,
                          text=True, timeout=30)


DENY = [
    ('until, plugin spelling', payload(UNTIL, 'graph-engineering:implementer')),
    ('while, plugin spelling', payload(WHILE, 'graph-engineering:implementer-simple')),
    ('for, plugin spelling', payload(FOR, 'graph-engineering:implementer')),
    ('until, bare spelling', payload(UNTIL, 'implementer')),
    ('while, bare spelling', payload(WHILE, 'implementer-simple')),
    ('for, bare spelling', payload(FOR, 'implementer-simple')),
    ('sleep in the condition', payload('while sleep 3; do test -f x && break; done', 'implementer')),
    ('nested loop', payload('while :; do for f in a b; do echo $f; done; sleep 1; done', 'implementer')),
    ('absolute sleep path', payload('until false; do /bin/sleep 1; done', 'implementer')),
    ('known limitation: heredoc writing a looping script', payload(HEREDOC, 'implementer')),
]

ALLOW = [
    ('main thread', payload(UNTIL, agent_id=None)),
    ('--agent main session', payload(UNTIL, 'graph-engineering:implementer', agent_id=None)),
    ('reviewer subagent', payload(UNTIL, 'graph-engineering:reviewer')),
    ('unknown subagent', payload(UNTIL, 'probe')),
    ('commit message', payload('git commit -m "no sleep loops"', 'implementer')),
    ('quoted prose with loop words', payload('git commit -m "while waiting, do not sleep"', 'implementer')),
    ('loop without sleep', payload('for f in a b; do echo $f; done', 'implementer')),
    ('sleep after the loop closed', payload('for f in a b; do echo $f; done; sleep 1', 'implementer')),
    ('loop word not in command position', payload('echo for; do_sleep', 'implementer')),
    ('unclosed quote', payload('echo "while true; do sleep 1; done', 'implementer')),
    ('unparsable stdin', 'not json, but it says sleep'),
    ('non-object json', '["sleep"]'),
    ('command not a string', json.dumps({'tool_name': 'Bash', 'agent_id': 'x', 'agent_type': 'implementer',
                                         'tool_input': {'command': ['sleep']}})),
    ('non-Bash tool', json.dumps({'tool_name': 'Write', 'agent_id': 'x', 'agent_type': 'implementer',
                                  'tool_input': {'command': UNTIL}})),
]


class PollLoopDecisions(unittest.TestCase):
    def test_denies_sleep_loops_in_implementer_subagents(self):
        for name, stdin in DENY:
            with self.subTest(name):
                result = run_hook(stdin)
                self.assertEqual(result.returncode, 0, result.stderr)
                out = json.loads(result.stdout)['hookSpecificOutput']
                self.assertEqual(out['hookEventName'], 'PreToolUse')
                self.assertEqual(out['permissionDecision'], 'deny')
                self.assertIn('hooks/scripts/wait-run.sh', out['permissionDecisionReason'])
                self.assertIn('Write tool', out['permissionDecisionReason'])

    def test_allows_everything_else_silently(self):
        for name, stdin in ALLOW:
            with self.subTest(name):
                result = run_hook(stdin)
                self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)


class KillSwitchAndFailOpen(unittest.TestCase):
    def test_guard_on_and_unset_are_active(self):
        stdin = payload(UNTIL, 'implementer')
        for guard in (None, 'on'):
            with self.subTest(guard=guard):
                self.assertIn('"deny"', run_hook(stdin, guard=guard).stdout)

    def test_guard_off_disables_the_hook(self):
        result = run_hook(payload(UNTIL, 'implementer'), guard='off')
        self.assertEqual((result.returncode, result.stdout), (0, ''))

    def test_no_python_fails_open_quietly(self):
        with tempfile.TemporaryDirectory() as empty:
            result = run_hook(payload(UNTIL, 'implementer'), path=empty)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))


STUB = '#!/bin/sh\n: > "$MARKER_DIR/started"\nexit 1\n'


class FastPath(unittest.TestCase):
    def run_with_stub_python(self, stdin):
        with tempfile.TemporaryDirectory() as work:
            stubs = Path(work)
            for name in ('python3', 'uv'):
                (stubs / name).write_text(STUB.replace('$MARKER_DIR', work))
                (stubs / name).chmod(0o755)
            result = run_hook(stdin, path=f'{work}:/bin')
            return result, (stubs / 'started').exists()

    def test_input_without_sleep_never_starts_python(self):
        result, started = self.run_with_stub_python(payload('until make; do echo again; done', 'implementer'))
        self.assertEqual((result.returncode, result.stdout), (0, ''))
        self.assertFalse(started, 'python must not start when the input has no sleep')

    def test_input_with_sleep_reaches_python(self):
        result, started = self.run_with_stub_python(payload(UNTIL, 'implementer'))
        self.assertEqual((result.returncode, result.stdout), (0, ''))
        self.assertTrue(started, 'control: the stub is on the path the hook takes')


if __name__ == '__main__':
    unittest.main(verbosity=2)
