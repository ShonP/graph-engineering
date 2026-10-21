"""gate_checks.py: blocking and expiring advisory checks from graph-checks.json, one line each."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

GATE = Path(__file__).resolve().parents[1] / 'scripts' / 'gate_checks.py'


class GateChecks(unittest.TestCase):  # AC-GC-RUN
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def configure(self, *checks, **extra):
        (self.root / '.claude').mkdir(exist_ok=True)
        data = {'version': 1, **extra, **({'checks': list(checks)} if checks else {})}
        (self.root / '.claude/graph-checks.json').write_text(json.dumps(data))

    def stub(self, name, body):
        path = self.root / name
        path.write_text(f'#!/bin/sh\n{body}\n')
        path.chmod(0o755)
        return str(path)

    def gate(self, *args):
        return subprocess.run([sys.executable, str(GATE), str(self.root), *args], capture_output=True, text=True,
                              timeout=30)

    def advisory(self, ident, argv, expires='2026-11-01'):
        return {'id': ident, 'argv': argv, 'mode': 'advisory', 'expires': expires}

    def test_checks_move_from_pass_to_advisory_to_expired(self):
        passing, failing = self.stub('pass.sh', 'exit 0'), self.stub('fail.sh', 'echo dup-found; exit 1')
        self.configure({'id': 'types', 'argv': [passing], 'mode': 'blocking'},
                       self.advisory('dup-code', [self.stub('dup.sh', 'test -f broken && exit 1; exit 0')]),
                       self.advisory('dead-code', [passing]))
        result = self.gate('--today', '2026-10-21')
        self.assertEqual((result.returncode, result.stdout.splitlines()), (0, ['ok types', 'ok dup-code', 'ok dead-code']))
        (self.root / 'broken').write_text('')
        result = self.gate('--today', '2026-10-31')
        self.assertEqual((result.returncode, result.stdout.splitlines()),
                         (0, ['ok types', 'advisory dup-code failed, blocks from 2026-11-01', 'ok dead-code']))
        for today in ('2026-11-01', '2026-12-25'):
            result = self.gate('--today', today)
            self.assertEqual((result.returncode, result.stdout.splitlines()[1]), (2, 'FAIL dup-code expired 2026-11-01'))
            self.assertEqual(result.stdout.splitlines()[2], 'ok dead-code')
        self.configure(self.advisory('dup-code', [failing]))
        self.assertIn('dup-found', self.gate('--today', '2026-11-01').stdout)

    def test_blocking_failure_prints_exit_and_tail(self):
        lines = 'for i in $(seq 1 50); do echo line-$i; done; exit 3'
        self.configure({'id': 'types', 'argv': ['sh', '-c', lines], 'mode': 'blocking'},
                       {'id': 'lint', 'argv': ['true'], 'mode': 'blocking'})
        result = self.gate()
        head, *tail = result.stdout.splitlines()
        self.assertEqual((result.returncode, head, tail[-1]), (2, 'FAIL types exit=3', 'ok lint'))
        self.assertEqual(tail[:-1], [f'line-{i}' for i in range(31, 51)])

    def test_missing_program_fails(self):
        self.configure({'id': 'types', 'argv': ['graph-nonexistent-gate-check'], 'mode': 'blocking'})
        result = self.gate()
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout.startswith('FAIL types not found'), result.stdout)

    def test_timeout_kills_the_group_and_fails(self):
        marker = self.root / 'marker'
        self.configure({'id': 'slow', 'argv': ['sh', '-c', f'(sleep 4; touch {marker}) & wait'], 'mode': 'blocking',
                        'timeout_seconds': 1})
        started = time.monotonic()
        result = self.gate()
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual((result.returncode, result.stdout), (2, 'FAIL slow timeout\n'))
        time.sleep(5)
        self.assertFalse(marker.exists())

    def test_advisory_timeout_is_advisory_until_expiry(self):
        self.configure({**self.advisory('slow', ['sleep', '5']), 'timeout_seconds': 1})
        self.assertEqual(self.gate('--today', '2026-10-01').stdout, 'advisory slow failed, blocks from 2026-11-01\n')

    def test_cwd_is_the_root_and_stdin_is_closed(self):
        self.configure({'id': 'where', 'argv': ['sh', '-c', 'test -f .claude/graph-checks.json && ! read x'],
                        'mode': 'blocking'})
        self.assertEqual(self.gate().stdout, 'ok where\n')

    def test_nothing_to_run_exits_77(self):
        self.assertEqual(self.gate().returncode, 77)
        self.configure(test={'argv': ['true']})
        self.assertEqual(self.gate().returncode, 77)
        self.configure(checks=[])
        self.assertEqual((self.gate().returncode, self.gate().stdout), (77, ''))

    def test_invalid_config_and_usage_fail(self):
        self.configure({'id': 'Bad', 'argv': ['true'], 'mode': 'blocking'})
        result = self.gate()
        self.assertEqual(result.returncode, 2)
        self.assertIn('graph-checks.json is invalid', result.stderr)
        self.configure({'id': 'ok', 'argv': ['true'], 'mode': 'blocking'})
        self.assertEqual(self.gate('--today', '2026-13-01').returncode, 2)
        self.assertEqual(self.gate('--today', '2026-10-21').returncode, 0)


if __name__ == '__main__':
    unittest.main()
