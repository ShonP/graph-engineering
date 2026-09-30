#!/usr/bin/env python3
"""SessionStart doctor hook (AC-W2-DR-04) and its registration (AC-W2-DR-05).

Stdlib only. Run from any directory:

    python3 hooks/tests/test_doctor_on_start.py

Drives hooks/scripts/doctor-on-start.sh the way Claude Code does: the event's
JSON on stdin, CLAUDE_PROJECT_DIR in the environment, a working directory
unrelated to the project. `uv` is a stub first on PATH that logs its argv and
prints a canned doctor report, so the log is the oracle for "the cache hit
started no doctor". Every fixture repo is synthetic and lives in a temp dir.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent
PLUGIN = HOOKS.parent
SCRIPT = HOOKS / "scripts" / "doctor-on-start.sh"
VERSION = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())["version"]
HINT = "graph-engineering: this repo has no .claude/graph-profile.yaml. The owner can run /graph-init to set it up."
MARKERS = ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "Package.swift", "build.gradle",
           "build.gradle.kts", "pom.xml", "Gemfile")
STUB = '#!/bin/sh\nprintf \'%s\\n\' "$*" >>"$STUB_LOG"\ncat "$STUB_OUT"\nexit "${STUB_RC:-0}"\n'
CLEAN = {"status": "PASS", "findings": []}


def finding(level, ident, message, fix="do the fix"):
    return {"level": level, "id": ident, "message": message, "fix": fix}


def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


class Hook(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name).resolve()
        self.bin = self.work / "bin"
        self.bin.mkdir()
        (self.bin / "uv").write_text(STUB)
        (self.bin / "uv").chmod(0o755)
        self.log, self.out = self.work / "uv.log", self.work / "uv.out"
        self.report(CLEAN)

    def report(self, data, rc=0):
        self.out.write_text(data if isinstance(data, str) else json.dumps(data))
        self.rc = rc

    def repo(self, name="repo", profile=True):
        path = self.work / name
        git("init", "-q", str(path))
        if profile:
            (path / ".claude").mkdir()
            (path / ".claude" / "graph-profile.yaml").write_text("schema_version: 2\n")
        return path

    def run_hook(self, project, path=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        env.update(PATH=path or f"{self.bin}{os.pathsep}{os.environ['PATH']}", STUB_LOG=str(self.log),
                   STUB_OUT=str(self.out), STUB_RC=str(self.rc), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        if project is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project)
        stdin = json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(project)})
        result = subprocess.run(["bash", str(SCRIPT)], input=stdin, env=env, cwd=self.work,
                                capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []


class NoProfile(Hook):
    def test_stack_marker_prints_the_init_hint(self):
        for marker in MARKERS:
            with self.subTest(marker):
                project = self.repo(marker.replace(".", "-"), profile=False)
                (project / marker).write_text("")
                self.assertEqual(self.run_hook(project), HINT + "\n")
        self.assertEqual(self.calls(), [])

    def test_no_stack_marker_is_silent(self):
        project = self.repo(profile=False)
        (project / "README.md").write_text("# notes\n")
        self.assertEqual(self.run_hook(project), "")

    def test_not_a_git_repo_is_silent(self):
        project = self.work / "scratch"
        (project / ".claude").mkdir(parents=True)
        (project / "package.json").write_text("{}")
        (project / ".claude" / "graph-profile.yaml").write_text("schema_version: 1\n")
        self.assertEqual(self.run_hook(project), "")
        self.assertEqual(self.calls(), [])

    def test_unset_project_dir_is_silent(self):
        self.assertEqual(self.run_hook(None), "")


class WithProfile(Hook):
    def cache(self, project):
        return project / ".git" / "graph-engineering" / "doctor-cache"

    def test_clean_profile_is_cached_and_the_second_run_never_starts_uv(self):
        project = self.repo()
        self.assertEqual(self.run_hook(project), "")
        self.assertEqual(self.calls(), [f"run --quiet --script {PLUGIN}/scripts/graph-control.py doctor "
                                        f"--root {project} --quick"])
        self.assertIn(VERSION, self.cache(project).read_text())
        self.assertEqual(self.run_hook(project), "")
        self.assertEqual(len(self.calls()), 1, "a cache hit started the doctor")

    def test_findings_print_errors_first_and_are_not_cached(self):
        project = self.repo()
        self.report({"status": "PASS", "findings": [
            finding("warn", "checks-missing", "no checks file", "copy the template"),
            finding("error", "profile-invalid", "bad YAML:\n  line 3", "fix the YAML"),
            finding("info", "cannot-determine", "unknown version")]})
        self.assertEqual(self.run_hook(project).splitlines(), [
            "graph-engineering doctor: bad YAML: line 3 - fix: fix the YAML",
            "graph-engineering doctor: no checks file - fix: copy the template"])
        self.assertFalse(self.cache(project).exists())
        self.run_hook(project)
        self.assertEqual(len(self.calls()), 2)

    def test_at_most_three_lines(self):
        project = self.repo()
        self.report({"status": "PASS", "findings": [finding("warn", f"w{n}", f"warning {n}") for n in range(5)]})
        self.assertEqual(self.run_hook(project).splitlines(), [
            "graph-engineering doctor: warning 0 - fix: do the fix",
            "graph-engineering doctor: warning 1 - fix: do the fix",
            "graph-engineering doctor: 3 more findings - fix: run /graph-doctor"])

    def test_info_only_is_silent_and_cached(self):
        project = self.repo()
        self.report({"status": "PASS", "findings": [finding("info", "cannot-determine", "unknown version")]})
        self.assertEqual(self.run_hook(project), "")
        self.run_hook(project)
        self.assertEqual(len(self.calls()), 1)

    def test_profile_or_checks_change_misses_the_cache(self):
        project = self.repo()
        profile = project / ".claude" / "graph-profile.yaml"
        self.run_hook(project)
        stamp = profile.stat().st_mtime
        os.utime(profile, (stamp + 10, stamp + 10))
        self.run_hook(project)
        (project / ".claude" / "graph-checks.json").write_text('{"version": 1}')
        self.run_hook(project)
        self.run_hook(project)
        self.assertEqual(len(self.calls()), 3)

    def test_linked_worktrees_share_one_cache_file_with_an_entry_each(self):
        main = self.repo()
        git("-C", str(main), "add", ".claude")
        git("-C", str(main), "-c", "user.email=t@example.invalid", "-c", "user.name=T", "-c", "commit.gpgsign=false",
            "commit", "-qm", "fixture")
        linked = self.work / "linked"
        git("-C", str(main), "worktree", "add", "-q", str(linked))
        for project in (main, linked, main, linked):
            self.run_hook(project)
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(len(self.cache(main).read_text().splitlines()), 2)

    def test_a_failing_or_garbled_doctor_is_silent_and_uncached(self):
        project = self.repo()
        for report, rc in ((json.dumps({"status": "BLOCKED", "reason": "x"}), 1), ("not json", 0),
                           (json.dumps({"status": "BLOCKED", "reason": "x"}), 0)):
            with self.subTest(report=report, rc=rc):
                self.report(report, rc)
                self.assertEqual(self.run_hook(project), "")
                self.assertFalse(self.cache(project).exists())

    def test_no_uv_on_path_is_silent(self):
        path = "/usr/bin:/bin"
        if shutil.which("uv", path=path):
            self.skipTest("uv is installed in /usr/bin or /bin")
        self.assertEqual(self.run_hook(self.repo(), path=path), "")


class Registration(unittest.TestCase):  # AC-W2-DR-05
    longMessage = False  # a README miss names the needle, not the whole file

    def test_sessionstart_doctor_entry_is_startup_only(self):
        hooks = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(sorted(hooks), ["PostToolUse", "PreToolUse", "SessionStart", "Stop"])
        root = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/"
        self.assertEqual(hooks["SessionStart"], [
            {"matcher": "startup|clear|compact",
             "hooks": [{"type": "command", "command": root + "print-handoff.sh", "args": [], "timeout": 15}]},
            {"matcher": "startup",
             "hooks": [{"type": "command", "command": root + "doctor-on-start.sh", "args": [], "timeout": 5}]}])

    def test_script_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_readme_documents_the_hook(self):
        text = (HOOKS / "README.md").read_text(encoding="utf-8")
        for needle in ("doctor-on-start.sh", "doctor-cache", "/graph-doctor", "/graph-init", "--quick"):
            self.assertIn(needle, text, "README lacks: " + needle)


if __name__ == "__main__":
    unittest.main(verbosity=2)
