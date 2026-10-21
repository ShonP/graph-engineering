"""Acceptance cases for the commit hygiene guard (PreToolUse on Bash).

Payloads are SYNTHETIC, built on make-input.py's common fields. The allow cases put a
stub `uv` first on PATH that logs every call and prints a canned verdict. The deny
cases run the installed uv and the real `graph-control hygiene --staged`, and are
skipped without uv. A shim manager's `uv` would find the stub again, so the deny
cases never put the stub on PATH.

    python3 -m unittest discover -s hooks/tests -p 'test_guard_commit.py' -v
"""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
GUARD = HERE.parent / 'scripts' / 'guard-commit.sh'
BASH = shutil.which('bash') or '/bin/bash'
REAL_UV = shutil.which('uv')
PROFILE = 'name: acme-widget\n'
PNG = b'\x89PNG\r\n\x1a\nacme'
STUB = '''#!/bin/sh
printf '%s\\n' "$*" >> "$UV_LOG"
case "$UV_MODE" in
  pass) printf '{"findings": [], "status": "PASS"}\\n' ;;
  blocked) printf '{"reason": "profile cannot be read", "status": "BLOCKED"}\\n'; exit 1 ;;
  crash) echo 'Traceback (most recent call last)' >&2; exit 1 ;;
  garbage) echo 'not json'; exit 0 ;;
  mixed) printf '{"findings": [{"fix": "fix-w", "id": "home-path", "level": "warn", "message": "warn-w", "path": "w.md"}, {"fix": "fix-a", "id": "media-size", "level": "error", "message": "too big", "path": "a.bin"}], "status": "FAIL"}\\n'; exit 1 ;;
  warn) printf '{"findings": [{"fix": "f", "id": "home-path", "level": "warn", "line": 1, "message": "m", "path": "n.md"}], "status": "PASS"}\\n' ;;
esac
'''


