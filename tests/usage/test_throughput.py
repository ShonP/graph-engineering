import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metrics = load('throughput_metrics')
signals = load('measure_signals')

# SYNTHETIC fixture; the expected values are hand-computed in its README.
FIXTURE = Path(__file__).resolve().parent / 'fixtures/throughput/project'
SCRIPT = SCRIPTS / 'throughput.py'
AT = '2026-09-30T00:00:00Z'
WINDOW = (metrics.instant('2026-09-16T00:00:00Z'), metrics.instant(AT))
SENTINELS = ('SENTINEL-PROMPT-thr7', 'SENTINEL-RESPONSE-thr9')


def run(*args, at=AT, root=FIXTURE):
    env = {key: value for key, value in os.environ.items() if key != 'GRAPH_MEASURE_AT'}
    if at is not None:
        env['GRAPH_MEASURE_AT'] = at
    return subprocess.run([sys.executable, str(SCRIPT), *args, '--root', str(root)],
                          capture_output=True, text=True, env=env, timeout=30)


class FunctionTests(unittest.TestCase):
    def test_active_seconds_counts_gaps_up_to_ten_minutes(self):
        self.assertEqual(metrics.active_seconds([0, 600, 1201, 1260]), 659)
        self.assertEqual(metrics.active_seconds([30, 0]), 30)
        self.assertEqual(metrics.active_seconds([5]), 0)

    def test_p90_is_nearest_rank(self):
        self.assertEqual(metrics.p90(list(range(1, 21))), 18)
        self.assertEqual(metrics.p90([15, 95, 40]), 95)
        self.assertEqual(metrics.p90([7]), 7)
        self.assertIsNone(metrics.p90([]))

    def test_concurrency_skips_single_agent_groups_and_idle_time_between_agents(self):
        span = metrics.Span
        spans = [span('a', 'g1', 0, 10, 0), span('a', 'g1', 20, 30, 0),
                 span('a', 'g2', 0, 10, 0), span('a', 'g2', 0, 10, 0), span('a', 'solo', 0, 99, 0),
                 span('a', None, 0, 10, 0), span('a', None, 0, 10, 0)]
        self.assertEqual(metrics.concurrency(spans), 1.5)
        self.assertIsNone(metrics.concurrency(spans[4:]))

    def test_spans_cover_the_window_by_last_timestamp(self):
        spans = sorted(metrics.agent_spans(FIXTURE, *WINDOW), key=lambda s: (s.first, s.last))
        self.assertEqual([(s.role, round(s.active / 60)) for s in spans],
                         [('graph-engineering:implementer', 15), ('graph-engineering:implementer', 95),
                          ('graph-engineering:implementer-simple', 120), ('graph-engineering:implementer', 40),
                          ('graph-engineering:reviewer', 30)])
        self.assertEqual([s.group for s in spans][:3], ['run:0192f3ab', 'run:0192f3ab', 'run:0192f3ac'])
        self.assertEqual(spans[3].group, spans[4].group)
        self.assertTrue(spans[3].group.endswith('wf_thr01'))

    def test_files_older_than_the_window_are_not_parsed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'project'
            shutil.copytree(FIXTURE, root)
            old = root / 'synthetic-session/subagents/agent-athr0002.jsonl'
            stamp = WINDOW[0].timestamp() - 1
            os.utime(old, (stamp, stamp))
            self.assertEqual(len(metrics.agent_spans(root, *WINDOW)), 4)


class CliTests(unittest.TestCase):
    """AC-TP-1 and AC-TP-2 against the README's oracle."""

    def assert_prints(self, metric, expected):
        result = run(metric)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected + '\n', ''))
        self.assertEqual(signals.scalar(result.stdout.encode()), float(expected))

    def test_metrics_print_the_readme_values(self):
        self.assert_prints('implementer-p90-active', '95.00')
        self.assert_prints('implementer-over-90', '2')
        self.assert_prints('workflow-concurrency', '1.53')

    def test_days_narrows_the_window(self):
        result = run('implementer-over-90', '--days', '1', at='2026-09-29T12:30:00+00:00')
        self.assertEqual(result.stdout, '1\n')
        # From 09-29 11:00: 95, 120 and 40 active minutes remain, so only the two long ones count.
        result = run('implementer-over-90', '--days', '1', at='2026-09-30T11:00:00Z')
        self.assertEqual(result.stdout, '2\n')

    def test_empty_window_is_no_data_never_a_fake_zero(self):
        for metric in ('implementer-p90-active', 'workflow-concurrency'):
            result = run(metric, at='2026-01-01T00:00:00Z')
            self.assertEqual((result.returncode, result.stdout), (1, ''))
            self.assertEqual(len(result.stderr.splitlines()), 1)
            self.assertIn(metric, result.stderr)
            self.assertIn('2026-01-01', result.stderr)
        result = run('implementer-over-90', at='2026-01-01T00:00:00Z')
        self.assertEqual((result.returncode, result.stdout), (0, '0\n'))

    def test_bad_input_exits_2(self):
        cases = [(('implementer-p90-active',), '2026-09-30T00:00:00'),
                 (('implementer-p90-active',), 'yesterday'),
                 (('unknown-metric',), AT),
                 (('implementer-over-90', '--days', '0'), AT),
                 (('implementer-over-90', '--days', '91'), AT)]
        for args, at in cases:
            with self.subTest(args=args, at=at):
                result = run(*args, at=at)
                self.assertEqual((result.returncode, result.stdout), (2, ''))
        self.assertEqual(run('implementer-over-90', root=FIXTURE / 'missing').returncode, 2)

    def test_default_end_is_now(self):
        result = run('implementer-over-90', '--days', '1', at=None)
        self.assertEqual((result.returncode, result.stdout), (0, '0\n'))

    def test_transcript_text_never_reaches_output(self):
        for metric in ('implementer-p90-active', 'implementer-over-90', 'workflow-concurrency'):
            for at in (AT, '2026-01-01T00:00:00Z'):
                result = run(metric, at=at)
                for sentinel in SENTINELS:
                    self.assertNotIn(sentinel, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
