"""Acceptance cases for the destructive-command guard (PreToolUse on Bash).

Every payload here is SYNTHETIC. Its shape follows the keys spike e observed in
a real Claude Code 2.1.285 PreToolUse(Bash) payload: tool_name,
tool_input.command and cwd. The oracle is the parsed hook output: exactly one
JSON object with permissionDecision "ask" and the rule's reason, or no output.

    python3 -m unittest discover -s hooks/tests -p 'test_guard_destructive.py' -v
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

GUARD = Path(__file__).resolve().parents[1] / 'scripts' / 'guard-destructive.sh'
BASH = shutil.which('bash') or '/bin/bash'
PREFIX = 'graph-engineering guard: '
SUFFIX = '. Approve only if this is intended.'
URL = 'https://example.invalid/fixture.git'
PARSE = 'could not parse this command; it matches a destructive pattern'


def stub(directory, name, body):
    path = Path(directory) / name
    path.write_text('#!/bin/sh\n' + body)
    path.chmod(0o755)


class GuardDestructive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name).resolve()
        cls.home = cls.root / 'home'
        cls.home.mkdir()
        cls.repo = cls.root / 'repo'
        (cls.repo / 'build').mkdir(parents=True)
        cls.git('init', '-q', '-b', 'main')
        cls.git('config', 'user.name', 'Guard fixture')
        cls.git('config', 'user.email', 'fixture@example.invalid')
        cls.git('commit', '-q', '--allow-empty', '-m', 'first')
        cls.remote_sha = cls.git('rev-parse', '--short=7', 'HEAD')
        cls.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        cls.git('commit', '-q', '--allow-empty', '-m', 'second')
        cls.local_sha = cls.git('rev-parse', '--short=7', 'HEAD')
        cls.git('remote', 'add', 'origin', URL)
        cls.git('remote', 'add', 'up', 'https://example.invalid/up.git')
        cls.git('remote', 'add', 'leak', 'https://bot:s3cr3t-token@example.invalid/x.git')
        cls.bin = cls.root / 'bin'
        cls.bin.mkdir()
        stub(cls.bin, 'docker', '[ "$1 $2 $3" = "volume ls -q" ] && printf "pg\\nredis\\ncache\\n" && exit 0\nexit 1\n')
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        cls.env.update(HOME=str(cls.home), PATH=f'{cls.bin}{os.pathsep}{os.environ["PATH"]}', GE_PYTHON=sys.executable)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def git(cls, *args):
        out = subprocess.run(['git', '-C', str(cls.repo), *args], check=True, capture_output=True, text=True)
        return out.stdout.strip()

    def run_guard(self, command, cwd=None, env=None, raw=None):
        payload = raw if raw is not None else json.dumps({
            'session_id': 'synthetic', 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
            'tool_input': {'command': command}, 'cwd': str(cwd or self.repo)})
        result = subprocess.run([BASH, str(GUARD)], input=payload, env=env or self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '', 'the guard must stay quiet on stderr')
        return result.stdout

    def reason(self, command, **kwargs):
        out = self.run_guard(command, **kwargs)
        self.assertEqual(len(out.strip().splitlines()), 1, f'expected one ask for {command!r}, got {out!r}')
        hso = json.loads(out)['hookSpecificOutput']
        self.assertEqual(hso['hookEventName'], 'PreToolUse')
        self.assertEqual(hso['permissionDecision'], 'ask')
        text = hso['permissionDecisionReason']
        self.assertTrue(text.startswith(PREFIX) and text.endswith(SUFFIX), text)
        return text[len(PREFIX):-len(SUFFIX)]

    def test_ac01_positives_ask_with_rule_reason(self):
        home, repo, docker = str(self.home), str(self.repo), os.path.realpath('/var/lib/docker')
        force = 'force push without --force-with-lease to '
        cases = [
            ('git remote remove origin', None, 'removes git remote origin ('),
            ('git remote rm up', None, 'removes git remote up ('),
            ('cd repo && git push --force origin main', self.root, force + 'origin main'),
            ('git push -f', None, force),
            ('git push origin +main', None, force + 'origin main'),
            ('FOO=1 git push --force', None, force),
            ('docker volume prune', None, 'deletes Docker volumes (3 present)'),
            ('docker volume rm pg', None, 'deletes Docker volumes (3 present)'),
            ('docker system prune -a --volumes', None, 'deletes Docker volumes (3 present)'),
            ('docker system prune -af', None, 'deletes Docker volumes (3 present)'),
            ('rm -rf /', None, 'recursive delete of / (filesystem root)'),
            ('rm -rf ~', None, f'recursive delete of {home} (home directory)'),
            ('rm -rf $HOME', None, f'recursive delete of {home} (home directory)'),
            ('rm -rf .git', None, f'recursive delete of {repo}/.git (git metadata directory)'),
            (f'rm -rf {repo}', self.root, f'recursive delete of {repo} (repository root)'),
            ('rm -fr /var/lib/docker', None, f'recursive delete of {docker} (Docker data directory)'),
            ('rm -rf ~/*', None, f'recursive delete of {home}/* (everything in the home directory)'),
        ]
        for command, cwd, expected in cases:
            with self.subTest(command=command):
                self.assertTrue(self.reason(command, cwd=cwd).startswith(expected))

    def test_ac02_negatives_are_silent(self):
        for command in [
            'git push', 'git push --force-with-lease', 'git push --force --force-with-lease',
            'git remote -v', 'git remote add x https://e.invalid/x.git', 'rm -rf node_modules',
            'rm -rf dist build', 'rm file.txt', 'rm -rf build/*', 'docker volume ls', 'docker ps', 'docker system prune -f',
            'docker compose -p ge-x down -v', "echo 'rm -rf /'", "git commit -m 'rm -rf /'",
            "cat > notes.txt <<'EOF'\nplease confirm it's fine to rm stuff\nEOF",
        ]:
            with self.subTest(command=command):
                self.assertEqual(self.run_guard(command), '')

    def test_ac03_remote_reason_carries_url_and_recovery(self):
        self.assertEqual(self.reason('git remote remove origin'),
                         f'removes git remote origin ({URL}); recover with: git remote add origin {URL}')

    def test_remote_url_credentials_never_printed(self):
        text = self.reason('git remote remove leak')
        self.assertNotIn('s3cr3t-token', text)
        self.assertIn('https://***@example.invalid/x.git', text)

    def test_force_push_evidence_names_both_shas(self):
        self.assertEqual(self.reason('cd repo && git push --force origin main', cwd=self.root),
                         f'force push without --force-with-lease to origin main '
                         f'(local {self.local_sha}, last known remote {self.remote_sha})')

    def test_ac04_compound_cd_tracking(self):
        self.assertTrue(self.reason(f'cd /tmp && rm -rf {self.repo}').endswith('(repository root)'))
        self.assertTrue(self.reason('cd repo && rm -rf .', cwd=self.root).endswith('(repository root)'))
        self.assertEqual(self.run_guard(f'cd {self.repo}/build && rm -rf .'), '')

    def test_wrapped_and_ancestor_targets_ask(self):
        for command, expected in [
            ('sudo rm -rf /', '(filesystem root)'), ('/bin/rm -r -f /', '(filesystem root)'),
            ('ls; rm --recursive ~', '(home directory)'), (f'rm -rf {self.root}', '(contains the home directory)'),
        ]:
            with self.subTest(command=command):
                self.assertTrue(self.reason(command).endswith(expected))

    def test_heredoc_body_skipped_but_following_lines_checked(self):
        self.assertEqual(self.run_guard("cat > x.sh <<'EOF'\nrm -rf /\nEOF"), '')
        self.assertTrue(self.reason('cat > x.sh <<-EOF\n\trm -rf /\n\tEOF\nrm -rf ~').endswith('(home directory)'))
        self.assertTrue(self.reason('cat <<< "done"\nrm -rf /').endswith('(filesystem root)'))

    def test_docker_unavailable_is_reported(self):
        broken = self.root / 'broken-bin'
        broken.mkdir(exist_ok=True)
        stub(broken, 'docker', 'exit 1\n')
        env = dict(self.env, PATH=f'{broken}{os.pathsep}{os.environ["PATH"]}')
        self.assertEqual(self.reason('docker volume prune', env=env), 'deletes Docker volumes (docker unavailable)')

    def test_ac05_fast_path_never_spawns_python(self):
        marked = self.root / 'marker-bin'
        marked.mkdir(exist_ok=True)
        marker = self.root / 'python-ran'
        stub(marked, 'python3', f'touch "{marker}"\nexec "{sys.executable}" "$@"\n')
        env = {k: v for k, v in self.env.items() if k != 'GE_PYTHON'}
        env['PATH'] = f'{marked}{os.pathsep}{env["PATH"]}'
        best = min(self.timed('npm test && ls -la', env) for _ in range(5))
        self.assertFalse(marker.exists(), 'a non-matching command spawned python')
        print(f'\n  fast path best of 5: {best * 1000:.1f} ms', file=sys.stderr)
        self.assertLess(best, 0.05)
        self.assertTrue(self.reason('rm -rf /', env=env))
        self.assertTrue(marker.exists(), 'control: the python3 stub was never used')

    def timed(self, command, env):
        start = time.perf_counter()
        self.assertEqual(self.run_guard(command, env=env), '')
        return time.perf_counter() - start

    def test_ac06_unparseable_asks_and_malformed_json_is_silent(self):
        self.assertEqual(self.reason('rm -rf "/'), PARSE)
        self.assertEqual(self.run_guard(None, raw='{"tool_input": {"command": "rm -rf /"'), '')
        self.assertEqual(self.run_guard(None, raw='["rm -rf /"]'), '')

    def test_no_python_runtime_fails_open(self):
        empty = self.root / 'empty-bin'
        empty.mkdir(exist_ok=True)
        env = {k: v for k, v in self.env.items() if k != 'GE_PYTHON'}
        env['PATH'] = str(empty)
        self.assertEqual(self.run_guard('rm -rf /', env=env), '')


if __name__ == '__main__':
    unittest.main()