def common_fields():
    spec = importlib.util.spec_from_file_location('make_input', HERE / 'make-input.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.COMMON


class GuardCommit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.repo = self.make_repo('repo')
        self.other = self.root / 'elsewhere'
        self.other.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'uv').write_text(STUB)
        (self.bin / 'uv').chmod(0o755)
        self.log = self.root / 'uv.log'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('GIT_', 'CLAUDE_'))}
        self.env.update(PATH=f'{self.bin}{os.pathsep}{os.environ["PATH"]}', GE_PYTHON=sys.executable,
                        CLAUDE_PROJECT_DIR=str(self.repo), UV_LOG=str(self.log), UV_MODE='pass')

    def tearDown(self):
        self.temp.cleanup()

    def make_repo(self, name, profile=PROFILE):
        repo = self.root / name
        (repo / '.claude').mkdir(parents=True)
        self.git(repo, 'init', '-q', '-b', 'main')
        self.git(repo, 'config', 'user.name', 'example-user')
        self.git(repo, 'config', 'user.email', 'example-user@api.example.test')
        if profile is not None:
            (repo / '.claude' / 'graph-profile.yaml').write_text(profile)
        self.git(repo, 'add', '-A')
        self.git(repo, 'commit', '-q', '--allow-empty', '-m', 'first')
        return repo

    @staticmethod
    def git(repo, *args):
        subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)

    def stage(self, rel, data, repo=None):
        repo = repo or self.repo
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.git(repo, 'add', '--', rel)

    def run_guard(self, command, cwd=None, mode='default', env=None):
        payload = dict(common_fields(), hook_event_name='PreToolUse', tool_name='Bash',
                       permission_mode=mode, tool_input={'command': command}, cwd=str(cwd or self.repo))
        result = subprocess.run([BASH, str(GUARD)], input=json.dumps(payload), env=env or self.env,
                                cwd=self.repo, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.stderr = result.stderr
        return result.stdout

    def deny(self, command, **kwargs):
        out = self.run_guard(command, **kwargs)
        self.assertEqual(len(out.strip().splitlines()), 1, f'expected one deny for {command!r}, got {out!r}')
        hso = json.loads(out)['hookSpecificOutput']
        self.assertEqual(hso['hookEventName'], 'PreToolUse')
        self.assertEqual(hso['permissionDecision'], 'deny')
        return hso['permissionDecisionReason']

    def uv_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def spellings(self):
        repo = shlex.quote(str(self.repo))
        return [('git commit -m x', self.repo), (f'git -C {repo} commit -m x', self.other),
                (f'cd {repo} && git commit -am x', self.other)]


@unittest.skipUnless(REAL_UV, 'uv is not installed: the deny path needs the real hygiene command')
class DenyPath(GuardCommit):
    def setUp(self):
        super().setUp()
        self.env['PATH'] = os.environ['PATH']
    def test_large_added_file_is_denied_then_allowed_after_unstaging(self):
        self.stage('assets/hero.bin', b'\0' * 600 * 1024)
        for command, cwd in self.spellings():
            with self.subTest(command=command):
                reason = self.deny(command, cwd=cwd)
                self.assertEqual(reason.count('assets/hero.bin: 600 KB > 500 KB'), 1, reason)
                self.assertNotIn('assets/hero.bin: assets/hero.bin', reason)
                self.assertIn('git rm --cached -- assets/hero.bin', reason)
        self.git(self.repo, 'rm', '-q', '--cached', '--', 'assets/hero.bin')
        for command, cwd in self.spellings():
            with self.subTest(command=command, staged=False):
                self.assertEqual(self.run_guard(command, cwd=cwd), '')

    def test_design_media_is_denied_then_allowed_after_unstaging(self):
        self.stage('docs/ux/flow.png', PNG)
        for command, cwd in self.spellings():
            with self.subTest(command=command):
                reason = self.deny(command, cwd=cwd)
                self.assertIn('docs/ux/flow.png is design media under docs/ux/', reason)
                self.assertIn('git rm --cached -- docs/ux/flow.png', reason)
        self.git(self.repo, 'rm', '-q', '--cached', '--', 'docs/ux/flow.png')
        for command, cwd in self.spellings():
            with self.subTest(command=command, staged=False):
                self.assertEqual(self.run_guard(command, cwd=cwd), '')

    def test_reason_names_at_most_three_findings(self):
        for n in range(4):
            self.stage(f'assets/big-{n}.bin', b'\0' * 600 * 1024)
        reason = self.deny('git commit -m x')
        self.assertEqual(reason.count('KB > 500 KB'), 3, reason)
        self.assertIn('1 more', reason)

    def test_commit_inside_a_substitution_and_after_env_prefix(self):
        self.stage('assets/hero.bin', b'\0' * 600 * 1024)
        repo = shlex.quote(str(self.repo))
        for command in (f'echo "$(git -C {repo} commit -m x)"', f'GIT_EDITOR=true git -C {repo} commit'):
            with self.subTest(command=command):
                self.assertIn('assets/hero.bin', self.deny(command, cwd=self.other))

    def test_bypass_permissions_still_denies(self):
        self.stage('assets/hero.bin', b'\0' * 600 * 1024)
        self.assertIn('assets/hero.bin', self.deny('git commit -m x', mode='bypassPermissions'))

    def test_amend_with_nothing_staged_and_warn_only_are_allowed(self):
        self.assertEqual(self.run_guard('git commit --amend --no-edit'), '')
        self.stage('notes/setup.md', b'see /Users/example-user/acme-widget\n')
        self.assertEqual(self.run_guard('git commit -m x'), '')
        self.assertEqual(self.stderr, '')

    def test_subdirectory_cwd_checks_the_repo_root(self):
        self.stage('assets/hero.bin', b'\0' * 600 * 1024)
        self.assertIn('assets/hero.bin', self.deny('git commit -m x', cwd=self.repo / 'assets'))


class AllowPath(GuardCommit):
    def test_non_commit_commands_start_no_uv(self):
        self.stage('assets/hero.bin', b'\0' * 600 * 1024)
        for command in ('git status', 'git log --grep commit', 'echo git commit', 'npm test',
                        'git diff -- commit.txt', 'grep -r commit .git'):
            with self.subTest(command=command):
                self.assertEqual(self.run_guard(command), '')
                self.assertEqual(self.stderr, '')
        self.assertEqual(self.uv_calls(), [])

    def test_fast_path_starts_no_interpreter(self):
        marker = self.root / 'ran-python'
        trap = self.root / 'python-trap'
        trap.write_text(f'#!/bin/sh\ntouch {shlex.quote(str(marker))}\nexit 1\n')
        trap.chmod(0o755)
        self.env['GE_PYTHON'] = str(trap)
        for command in ('git status', 'npm test && git push', 'npm run commit'):
            with self.subTest(command=command):
                self.assertEqual(self.run_guard(command), '')
        self.assertFalse(marker.exists())

    def test_reason_lists_errors_only_with_path_message_and_fix(self):
        self.env['UV_MODE'] = 'mixed'
        reason = self.deny('git commit -m x')
        self.assertEqual(reason, 'graph-engineering commit guard: a.bin: too big - fix-a')

    def test_stub_is_reached_for_a_commit(self):
        self.assertEqual(self.run_guard('git commit -am x'), '')
        self.assertEqual(len(self.uv_calls()), 1)
        self.assertIn('hygiene', self.uv_calls()[0])
        self.assertIn('--staged', self.uv_calls()[0])

    def test_no_project_profile_starts_no_uv(self):
        self.env['CLAUDE_PROJECT_DIR'] = str(self.other)
        self.assertEqual(self.run_guard('git commit -m x'), '')
        del self.env['CLAUDE_PROJECT_DIR']
        self.assertEqual(self.run_guard('git commit -m x'), '')
        self.assertEqual(self.uv_calls(), [])

    def test_target_repo_without_profile_starts_no_uv(self):
        bare = self.make_repo('no-profile', profile=None)
        self.stage('assets/hero.bin', b'\0' * 600 * 1024, repo=bare)
        self.assertEqual(self.run_guard(f'git -C {shlex.quote(str(bare))} commit -m x'), '')
        self.assertEqual(self.uv_calls(), [])

    def test_commit_aimed_at_another_repo_starts_no_uv(self):
        self.env['UV_MODE'] = 'mixed'
        bare = self.make_repo('no-profile', profile=None)
        self.stage('a.txt', b'a\n', repo=bare)
        other = shlex.quote(str(bare))
        for command in (f'git --git-dir={other}/.git --work-tree={other} commit -m x',
                        f'git --git-dir {other}/.git commit -m x', f'git --work-tree {other} commit -m x',
                        f'GIT_DIR={other}/.git git commit -m x', f'GIT_WORK_TREE={other} git commit -m x',
                        f'export GIT_DIR={other}/.git; git commit -m x'):
            with self.subTest(command=command):
                self.assertEqual(self.run_guard(command), '')
        self.assertEqual(self.uv_calls(), [])

    def test_git_missing_from_path_fails_open_without_a_traceback(self):
        no_git = self.root / 'no-git'
        no_git.mkdir()
        (no_git / 'uv').symlink_to(self.bin / 'uv')
        env = dict(self.env, PATH=str(no_git))
        self.assertEqual(self.run_guard('git commit -m x', env=env), '')
        self.assertNotIn('Traceback', self.stderr)

    def test_no_uv_on_path_fails_open(self):
        only_git = self.root / 'only-git'
        only_git.mkdir()
        (only_git / 'git').symlink_to(shutil.which('git'))
        env = dict(self.env, PATH=str(only_git))
        self.assertEqual(self.run_guard('git commit -m x', env=env), '')
        self.assertEqual(self.stderr, '')
        self.assertEqual(self.uv_calls(), [])

    def test_hygiene_errors_fail_open_and_say_so(self):
        for mode in ('blocked', 'crash', 'garbage'):
            with self.subTest(mode=mode):
                self.env['UV_MODE'] = mode
                self.assertEqual(self.run_guard('git commit -m x'), '')
                self.assertIn('commit allowed', self.stderr)

    def test_warn_only_findings_are_allowed(self):
        self.env['UV_MODE'] = 'warn'
        self.assertEqual(self.run_guard('git commit -m x'), '')
        self.assertEqual(self.stderr, '')

    def test_unparseable_or_missing_dir_fails_open(self):
        for command in ('git commit -m "x', 'git -C /nonexistent/acme-widget commit -m x'):
            with self.subTest(command=command):
                self.assertEqual(self.run_guard(command), '')
                self.assertEqual(self.stderr, '')
        self.assertEqual(self.uv_calls(), [])


if __name__ == '__main__':
    unittest.main()
