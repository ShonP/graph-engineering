import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'plugin_shell_calls.py'
# SYNTHETIC fixture; the expected count is fixed by construction, see its README.
FIXTURE = Path(__file__).resolve().parent / 'fixtures/plugin_shell/project'
AT = '2026-09-30T00:00:00Z'
SENTINEL = 'SENTINEL-CMD-ps'


def run(*args, at=AT, root=FIXTURE):
    env = {key: value for key, value in os.environ.items() if key != 'GRAPH_MEASURE_AT'}
    if at is not None:
        env['GRAPH_MEASURE_AT'] = at
    return subprocess.run([sys.executable, str(SCRIPT), *args, '--root', str(root)],
                          capture_output=True, text=True, env=env, timeout=30)


class CountTests(unittest.TestCase):
    def test_fixture_counts_only_in_window_plugin_agent_violations(self):
        result = run('--days', '14')
        self.assertEqual((result.returncode, result.stdout), (0, '3\n'), result.stderr)

    def test_output_is_aggregate_only(self):
        result = run('--days', '14')
        for stream in (result.stdout, result.stderr):
            self.assertNotIn(SENTINEL, stream)
            self.assertNotIn('wait-run', stream)
            self.assertNotIn('/opt/ge', stream)
        self.assertLessEqual(len(result.stderr.splitlines()), 1)

    def test_malformed_lines_are_counted_on_stderr(self):
        self.assertIn('skipped 2 malformed', run('--days', '14').stderr)

    def test_wider_window_reaches_the_older_hit(self):
        self.assertEqual(run('--days', '30').stdout, '4\n')

    def test_default_window_is_fourteen_days(self):
        self.assertEqual(run().stdout, '3\n')

    def test_empty_tree_prints_zero(self):
        with tempfile.TemporaryDirectory() as empty:
            result = run(root=Path(empty))
        self.assertEqual((result.returncode, result.stdout), (0, '0\n'))

    def test_naive_or_bad_measure_at_exits_two(self):
        for at in ('2026-09-30T00:00:00', 'yesterday'):
            with self.subTest(at=at):
                result = run(at=at)
                self.assertEqual((result.returncode, result.stdout), (2, ''))
                self.assertIn('GRAPH_MEASURE_AT must be ISO 8601', result.stderr)

    def test_days_out_of_range_exits_two(self):
        for days in ('0', '91', 'x'):
            with self.subTest(days=days):
                result = run('--days', days)
                self.assertEqual((result.returncode, result.stdout), (2, ''))
                self.assertIn('--days', result.stderr)

    def test_days_bounds_are_accepted(self):
        for days in ('1', '90'):
            with self.subTest(days=days):
                self.assertEqual(run('--days', days).returncode, 0)

    def test_missing_root_exits_two(self):
        result = run(root=FIXTURE / 'absent')
        self.assertEqual(result.returncode, 2)
        self.assertIn('--root must be an existing directory', result.stderr)


if __name__ == '__main__':
    unittest.main()
