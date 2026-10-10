"""scripts/run-all-tests.sh: per-directory test pins and honest skip reporting.

Every repo here is a SYNTHETIC fixture: a copy of the runner, check scripts that
exit 0, one demo suite, and a stub `uv` first on PATH that logs its argv and
runs the command after `python` with this interpreter. No network, no real uv.

    python3 -m unittest discover -s tests/checks -p 'test_run_all_tests.py' -v
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).resolve().parents[2] / 'scripts' / 'run-all-tests.sh'
PASSING = 'import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n'
SKIPPING = PASSING + '\n    @unittest.skip("needs a missing dependency")\n    def test_skipped(self):\n        pass\n'


def write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


class RunAllTests(unittest.TestCase):
    def fixture(self, demo, requirements=None, skill_checks='exit 0\n',
                private_names='print("ok check-private-names")\n'):
        root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, root)
        write(root / 'scripts' / 'run-all-tests.sh', RUNNER.read_text(), 0o755)
        write(root / 'scripts' / 'graph-control.py', '# /// script\n# dependencies = ["PyYAML==6.0.2"]\n# ///\n')
        for name in ('check-skill-frontmatter', 'check-routing-resolves', 'check-agent-frontmatter'):
            write(root / 'scripts' / f'{name}.sh', 'exit 0\n', 0o755)
        write(root / 'scripts' / 'check-skill-scripts.sh', skill_checks, 0o755)
        write(root / 'scripts' / 'check-private-names.py', private_names)
        write(root / 'hooks' / 'tests' / 'run-tests.sh', 'exit 0\n', 0o755)
        write(root / 'hooks' / 'tests' / 'test_hooks_ok.py', PASSING)
        write(root / 'tests' / 'demo' / 'test_demo.py', demo)
        if requirements:
            write(root / 'tests' / 'demo' / 'requirements.txt', requirements)
        self.log = root / 'uv.log'
        write(root / 'bin' / 'uv', '#!/bin/sh\nprintf "%s\\n" "$*" >> "$UV_LOG"\n'
              'while [ "$#" -gt 0 ] && [ "$1" != python ]; do shift; done\nshift\n'
              'exec "$FIXTURE_PY" "$@"\n', 0o755)
        return root

    def run_all(self, root):
        env = dict(os.environ, PATH=f'{root / "bin"}{os.pathsep}{os.environ["PATH"]}',
                   UV_LOG=str(self.log), FIXTURE_PY=sys.executable)
        result = subprocess.run(['bash', str(root / 'scripts' / 'run-all-tests.sh')], env=env,
                                capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout.strip().splitlines()

    def test_clean_run_is_complete(self):
        code, lines = self.run_all(self.fixture(PASSING))
        self.assertEqual((code, lines[-1]), (0, 'run-all-tests: exit=0 complete'), lines)

    def test_a_skipped_test_reads_partial(self):
        code, lines = self.run_all(self.fixture(SKIPPING))
        self.assertEqual((code, lines[-1]), (0, 'run-all-tests: exit=0 partial'), lines)
        self.assertIn('tests/demo: exit=0 (tests skipped)', lines)

    def test_a_skip_line_from_a_check_reads_partial(self):
        checks = 'echo "ok   skills/a/tests/test_a.sh"; echo "SKIP skills/b/tests/test_b.sh (no docker)"\n'
        code, lines = self.run_all(self.fixture(PASSING, skill_checks=checks))
        self.assertEqual((code, lines[-1]), (0, 'run-all-tests: exit=0 partial'), lines)
        self.assertIn('check-skill-scripts: exit=0 (tests skipped)', lines)

    def test_private_names_check_runs_and_its_failure_fails_the_run(self):
        code, lines = self.run_all(self.fixture(PASSING))
        self.assertIn('check-private-names: exit=0', lines)
        code, lines = self.run_all(self.fixture(PASSING, private_names='raise SystemExit(1)\n'))
        self.assertEqual((code, lines[-1]), (1, 'run-all-tests: exit=1 complete'), lines)

    def test_unconfigured_private_names_reads_partial(self):
        skip = 'print("SKIP check-private-names: no list configured")\n'
        code, lines = self.run_all(self.fixture(PASSING, private_names=skip))
        self.assertEqual((code, lines[-1]), (0, 'run-all-tests: exit=0 partial'), lines)

    def test_directory_requirements_reach_uv(self):
        self.run_all(self.fixture(PASSING, requirements='wcmatch==11.0.1\n'))
        calls = self.log.read_text().splitlines()
        self.assertIn('run --with PyYAML==6.0.2 --with-requirements tests/demo/requirements.txt '
                      'python -m unittest discover -s tests/demo -p test_*.py', calls)

    def test_suite_without_requirements_gets_only_the_shared_pins(self):
        self.run_all(self.fixture(PASSING))
        self.assertEqual(self.log.read_text().splitlines(),
                         ['run --with PyYAML==6.0.2 python -m unittest discover -s tests/demo -p test_*.py'])


if __name__ == '__main__':
    unittest.main()
