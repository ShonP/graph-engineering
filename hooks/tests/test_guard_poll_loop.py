"""guard-poll-loop.sh: deny shell loops that sleep, inside every roster subagent.

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
SCRIPTS = PLUGIN / 'hooks' / 'scripts'
HOOK = SCRIPTS / 'guard-poll-loop.sh'
WAIT_RUN = PLUGIN / 'hooks' / 'scripts' / 'wait-run.sh'
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
    ('sleep after then inside a loop', payload('until x; do if y; then sleep 1; fi; done', 'implementer')),
    ('sleep in a command substitution', payload('until x; do y=$(sleep 1); done', 'implementer')),
    ('known limitation: heredoc writing a looping script', payload(HEREDOC, 'implementer')),
    ('reviewer subagent', payload(UNTIL, 'graph-engineering:reviewer')),
    ('qa, plugin spelling', payload(WHILE, 'graph-engineering:qa')),
    ('qa-lead, bare spelling', payload(UNTIL, 'qa-lead')),
    ('researcher, plugin spelling', payload(FOR, 'graph-engineering:researcher')),
    ('retro, bare spelling', payload(WHILE, 'retro')),
]

ALLOW = [
    ('main thread', payload(UNTIL, agent_id=None)),
    ('--agent main session', payload(UNTIL, 'graph-engineering:implementer', agent_id=None)),
    ('unknown subagent', payload(UNTIL, 'probe')),
    ('commit message', payload('git commit -m "no sleep loops"', 'implementer')),
    ('quoted prose with loop words', payload('git commit -m "while waiting, do not sleep"', 'implementer')),
    ('loop without sleep', payload('for f in a b; do echo $f; done', 'implementer')),
    ('sleep after the loop closed', payload('for f in a b; do echo $f; done; sleep 1', 'implementer')),
    ('loop word not in command position', payload('echo for; do_sleep', 'implementer')),
    ('loop words as plain arguments', payload("printf '%s\\n' for do sleep done", 'implementer')),
    ('unclosed quote', payload('echo "while true; do sleep 1; done', 'implementer')),
    ('grep for sleep in a loop', payload('for f in hooks/scripts/*.sh; do grep -n sleep "$f"; done', 'implementer')),
    ('quoted sleep argument in a loop', payload("for f in a b; do grep -n 'sleep' $f; done", 'implementer')),
    ('git log --grep sleep in a loop', payload('for p in a b; do git log --grep sleep -- $p; done', 'implementer')),
    ('unparsable stdin', 'not json, but it says sleep'),
    ('non-object json', '["sleep"]'),
    ('command not a string', json.dumps({'tool_name': 'Bash', 'agent_id': 'x', 'agent_type': 'implementer',
                                         'tool_input': {'command': ['sleep']}})),
    ('non-Bash tool', json.dumps({'tool_name': 'Write', 'agent_id': 'x', 'agent_type': 'implementer',
                                  'tool_input': {'command': UNTIL}})),
]


class PollLoopDecisions(unittest.TestCase):
    def test_denies_sleep_loops_in_roster_subagents(self):
        for name, stdin in DENY:
            with self.subTest(name):
                result = run_hook(stdin)
                self.assertEqual(result.returncode, 0, result.stderr)
                out = json.loads(result.stdout)['hookSpecificOutput']
                self.assertEqual(out['hookEventName'], 'PreToolUse')
                self.assertEqual(out['permissionDecision'], 'deny')
                self.assertIn(f' {WAIT_RUN} ', out['permissionDecisionReason'])
                self.assertIn('Write tool', out['permissionDecisionReason'])

    def test_allows_everything_else_silently(self):
        for name, stdin in ALLOW:
            with self.subTest(name):
                result = run_hook(stdin)
                self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)


def import_poll_loop(test):
    sys.path.insert(0, str(SCRIPTS))
    test.addCleanup(sys.path.remove, str(SCRIPTS))
    import poll_loop
    return poll_loop


def frontmatter(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    end = lines.index('---', 1)
    return dict(line.split(':', 1) for line in lines[1:end] if ':' in line and not line.startswith(('#', ' ')))


class DecideDirectly(unittest.TestCase):
    def test_unclosed_quote_is_no_decision_not_an_exception(self):
        poll_loop = import_poll_loop(self)
        command = 'until false; do sleep 1; done; echo "open'
        self.assertIsNone(poll_loop.decide(json.loads(payload(command, 'implementer'))))


class RosterDrift(unittest.TestCase):
    """Every roster agent that lists Bash is guarded, in both spellings, and nothing else is."""

    def test_guarded_types_match_agents_with_bash(self):
        poll_loop = import_poll_loop(self)
        with_bash = set()
        for path in sorted((PLUGIN / 'agents').glob('*.md')):
            fields = frontmatter(path)
            tools = {tool.strip() for tool in fields.get('tools', '').strip(' []').split(',')}
            if 'Bash' in tools:
                with_bash.add(fields['name'].strip())
        self.assertGreaterEqual(len(with_bash), 11)
        bare = {name for name in poll_loop.GUARDED_TYPES if ':' not in name}
        self.assertEqual(bare, with_bash)
        self.assertEqual(poll_loop.GUARDED_TYPES, bare | {f'graph-engineering:{name}' for name in bare})


class AllowCorpusUnderQa(unittest.TestCase):
    """Widening the gate denies no command the tokenizer already allows."""

    def test_non_loop_commands_stay_allowed_for_qa(self):
        replayed = 0
        for name, stdin in ALLOW:
            try:
                body = json.loads(stdin)
            except ValueError:
                continue
            if not isinstance(body, dict) or body.get('agent_type') != 'implementer':
                continue
            body['agent_type'] = 'graph-engineering:qa'
            replayed += 1
            with self.subTest(name):
                result = run_hook(json.dumps(body))
                self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)
        self.assertGreaterEqual(replayed, 12)


class KnownBypassForms(unittest.TestCase):
    """Forms the tokenizer misses (followups FU2). A fix flips these to unexpected successes."""

    def assert_denied(self, command):
        result = run_hook(payload(command, 'graph-engineering:qa'))
        self.assertIn('"deny"', result.stdout)

    @unittest.expectedFailure
    def test_loop_inside_bash_c(self):
        self.assert_denied("bash -c 'until test -f r; do sleep 1; done'")

    @unittest.expectedFailure
    def test_sleep_after_an_assignment(self):
        self.assert_denied('while true; do FOO=1 sleep 1; done')

    @unittest.expectedFailure
    def test_sleep_in_backticks(self):
        self.assert_denied('while true; do `sleep 1`; done')


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


class AgentsWaitThroughWaitRun(unittest.TestCase):
    """The guarded agents are told the full-suite form of the wait the deny reason names."""

    def test_full_suite_form_and_reason_budget(self):
        for name in ('implementer', 'implementer-simple'):
            text = (PLUGIN / 'agents' / f'{name}.md').read_text(encoding='utf-8')
            with self.subTest(name):
                self.assertIn('wait-run.sh --full --log <absolute path> -- <argv>', text)
                self.assertIn('--reason "<why>"', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
