"""hygiene docs-age: ephemeral docs warn past ephemeralDays and error past twice that, by last commit date."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hygiene_fixture import commit_at, git, make_repo, stage, write_profile
from graph_control.commands import hygiene as command

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
PROFILE = 'hygiene:\n  docs:\n    ephemeral: ["docs/plans/**"]\n    ephemeralDays: 14\n'


class DocsAge(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = make_repo(self.tmp)
        self.profile = write_profile(self.root, PROFILE)

    def add(self, rel, days_ago, root=None):
        stage(root or self.root, rel, f"{rel}\n")
        return commit_at(root or self.root, f"add {rel}", days_ago, NOW)

    def check(self, *scope, root=None):
        parser = ArgumentParser()
        command.add_arguments(parser)
        args = parser.parse_args(["--root", str(root or self.root), "--profile", str(self.profile),
                                  *(scope or ("--tracked",)), "--only", "docs-age"])
        output = command.run(args, now=NOW)
        result = json.loads(output.text)
        self.assertEqual(output.exit_code, 1 if result["status"] == "FAIL" else 0)
        return result

    def found(self, *scope, root=None):
        return sorted((f["path"], f["level"], f["id"]) for f in self.check(*scope, root=root)["findings"])

    def test_ages_against_the_ephemeral_days(self):
        self.add("docs/plans/old.md", 29)
        self.add("docs/plans/stale.md", 20)
        self.add("docs/plans/fresh.md", 5)
        self.add("docs/specs/kept.md", 40)
        stage(self.root, "docs/plans/new.md", "uncommitted\n")
        result = self.check()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(self.found(), [("docs/plans/old.md", "error", "doc-ephemeral"),
                                        ("docs/plans/stale.md", "warn", "doc-ephemeral")])
        stale = next(f for f in result["findings"] if f["path"] == "docs/plans/stale.md")
        self.assertIn("20 days", stale["message"])
        self.assertIn("ephemeralDays 14", stale["message"])
        self.assertIn("delete it in the merge PR of the run that shipped it", stale["fix"])

    def test_warn_only_passes(self):
        self.add("docs/plans/stale.md", 20)
        self.assertEqual(self.check()["status"], "PASS")

    def test_no_globs_reports_nothing(self):
        self.profile = write_profile(self.root, "hygiene:\n  docs:\n    ephemeralDays: 14\n")
        self.add("docs/plans/old.md", 400)
        self.assertEqual(self.found(), [])

    def test_old_files_outside_the_globs_are_not_aged(self):
        self.add("docs/specs/kept.md", 400)
        self.add("README.md", 400)
        self.assertEqual(self.found(), [])

    def test_ephemeral_days_defaults_to_fourteen(self):
        self.profile = write_profile(self.root, 'hygiene:\n  docs:\n    ephemeral: ["docs/plans/**"]\n')
        self.add("docs/plans/a.md", 14)
        self.add("docs/plans/b.md", 15)
        self.add("docs/plans/c.md", 29)
        self.assertEqual(self.found(), [("docs/plans/b.md", "warn", "doc-ephemeral"),
                                        ("docs/plans/c.md", "error", "doc-ephemeral")])

    def test_boundaries_are_strict(self):
        self.add("docs/plans/at.md", 14)
        self.add("docs/plans/over.md", 15)
        self.add("docs/plans/twice.md", 28)
        self.add("docs/plans/past.md", 29)
        self.assertEqual(self.found(), [("docs/plans/over.md", "warn", "doc-ephemeral"),
                                        ("docs/plans/past.md", "error", "doc-ephemeral"),
                                        ("docs/plans/twice.md", "warn", "doc-ephemeral")])

    def test_last_commit_touching_the_file_counts(self):
        self.add("docs/plans/touched.md", 40)
        self.add("docs/other.md", 1)
        stage(self.root, "docs/plans/touched.md", "edited\n")
        commit_at(self.root, "edit", 3, NOW)
        self.assertEqual(self.found(), [])

    def test_committer_date_not_author_date(self):
        stage(self.root, "docs/plans/rebased.md", "rebased\n")
        env = {**os.environ, "GIT_AUTHOR_DATE": (NOW - timedelta(days=40)).isoformat(),
               "GIT_COMMITTER_DATE": (NOW - timedelta(days=2)).isoformat()}
        git(self.root, "commit", "-q", "-m", "rebased", env=env)
        stage(self.root, "docs/plans/authored.md", "authored\n")
        env = {**os.environ, "GIT_AUTHOR_DATE": (NOW - timedelta(days=2)).isoformat(),
               "GIT_COMMITTER_DATE": (NOW - timedelta(days=20)).isoformat()}
        git(self.root, "commit", "-q", "-m", "authored", env=env)
        self.assertEqual(self.found(), [("docs/plans/authored.md", "warn", "doc-ephemeral")])

    def test_base_reports_old_files_outside_the_diff(self):
        self.add("docs/plans/old.md", 29)
        self.add("docs/plans/stale.md", 20)
        git(self.root, "branch", "base")
        self.add("src/acme-widget.py", 1)
        self.assertEqual(self.found("--base", "base"), [("docs/plans/old.md", "error", "doc-ephemeral"),
                                                        ("docs/plans/stale.md", "warn", "doc-ephemeral")])

    def test_many_files_in_one_walk(self):
        for number in range(30):
            stage(self.root, f"docs/plans/p{number:02}.md", f"{number}\n")
            commit_at(self.root, f"plan {number}", 30 - number, NOW)
        found = self.found()
        self.assertEqual([path for path, level, _ in found if level == "error"],
                         [f"docs/plans/p{number:02}.md" for number in range(2)])
        self.assertEqual([path for path, level, _ in found if level == "warn"],
                         [f"docs/plans/p{number:02}.md" for number in range(2, 16)])

    def test_unusual_paths(self):
        self.add("docs/plans/with space é.md", 20)
        self.assertEqual(self.found(), [("docs/plans/with space é.md", "warn", "doc-ephemeral")])

    def test_rename_ages_from_the_rename(self):
        self.add("docs/plans/before.md", 40)
        git(self.root, "mv", "docs/plans/before.md", "docs/plans/after.md")
        commit_at(self.root, "rename", 2, NOW)
        self.assertEqual(self.found(), [])

    def test_shallow_clone_uses_the_oldest_available_date(self):
        self.add("docs/plans/old.md", 40)
        self.add("src/acme-widget.py", 3)
        clone = self.tmp / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{self.root}", str(clone)], check=True,
                       capture_output=True)
        self.assertEqual(git(clone, "rev-parse", "--is-shallow-repository"), "true")
        self.assertEqual(self.found(root=clone), [])

    def test_empty_repository(self):
        stage(self.root, "docs/plans/new.md", "uncommitted\n")
        self.assertEqual(self.found(), [])


if __name__ == "__main__":
    unittest.main()
