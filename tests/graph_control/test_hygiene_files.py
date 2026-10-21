"""hygiene media and home-path rules over staged, base and tracked scopes."""

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from hygiene_fixture import commit_at, git, make_repo, stage
from graph_control.hygiene import Context, iter_rules, scope
from graph_control.hygiene import files as media
from graph_control.hygiene import home_paths
from graph_control.hygiene.config import parse
from graph_control.hygiene.scope import base, staged, tracked

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
KB = 1024
NO_LFS = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
PATHS = {"docsPath": "docs/specs", "uxEvidence": {"path": "docs/evidence"}}
STORE = {"docsPath": "docs/specs",
         "uxEvidence": {"path": "docs/evidence", "store": {"push": "acme-store push", "pull": "acme-store pull"}}}


def findings(rule, root, profile=None, mode="staged", rev=None):
    listing = {"staged": lambda: staged(root), "base": lambda: base(root, rev), "tracked": lambda: tracked(root)}
    ctx = Context(root=root, config=parse(profile or {}), mode=mode, now=NOW, files=tuple(listing[mode]()), base=rev)
    return rule.run(ctx)


def ids(rule, root, profile=None, mode="staged", rev=None):
    return sorted((item.level, item.id, item.path) for item in findings(rule, root, profile, mode, rev))


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_repo(Path(self.tmp.name))

    def commit(self, msg="base"):
        return commit_at(self.root, msg, 1, NOW)


class Contract(unittest.TestCase):
    def test_both_rules_are_discovered_with_their_modes(self):
        rules = {rule.ID: rule for rule in iter_rules()}
        self.assertEqual(rules["media"].MODES, frozenset({"staged", "base", "tracked"}))
        self.assertEqual(rules["home-paths"].MODES, frozenset({"staged", "base", "tracked"}))


