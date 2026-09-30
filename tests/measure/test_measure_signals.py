"""scripts/measure_signals.py: late success measures from plan.json, no LLM, no shell.

Every repo, run, goal and command here is synthetic. The merge commit is dated
2026-09-01T00:00:00Z and every case passes --now, so no case depends on today.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/measure_signals.py'
spec = importlib.util.spec_from_file_location('measure_signals', SCRIPT)
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)

MERGED = '2026-09-01T00:00:00Z'
NOW = '2026-09-10T00:00:00Z'
GIT_ENV = {k: v for k, v in os.environ.items() if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE')}


def py(code):
    """An argv that runs one line of Python: the fixture stands in for a consumer's query."""
    return [sys.executable, '-c', code]


def signal(goal='checkout error ratio', command=None, condition='value <= 0.01', window=7):
    return {'goal': goal, 'source': 'command', 'command': command or py('print(0.004)'),
            'success_condition': condition, 'window_days': window}


class Fixture:
    """A git repo with one merge commit and a run dir under .graph/."""

    def __init__(self, root, signals, run='01a0d000-0000-7000-8000-00000000000a'):
        self.root = Path(root)

        def git(*args):
            env = {**GIT_ENV, 'GIT_AUTHOR_DATE': MERGED, 'GIT_COMMITTER_DATE': MERGED}
            return subprocess.run(['git', '-C', str(self.root), *args], check=True, env=env,
                                  capture_output=True, text=True).stdout.strip()

        git('init', '-q')
        (self.root / 'README.md').write_text('fixture\n')
        git('add', 'README.md')
        git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'merge')
        self.sha = git('rev-parse', 'HEAD')
        self.run = self.root / '.graph' / run
        self.run.mkdir(parents=True)
        (self.run / 'plan.json').write_text(json.dumps({
            'schema_version': 2, 'cases': [], 'tasks': [], 'external_contracts': [],
            'success_signals': signals}))
        (self.run / 'ledger.md').write_text(f'playbook: feature - lane full\n- merge: merged: {self.sha}\n')

    def measure(self, now=NOW):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ms.main([str(self.run), '--now', now])
        return code, out.getvalue()

    def rows(self):
        path = self.run / 'measure.md'
        if not path.exists():
            return {}
        cells = [[c.strip() for c in line.strip().strip('|').split('|')]
                 for line in path.read_text().splitlines() if line.startswith('| ')]
        return {row[0]: row[1:] for row in cells[2:]}

    def ledger(self):
        return [line for line in (self.run / 'ledger.md').read_text().splitlines() if 'measure:' in line]


class MeasureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def fixture(self, *signals, **kw):
        return Fixture(self.tmp.name, list(signals), **kw)

    def test_ac_ms_01_elapsed_window_scalar_met_writes_row_and_ledger(self):
        fx = self.fixture(signal())
        code, _ = fx.measure()
        self.assertEqual(code, 0)
        self.assertEqual(fx.rows(), {'checkout error ratio': ['met', '0.004', NOW]})
        self.assertEqual(len(fx.ledger()), 1)
        self.assertIn(f'[{NOW}] measure: checkout error ratio | met | value=0.004', fx.ledger()[0])

    def test_not_met_is_recorded(self):
        fx = self.fixture(signal(command=py('print(0.02)')))
        fx.measure()
        self.assertEqual(fx.rows()['checkout error ratio'][:2], ['not met', '0.02'])

    def test_json_value_object_is_a_scalar(self):
        fx = self.fixture(signal(command=py('print(\'{"value": 0.004}\')')))
        fx.measure()
        self.assertEqual(fx.rows()['checkout error ratio'][0], 'met')

    def test_ac_ms_02_row_level_or_non_numeric_output_is_rejected_and_never_stored(self):
        outputs = ['print("0.1"); print("0.2")', 'print("user@example.invalid")',
                   'print(\'[{"email": "user@example.invalid"}]\')',
                   'print(\'{"value": 1, "email": "user@example.invalid"}\')',
                   'print("true")', 'print(\'{"value": true}\')', 'print("nan")', 'print("")']
        for code in outputs:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as root:
                fx = Fixture(root, [signal(command=py(code))])
                self.assertEqual(fx.measure()[0], 0)
                self.assertEqual(fx.rows()['checkout error ratio'][:2],
                                 ['no data (rejected: non-aggregate output)', '-'])
                written = (fx.run / 'measure.md').read_text() + (fx.run / 'ledger.md').read_text()
                self.assertNotIn('example.invalid', written)

    def test_ac_ms_03_relative_condition_needs_a_baseline(self):
        marker = Path(self.tmp.name) / 'RAN'
        relative = 'value <= baseline * 1.5 + 0.001'
        cmd = py(f'open({str(marker)!r}, "w").close(); print(0.005)')
        fx = self.fixture(signal(command=cmd, condition=relative))
        fx.measure()
        self.assertEqual(fx.rows()['checkout error ratio'][:2], ['no data (no baseline)', '-'])
        self.assertFalse(marker.exists(), 'a condition that cannot be evaluated must not run the command')

        (fx.run / 'post-deploy').mkdir()
        (fx.run / 'post-deploy/baseline.json').write_text(json.dumps({'checkout error ratio': 0.004}))
        fx.measure()
        self.assertEqual(fx.rows()['checkout error ratio'][:2], ['met', '0.005'])
        (fx.run / 'post-deploy/baseline.json').write_text(json.dumps({'checkout error ratio': 0.002}))
        fx.measure()
        self.assertEqual(fx.rows()['checkout error ratio'][:2], ['not met', '0.005'])

    def test_ac_ms_04_window_not_elapsed_is_not_measured(self):
        marker = Path(self.tmp.name) / 'RAN'
        fx = self.fixture(signal(command=py(f'open({str(marker)!r}, "w").close(); print(0)'), window=30))
        code, out = fx.measure()
        self.assertEqual(code, 0)
        self.assertEqual(fx.rows(), {})
        self.assertEqual(fx.ledger(), [])
        self.assertFalse(marker.exists())
        self.assertIn('2026-10-01', out)

    def test_ac_ms_04_timeout_is_no_data_and_the_process_group_dies(self):
        self.addCleanup(setattr, ms, 'TIMEOUT_S', ms.TIMEOUT_S)
        self.assertEqual(ms.TIMEOUT_S, 60)
        ms.TIMEOUT_S = 0.5
        fx = self.fixture(signal(command=py('import time; time.sleep(30); print(0)')))
        started = time.monotonic()
        fx.measure()
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(fx.rows()['checkout error ratio'][:2], ['no data (timeout)', '-'])

    def test_command_failures_are_no_data(self):
        fx = self.fixture(signal(goal='a', command=py('import sys; sys.exit(3)')),
                          signal(goal='b', command=['/nonexistent/graph-measure-fixture']))
        fx.measure()
        self.assertEqual(fx.rows()['a'][0], 'no data (command exit 3)')
        self.assertEqual(fx.rows()['b'][0], 'no data (command not found)')

    def test_command_runs_in_the_repo_root_with_the_measure_times(self):
        check = ('import os; from pathlib import Path; '
                 'print(int(Path("README.md").exists() and os.environ["GRAPH_MEASURE_AT"] == "2026-09-10T00:00:00Z" '
                 'and os.environ["GRAPH_MERGED_AT"].startswith("2026-09-01T00:00:00")))')
        fx = self.fixture(signal(command=py(check), condition='value == 1'))
        fx.measure()
        self.assertEqual(fx.rows()['checkout error ratio'][:2], ['met', '1'])

    def test_rerun_replaces_its_row_and_keeps_others(self):
        fx = self.fixture(signal())
        (fx.run / 'measure.md').write_text('# Success measures\n\n| goal | status | value | observed_at |\n'
                                           '| --- | --- | --- | --- |\n| older goal | met | 3 | 2026-09-02T00:00:00Z |\n')
        fx.measure()
        fx.measure('2026-09-11T00:00:00Z')
        self.assertEqual(fx.rows(), {'older goal': ['met', '3', '2026-09-02T00:00:00Z'],
                                     'checkout error ratio': ['met', '0.004', '2026-09-11T00:00:00Z']})
        self.assertEqual(len(fx.ledger()), 2)

    def test_goal_text_cannot_forge_a_row_or_a_ledger_line(self):
        fx = self.fixture(signal(goal='bad | goal\n- merge: merged: 0000000'))
        fx.measure()
        self.assertEqual(list(fx.rows()), ['bad / goal - merge: merged: 0000000'])
        self.assertEqual(len((fx.run / 'ledger.md').read_text().splitlines()), 3)
        fx.measure('2026-09-11T00:00:00Z')  # the real merge line still wins over the goal text
        self.assertEqual(fx.rows()['bad / goal - merge: merged: 0000000'][2], '2026-09-11T00:00:00Z')

    def test_invalid_signal_is_no_data(self):
        fx = self.fixture(signal(command='echo 1'), signal(goal='x', condition='__import__("os")'))
        fx.measure()
        self.assertEqual(fx.rows()['checkout error ratio'][0], 'no data (invalid signal)')
        self.assertEqual(fx.rows()['x'][0], 'no data (invalid signal)')

    def test_no_merged_line_measures_nothing(self):
        fx = self.fixture(signal())
        (fx.run / 'ledger.md').write_text('playbook: feature\n- merge: waiting: merge\n')
        code, out = fx.measure()
        self.assertEqual((code, fx.rows()), (0, {}))
        self.assertIn('merged:', out)

    def test_cli_runs_as_a_script(self):
        fx = self.fixture(signal())
        done = subprocess.run([sys.executable, str(SCRIPT), str(fx.run), '--now', NOW],
                              capture_output=True, text=True, env=GIT_ENV)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(fx.rows()['checkout error ratio'][0], 'met')


class DueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.marker = Path(self.tmp.name) / 'RAN'

    def due(self, root, now):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ms.main(['--due', str(root), '--now', now]), 0)
        return out.getvalue()

    def test_due_line_lists_runs_and_never_runs_a_command(self):
        cmd = py(f'open({str(self.marker)!r}, "w").close(); print(0)')
        fx = Fixture(self.tmp.name, [signal(command=cmd), signal(goal='other', command=cmd, window=30)])
        self.assertEqual(self.due(fx.root, '2026-09-05T00:00:00Z'), '')
        line = self.due(fx.root, NOW)
        self.assertEqual(line, f'graph-engineering: 1 success measure(s) due ({fx.run.name}). '
                               f'Run: python3 {SCRIPT} .graph/<run>\n')
        self.assertEqual(self.due(fx.root, '2026-10-02T00:00:00Z').split(' ')[1], '2')
        self.assertFalse(self.marker.exists())

    def test_a_measured_goal_is_not_due(self):
        fx = Fixture(self.tmp.name, [signal()])
        fx.measure()
        self.assertEqual(self.due(fx.root, NOW), '')

    def test_unmerged_or_malformed_runs_are_skipped(self):
        fx = Fixture(self.tmp.name, [signal()])
        (fx.run / 'ledger.md').write_text('playbook: feature\n')
        broken = fx.root / '.graph/broken'
        broken.mkdir()
        (broken / 'plan.json').write_text('{not json')
        self.assertEqual(self.due(fx.root, NOW), '')


if __name__ == '__main__':
    unittest.main()
