import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('session_usage', Path(__file__).resolve().parents[2] / 'scripts/session_usage.py')
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)

class UsageTests(unittest.TestCase):
    def test_stream_duplicates_do_not_double_bill_and_content_is_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            row = {'type': 'assistant', 'timestamp': '2026-09-28T10:00:00Z', 'message': {'id': 'same', 'model': 'model', 'content': 'secret sentinel', 'usage': {'input_tokens': 20, 'output_tokens': 2}}}
            path = Path(directory) / 'session.jsonl'
            first = json.dumps(row)
            row['message']['usage']['output_tokens'] = 8
            path.write_text(first + '\n' + json.dumps(row) + '\ninvalid')
            result = usage.aggregate(Path(directory), usage.instant('2026-09-28T00:00:00Z'), usage.instant('2026-09-29T00:00:00Z'))
            self.assertEqual(result['unique_requests'], 1)
            self.assertEqual(result['groups'][0]['output_tokens'], 8)
            self.assertNotIn('secret sentinel', json.dumps(result))
            self.assertEqual(result['malformed_rows'], 1)

    def test_invalid_metadata_is_counted_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [
                {'type': 'assistant', 'timestamp': 9},
                {'type': 'assistant', 'timestamp': '2026-09-28T10:00:00Z', 'message': {'id': [], 'model': 'model'}},
                {'type': 'assistant', 'timestamp': '2026-09-28T10:00:00Z', 'message': {'id': 'id', 'model': []}},
            ]
            (Path(directory) / 'bad.jsonl').write_text('\n'.join(json.dumps(row) for row in rows))
            result = usage.aggregate(Path(directory), usage.instant('2026-09-28T00:00:00Z'), usage.instant('2026-09-29T00:00:00Z'))
            self.assertEqual(result['unique_requests'], 0)
            self.assertEqual(result['malformed_rows'], 3)

    def test_timezone_is_required(self):
        with self.assertRaises(ValueError):
            usage.instant('2026-09-28T00:00:00')

# SYNTHETIC session fixture shared with the status tests (see its README): invented values.
FIXTURE = Path(__file__).resolve().parents[1] / 'graph_control/fixtures/sessions/project'
SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/session_usage.py'
DAY = (usage.instant('2026-09-28T00:00:00Z'), usage.instant('2026-09-29T00:00:00Z'))


def requests_by(result):
    return {(group['model'], group['bucket']): (group['requests'], group['output_tokens']) for group in result['groups']}


class FilterTests(unittest.TestCase):
    def test_session_keeps_its_main_thread_and_subagents(self):
        result = usage.aggregate(FIXTURE, *DAY, session='synthetic-session')
        self.assertEqual(result['unique_requests'], 8)
        self.assertEqual(requests_by(result), {('claude-opus-5-5', 'main'): (2, 18000),
                                               ('claude-opus-5-5', 'worker'): (4, 21200),
                                               ('claude-sonnet-5-5', 'worker'): (2, 9000)})
        self.assertEqual(result['filters'], {'session': 'synthetic-session', 'role': None, 'run': None})
        self.assertEqual(usage.aggregate(FIXTURE, *DAY)['unique_requests'], 10)

    def test_role_comes_from_meta_and_main_thread_is_main(self):
        implementer = usage.aggregate(FIXTURE, *DAY, session='synthetic-session', role='graph-engineering:implementer')
        self.assertEqual(requests_by(implementer), {('claude-opus-5-5', 'worker'): (3, 13200)})
        short = usage.aggregate(FIXTURE, *DAY, session='synthetic-session', role='implementer')
        self.assertEqual(requests_by(short), requests_by(implementer))
        main = usage.aggregate(FIXTURE, *DAY, session='synthetic-session', role='main')
        self.assertEqual(requests_by(main), {('claude-opus-5-5', 'main'): (2, 18000)})

    def test_run_matches_the_description_prefix(self):
        result = usage.aggregate(FIXTURE, *DAY, run='0192f3ab')
        self.assertEqual(result['unique_requests'], 5)
        self.assertEqual(requests_by(result), {('claude-opus-5-5', 'worker'): (4, 21200),
                                               ('claude-sonnet-5-5', 'worker'): (1, 5000)})

    def test_run_needs_the_colon_after_eight_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session/subagents/agent-a1.jsonl'
            path.parent.mkdir(parents=True)
            for description, run in (('Refactor login flow', None), ('0192f3ab:plan', '0192f3ab'), ('0192f3ab9:x', None)):
                path.with_suffix('.meta.json').write_text(json.dumps({'agentType': 'planner', 'description': description}))
                self.assertEqual(usage.identity(path), ('planner', run))

    def test_medians_per_role_per_agent(self):
        result = usage.aggregate(FIXTURE, *DAY, session='synthetic-session', medians_table=True)
        roles = {row.pop('role'): row for row in result['roles']}
        self.assertEqual(sorted(roles), ['graph-engineering:implementer', 'graph-engineering:implementer-simple',
                                         'graph-engineering:researcher', 'graph-engineering:reviewer', 'main'])
        self.assertEqual(roles['graph-engineering:implementer'], {
            'agents': 2, 'first_turn_input_median': 32602.0, 'output_median': 6600.0,
            'cache_read_median': 15000.0, 'cache_write_median': 32850.0})
        self.assertEqual(roles['main'], {'agents': 1, 'first_turn_input_median': 20010, 'output_median': 18000,
                                         'cache_read_median': 20000, 'cache_write_median': 21000})
        self.assertNotIn('roles', usage.aggregate(FIXTURE, *DAY, session='synthetic-session'))

    def test_cli_flags_and_privacy(self):
        command = [sys.executable, str(SCRIPT), '--root', str(FIXTURE), '--start', '2026-09-28T00:00:00Z',
                   '--end', '2026-09-29T00:00:00Z', '--session', 'synthetic-session', '--run', '0192f3ab',
                   '--role', 'reviewer', '--medians']
        done = subprocess.run(command, capture_output=True, text=True, check=True)
        result = json.loads(done.stdout)
        self.assertEqual(result['unique_requests'], 1)
        self.assertEqual([row['role'] for row in result['roles']], ['graph-engineering:reviewer'])
        for secret in ('SENTINEL-PROMPT-7f3a', 'SENTINEL-RESPONSE-9c1e', '0192f3ab:review'):
            self.assertNotIn(secret, done.stdout)
        bad = subprocess.run([*command[:8], '--run', '../x'], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)

if __name__ == '__main__':
    unittest.main()