class MediaSize(Repo):
    def test_added_file_over_the_limit_is_an_error_naming_path_and_sizes(self):
        stage(self.root, "assets/hero.bin", b"\0" * (513 * KB))
        [finding] = findings(media, self.root)
        self.assertEqual((finding.level, finding.id, finding.path), ("error", "media-size", "assets/hero.bin"))
        self.assertIn("assets/hero.bin", finding.message)
        self.assertIn("513 KB > 500 KB", finding.message)
        self.assertIn("hygiene.media.allow", finding.fix)
        self.assertIn("git rm --cached", finding.fix)

    def test_boundary_is_ceil_of_bytes_over_1024(self):
        stage(self.root, "assets/edge.bin", b"\0" * 512_000)
        self.assertEqual(findings(media, self.root), [])
        stage(self.root, "assets/edge.bin", b"\0" * 512_001)
        [finding] = findings(media, self.root)
        self.assertIn("501 KB > 500 KB", finding.message)

    def test_max_kb_moves_the_limit(self):
        stage(self.root, "assets/hero.bin", b"\0" * (513 * KB))
        self.assertEqual(findings(media, self.root, {"hygiene": {"media": {"max_kb": 600}}}), [])
        [finding] = findings(media, self.root, {"hygiene": {"media": {"max_kb": 100}}})
        self.assertIn("513 KB > 100 KB", finding.message)

    def test_allow_glob_exempts(self):
        stage(self.root, "vendor/lib/blob.bin", b"\0" * (600 * KB))
        self.assertEqual(findings(media, self.root, {"hygiene": {"media": {"allow": ["vendor/**"]}}}), [])

    def test_lfs_filtered_path_is_exempt(self):
        (self.root / ".gitattributes").write_text("*.psd filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
        (self.root / "art").mkdir()
        (self.root / "art/cover.psd").write_bytes(b"\0" * (600 * KB))
        git(self.root, "add", "--", ".gitattributes", "art/cover.psd", env=NO_LFS)
        self.assertEqual(findings(media, self.root), [])

    def test_modified_file_is_skipped_in_diff_scopes_and_swept_under_tracked(self):
        stage(self.root, "assets/old.bin", b"\0" * (600 * KB))
        first = self.commit()
        stage(self.root, "assets/old.bin", b"\1" * (600 * KB))
        self.assertEqual(findings(media, self.root), [])
        self.commit("change")
        self.assertEqual(findings(media, self.root, mode="base", rev=first), [])
        self.assertEqual(ids(media, self.root, mode="tracked"), [("error", "media-size", "assets/old.bin")])

    def test_added_file_is_reported_under_base(self):
        first = self.commit()
        stage(self.root, "assets/hero.bin", b"\0" * (513 * KB))
        self.commit("add")
        self.assertEqual(ids(media, self.root, mode="base", rev=first), [("error", "media-size", "assets/hero.bin")])

    def test_staged_rename_counts_as_added(self):
        stage(self.root, "assets/old.bin", b"\0" * (600 * KB))
        self.commit()
        git(self.root, "mv", "assets/old.bin", "assets/new.bin")
        self.assertEqual(ids(media, self.root), [("error", "media-size", "assets/new.bin")])

    def test_empty_staged_set_has_no_findings(self):
        self.commit()
        self.assertEqual(findings(media, self.root), [])

    def test_no_candidate_starts_no_attribute_lookup(self):
        stage(self.root, "src/app.txt", "small\n")
        files = tuple(staged(self.root))
        ctx = Context(root=self.root, config=parse({}), mode="staged", now=NOW, files=files)
        with mock.patch.object(scope.subprocess, "run", wraps=scope.subprocess.run) as spawn:
            self.assertEqual(media.run(ctx), [])
        self.assertEqual(spawn.call_count, 0)


class MediaPaths(Repo):
    def stage_set(self):
        stage(self.root, "docs/specs/ux/2026-01-01-f/to-be/home.png", b"\0" * (10 * KB))
        stage(self.root, "docs/specs/ux/2026-01-01-f/experience.md", "# Experience\n")
        stage(self.root, "docs/evidence/2026-01-01-f/after.png", b"\0" * KB)
        stage(self.root, "build/output/run.log", "ok\n")

    def test_design_evidence_and_deny_without_a_store(self):
        self.stage_set()
        profile = {**PATHS, "hygiene": {"media": {"deny": ["**/*.log"]}}}
        self.assertEqual(ids(media, self.root, profile), [
            ("error", "media-deny", "build/output/run.log"),
            ("error", "media-design", "docs/specs/ux/2026-01-01-f/to-be/home.png")])

    def test_evidence_media_is_an_error_when_a_store_is_set(self):
        self.stage_set()
        result = findings(media, self.root, STORE)
        self.assertEqual(sorted((item.level, item.id, item.path) for item in result), [
            ("error", "media-design", "docs/specs/ux/2026-01-01-f/to-be/home.png"),
            ("error", "media-evidence", "docs/evidence/2026-01-01-f/after.png")])
        evidence = next(item for item in result if item.id == "media-evidence")
        self.assertIn("uxEvidence.store", evidence.fix)
        design = next(item for item in result if item.id == "media-design")
        self.assertIn("git rm --cached", design.fix)

    def test_design_media_any_status_and_extension_case(self):
        stage(self.root, "docs/specs/ux/f/as-is/home.PNG", b"\0" * KB)
        self.commit()
        stage(self.root, "docs/specs/ux/f/as-is/home.PNG", b"\1" * KB)
        self.assertEqual(ids(media, self.root, PATHS), [("error", "media-design", "docs/specs/ux/f/as-is/home.PNG")])

    def test_default_paths_without_docs_path(self):
        stage(self.root, "docs/ux/f/to-be/home.webp", b"\0" * KB)
        stage(self.root, "docs/specs/ux/f/to-be/home.webp", b"\0" * KB)
        self.assertEqual(ids(media, self.root), [("error", "media-design", "docs/ux/f/to-be/home.webp")])

    def test_allow_exempts_path_rules(self):
        self.stage_set()
        profile = {**STORE, "hygiene": {"media": {"deny": ["**/*.log"], "allow": ["docs/**", "build/**"]}}}
        self.assertEqual(findings(media, self.root, profile), [])

    def test_enabled_false_turns_the_rule_off(self):
        self.stage_set()
        stage(self.root, "assets/hero.bin", b"\0" * (600 * KB))
        profile = {**STORE, "hygiene": {"media": {"enabled": False, "deny": ["**/*.log"]}}}
        self.assertEqual(findings(media, self.root, profile), [])
        self.assertEqual(findings(media, self.root, profile, mode="tracked"), [])


class HomePaths(Repo):
    def stage_set(self):
        stage(self.root, "notes/setup.md", "intro\n/home/example-user/x\nplain\nsee /Users/example-user/y\n")
        for skipped in ("app/fixtures/paths.txt", "app/test_widget.py", "app/widget_test.go", "web/widget.test.ts",
                        "tests/notes.txt", "CHANGELOG.md"):
            stage(self.root, skipped, "/home/example-user/x\n")
        stage(self.root, "assets/blob.bin", b"\0\1/home/example-user/x\n")
        stage(self.root, "notes/env.md", "$HOME/x\n~/x\n")

    def test_default_warns_at_each_path_line_without_the_name(self):
        self.stage_set()
        result = findings(home_paths, self.root)
        self.assertEqual([(item.level, item.id, item.path, item.line) for item in result],
                         [("warn", "home-path", "notes/setup.md", 2), ("warn", "home-path", "notes/setup.md", 4)])
        for item in result:
            self.assertIn("notes/setup.md", item.message)
            self.assertIn("names a home directory", item.message)
            self.assertNotIn("example-user", item.message + item.fix)

    def test_error_level_and_off(self):
        self.stage_set()
        levels = {item.level for item in findings(home_paths, self.root, {"hygiene": {"paths": {"home": "error"}}})}
        self.assertEqual(levels, {"error"})
        self.assertEqual(findings(home_paths, self.root, {"hygiene": {"paths": {"home": "off"}}}), [])

    def test_tracked_and_base_scopes(self):
        first = self.commit()
        stage(self.root, "notes/setup.md", "/Users/example-user/y\n")
        self.commit("add")
        self.assertEqual(ids(home_paths, self.root, mode="base", rev=first), [("warn", "home-path", "notes/setup.md")])
        self.assertEqual(ids(home_paths, self.root, mode="tracked"), [("warn", "home-path", "notes/setup.md")])


if __name__ == "__main__":
    unittest.main()
