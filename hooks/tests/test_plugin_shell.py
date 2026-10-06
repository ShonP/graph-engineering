"""plugin_shell.py: deny a Bash call that runs a plugin script the way Claude Code cannot check.

The commands below are strings, never executed. AC-DET-TRIGGER is the one REAL
witness (run 01a111fa, tasks/goal.md:16-17: an implementer on plugin 0.16.0, Claude
Code 2.1.291), with its placeholders filled by concrete paths. Every other command
and payload is SYNTHETIC, built from the tokenizer probe in the run's prior-art.md.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / 'scripts'))
sys.path.insert(0, str(HOOKS / 'tests'))

import plugin_shell
from test_guard_poll_loop import ALLOW, DENY

SCRIPT = HOOKS / 'scripts' / 'plugin_shell.py'

TRIGGER = ("cd /w/T16d && date -u +%s; P=/c/0.16.0; L=/r/logs; "
           "$P/hooks/scripts/wait-run.sh --full --log $L/T16d-fx2-tools-check-goldens.log "
           "-- bash -c 'set -o pipefail; tools/check --goldens'; echo wr=$?; "
           "tail -3 $L/T16d-fx2-tools-check-goldens.log")
TRIGGER_LITERAL_PATH = TRIGGER.replace('$P/hooks', '/c/0.16.0/hooks')
TRIGGER_FIXED = TRIGGER_LITERAL_PATH.replace(
    "-- bash -c 'set -o pipefail; tools/check --goldens'", '-- /r/check.sh')

GROUP_V = [
    '"$P"/hooks/scripts/wait-run.sh',
    '"$P/hooks/scripts/wait-run.sh"',
    '${P}/hooks/scripts/wait-run.sh',
    '"${CLAUDE_PLUGIN_ROOT}"/hooks/scripts/wait-run.sh',
    'GRAPH_RUN_ID=r1 $P/hooks/scripts/wait-run.sh',
    'env A=1 $P/hooks/scripts/wait-run.sh',
    'time $P/hooks/scripts/wait-run.sh',
    'cd /w && $P/scripts/lane-run.sh l -- x',
    '$ROOT/skills/process/review-protocol/scripts/mutate-witness.sh',
    'echo start\n$P/scripts/worktree-gc.sh --apply',
]

GROUP_C = [
    "/abs/hooks/scripts/wait-run.sh --log /x -- bash -c 'a | b'",
    "/abs/hooks/scripts/wait-run.sh --log /x -- sh -c 'a | b'",
    "/abs/hooks/scripts/wait-run.sh --log /x -- bash -lc 'a | b'",
    "/abs/hooks/scripts/wait-run.sh --log /x -- bash -euo pipefail -c 'a | b'",
    "/abs/hooks/scripts/wait-run.sh --log /x -- /bin/zsh -c 'a | b'",
    "/abs/scripts/lane-run.sh l --slots 1 -- sh -c 'a | b'",
    "bash /abs/skills/process/review-protocol/scripts/mutate-witness.sh --file f -- sh -c 'a | b'",
]

GROUP_G = [
    ('command substitution', 'x=$($P/hooks/scripts/wait-run.sh)'),
    ('heredoc body', "cat > run.sh <<'EOF'\n$P/hooks/scripts/wait-run.sh --log /x -- bash -c 'a | b'\nEOF"),
]

EXTRA_FP = [
    '/abs/hooks/scripts/wait-run.sh --log /x -- bash /abs/check.sh',
    'bash /abs/hooks/scripts/wait-run.sh --log /x -- tools/check',
    'git commit -m "fix $P/hooks/scripts/wait-run.sh under bash -c"',
    "bash -c 'echo hi'",
    '$EDITOR notes.md',
    '$HOME/bin/tool -c x',
    "rg -n 'wait-run.sh -- bash -c' docs",
    'echo "open $P/hooks/scripts/wait-run.sh',
    '',
]


def command_of(stdin):
    try:
        body = json.loads(stdin)
        command = body['tool_input']['command']
    except (ValueError, TypeError, KeyError):
        return stdin
    return command if isinstance(command, str) else stdin


def bash_payload(command, agent_id='a1b2c3d4e5f6a7b8c'):
    body = {'session_id': 's', 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
            'tool_input': {'command': command, 'description': 'd'}}
    if agent_id is not None:
        body['agent_id'] = agent_id
        body['agent_type'] = 'graph-engineering:implementer'
    return json.dumps(body)


def run_script(stdin):
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True,
                          text=True, timeout=30, check=False)


class Trigger(unittest.TestCase):
    """AC-DET-TRIGGER: the observed command, then its two boundary fixes."""

    def test_observed_command_is_a_variable_command(self):
        self.assertEqual(plugin_shell.find_violation(TRIGGER), 'variable-command')

    def test_literal_path_still_wraps_a_shell_c(self):
        self.assertEqual(plugin_shell.find_violation(TRIGGER_LITERAL_PATH), 'shell-c')

    def test_literal_path_and_plain_argv_is_clean(self):
        self.assertIsNone(plugin_shell.find_violation(TRIGGER_FIXED))


class Variants(unittest.TestCase):
    """AC-DET-VARIANTS: every spelling of the two shapes, and the named gaps."""

    def test_group_v_is_variable_command(self):
        self.assertEqual(len(GROUP_V), 10)
        for command in GROUP_V:
            with self.subTest(command):
                self.assertEqual(plugin_shell.find_violation(command), 'variable-command')

    def test_other_prefixes_keep_command_position(self):
        for prefix in ('nohup', 'command', 'exec', 'A=1 B=2', 'env A=1 B=2'):
            with self.subTest(prefix):
                command = f'{prefix} $P/hooks/scripts/wait-run.sh --log /x -- make'
                self.assertEqual(plugin_shell.find_violation(command), 'variable-command')

    def test_group_c_is_shell_c(self):
        self.assertEqual(len(GROUP_C), 7)
        for command in GROUP_C:
            with self.subTest(command):
                self.assertEqual(plugin_shell.find_violation(command), 'shell-c')

    def test_shell_c_stops_at_the_command_separator(self):
        command = "/abs/hooks/scripts/wait-run.sh --log /x -- make; bash -c 'echo hi'"
        self.assertIsNone(plugin_shell.find_violation(command))

    def test_separator_glued_to_a_substitution_still_splits(self):
        """Review F1: shlex glues `)` to the next operator (`);`, `)&&`, `)|`), so the
        command after an unquoted $(...) must still be read in command position."""
        cases = [
            ('P=$(cat /r/root); $P/hooks/scripts/wait-run.sh --log /x -- make',
             'variable-command'),
            ('P=$(ls -d /c/*/ | tail -1); $P/hooks/scripts/wait-run.sh --log /x -- make',
             'variable-command'),
            ('P=$(cat /r/root)&& $P/hooks/scripts/wait-run.sh --log /x -- make',
             'variable-command'),
            ('echo $(cat /r/root)| $P/hooks/scripts/wait-run.sh --log /x -- make',
             'variable-command'),
            ("echo $(date); /abs/hooks/scripts/wait-run.sh --log /x -- bash -c 'a|b'",
             'shell-c'),
            ("echo $(dirname $(pwd)); /abs/hooks/scripts/wait-run.sh -- sh -c 'a|b'",
             'shell-c'),
            ('echo $(date); make', None),
        ]
        for command, expected in cases:
            with self.subTest(command):
                self.assertEqual(plugin_shell.find_violation(command), expected)

    def test_known_gaps_return_none(self):
        """Known gap (followups F10), shared with the poll guard: the inside of $(...)
        and a heredoc body are not read as commands."""
        for name, command in GROUP_G:
            with self.subTest(name):
                self.assertIsNone(plugin_shell.find_violation(command))

    def test_plugin_scripts_are_exactly_the_agent_callable_ones(self):
        self.assertEqual(plugin_shell.PLUGIN_SCRIPTS, frozenset(
            {'wait-run.sh', 'mutate-witness.sh', 'lane-run.sh', 'worktree-gc.sh'}))


class FalsePositives(unittest.TestCase):
    """AC-DET-FP: legitimate commands are never flagged, and nothing raises."""

    def test_corpus_has_no_hits(self):
        poll_commands = [command_of(stdin) for _, stdin in ALLOW + DENY]
        corpus = poll_commands + EXTRA_FP
        self.assertGreaterEqual(len(poll_commands), 20)
        self.assertEqual(len(corpus), len(ALLOW) + len(DENY) + 9)
        hits = [command for command in corpus if plugin_shell.find_violation(command) is not None]
        self.assertEqual(hits, [])


class HookJson(unittest.TestCase):
    """AC-DET-HOOKJSON: the script speaks the PreToolUse protocol and fails open."""

    ROOT = Path(plugin_shell.__file__).resolve().parents[2]

    def assert_deny(self, stdin):
        result = run_script(stdin)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)['hookSpecificOutput']
        self.assertEqual(output['hookEventName'], 'PreToolUse')
        self.assertEqual(output['permissionDecision'], 'deny')
        self.assertIn(str(self.ROOT), output['permissionDecisionReason'])
        self.assertIn('script file', output['permissionDecisionReason'])
        self.assertRegex(output['permissionDecisionReason'], r'-- bash /\S+\.sh')
        self.assertIn('GRAPH_SHELL_GUARD=off', output['permissionDecisionReason'])

    def test_trigger_from_a_subagent_is_denied(self):
        self.assert_deny(bash_payload(TRIGGER))

    def test_trigger_from_the_main_thread_is_denied(self):
        self.assert_deny(bash_payload(TRIGGER, agent_id=None))

    def test_everything_else_prints_nothing(self):
        cases = [
            ('Read tool', json.dumps({'tool_name': 'Read', 'tool_input': {'command': TRIGGER}})),
            ('clean Bash', bash_payload(TRIGGER_FIXED)),
            ('malformed JSON', '{"tool_name": "Bash", '),
            ('tool_input not an object', json.dumps({'tool_name': 'Bash', 'tool_input': TRIGGER})),
        ]
        for name, stdin in cases:
            with self.subTest(name):
                result = run_script(stdin)
                self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)


if __name__ == '__main__':
    unittest.main()
