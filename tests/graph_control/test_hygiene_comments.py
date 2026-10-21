"""hygiene comments rule: comment-only lines a diff adds, per extension, with allow and cite escapes."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hygiene_fixture import commit_at, git, make_repo, stage
from graph_control.common import Invalid
from graph_control.hygiene import Context, iter_rules
from graph_control.hygiene.config import parse
from graph_control.hygiene.scope import base, staged

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
ALLOW = ["^#!", "noqa", "SPDX"]
NONE = {"hygiene": {"comments": {"mode": "none", "allow": ALLOW}}}
ADDED = {
    "src/a.ts": "const a = 1;\n// note\nconst b = a + 1; // trailing\n",
    "src/b.py": "import os  # trailing\n# note\n# noqa: E501\nu = \"http://x\"\n",
    "db/c.sql": "-- note\nselect 1; -- trailing\n",
    "ios/d.swift": "/* x */\nlet y = 2\n",
    "bin/e.sh": "#!/usr/bin/env bash\necho ok\n",
    "README.md": "# Heading\n<!-- note -->\n",
    "notes.txt": "# not code\n// nor this\n",
}
EXPECTED = [("error", "comment-added", "db/c.sql", 1), ("error", "comment-added", "ios/d.swift", 1),
            ("error", "comment-added", "src/a.ts", 2), ("error", "comment-added", "src/b.py", 2)]


class Repo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = make_repo(Path(tmp.name))
        self.rule = {rule.ID: rule for rule in iter_rules()}["comments"]

    def commit(self, msg="base"):
        return commit_at(self.root, msg, 1, NOW)

    def run_rule(self, profile=NONE, mode="staged", rev=None):
        files = staged(self.root) if mode == "staged" else base(self.root, rev)
        ctx = Context(root=self.root, config=parse(profile), mode=mode, now=NOW, files=tuple(files), base=rev)
        return self.rule.run(ctx)

    def rows(self, **kwargs):
        return sorted((item.level, item.id, item.path, item.line) for item in self.run_rule(**kwargs))

    def add_all(self, files=None):
        for rel, text in (files or ADDED).items():
            stage(self.root, rel, text)


class Contract(unittest.TestCase):
    def test_rule_is_discovered_for_staged_and_base(self):
        rule = {rule.ID: rule for rule in iter_rules()}["comments"]
        self.assertEqual(rule.MODES, frozenset({"staged", "base"}))
        self.assertIs(rule.QUICK, False)

    def test_cite_defaults_on_and_takes_a_boolean(self):
        self.assertIs(parse({}).comments.cite, True)
        self.assertIs(parse({"hygiene": {"comments": {"cite": False}}}).comments.cite, False)
        with self.assertRaisesRegex(Invalid, "hygiene.comments.cite"):
            parse({"hygiene": {"comments": {"cite": "yes"}}})


class Staged(Repo):
    def test_the_four_comment_only_lines_are_errors_at_path_and_line(self):
        stage(self.root, "src/a.ts", "// old\n")
        self.commit()
        self.add_all()
        self.assertEqual(self.rows(), EXPECTED)

    def test_message_names_path_line_and_fix_documents_the_escapes(self):
        stage(self.root, "src/a.ts", "// note\n")
        [finding] = self.run_rule()
        self.assertIn("src/a.ts:1", finding.message)
        self.assertIn("trailing comments after code are not checked", finding.fix)
        self.assertIn("hygiene.comments.allow", finding.fix)
        self.assertIn("comments.mode: any", finding.fix)

    def test_mode_any_gives_nothing(self):
        self.add_all()
        self.assertEqual(self.rows(profile={"hygiene": {"comments": {"mode": "any", "allow": ALLOW}}}), [])
        self.assertEqual(self.rows(profile={}), [])

    def test_unborn_branch_reads_the_index(self):
        stage(self.root, "src/a.ts", "x;\n  /** doc\n   * more\n   */\n")
        self.assertEqual([row[3] for row in self.rows()], [2, 3, 4])

    def test_empty_diff_gives_nothing(self):
        stage(self.root, "src/a.ts", "// old\n")
        self.commit()
        self.assertEqual(self.rows(), [])

    def test_pre_existing_comment_is_never_reported_and_lines_follow_the_hunks(self):
        stage(self.root, "src/k.kt", "".join(f"val v{n} = {n}\n" for n in range(1, 7)) + "// old\n")
        self.commit()
        lines = (Path(self.root) / "src/k.kt").read_text().split("\n")
        lines.insert(1, "// one")
        lines.insert(5, "    // two")
        stage(self.root, "src/k.kt", "\n".join(lines))
        self.assertEqual([row[3] for row in self.rows()], [2, 6])

    def test_removed_and_unchanged_comments_give_nothing(self):
        stage(self.root, "src/a.go", "// old\npackage a\n")
        self.commit()
        stage(self.root, "src/a.go", "package a\n")
        self.assertEqual(self.rows(), [])

    def test_hash_family_extensions(self):
        files = {f"x.{ext}": "# note\n" for ext in ("py", "sh", "bash", "rb", "yaml", "yml", "toml")}
        self.add_all(files)
        self.assertEqual([row[2] for row in self.rows()], sorted(files))

    def test_slash_family_and_dash_family_extensions(self):
        slash = ("ts", "tsx", "js", "jsx", "swift", "kt", "kts", "java", "go", "rs", "c", "h", "cpp", "cs", "css")
        files = {f"y.{ext}": "a\n// one\n/* two\n * three\n */\n" for ext in slash}
        files.update({"z.sql": "-- one\n", "z.lua": "-- one\n"})
        self.add_all(files)
        flagged = self.rows()
        self.assertEqual(len(flagged), 4 * len(slash) + 2)
        self.assertEqual({row[2] for row in flagged}, set(files))

    def test_wrong_family_marker_is_not_a_comment(self):
        self.add_all({"p.py": "// x\n-- y\n", "q.ts": "# x\n-- y\n", "r.sql": "# x\n// y\n", "s.css": "#id { }\n"})
        self.assertEqual(self.rows(), [])

    def test_dotted_directory_without_an_extension_is_skipped(self):
        self.add_all({"conf.d/run": "# note\n", "Makefile": "# note\n"})
        self.assertEqual(self.rows(), [])

    def test_an_invalid_allow_regex_is_a_profile_error(self):
        stage(self.root, "src/a.ts", "// note\n")
        with self.assertRaisesRegex(Invalid, r"hygiene\.comments\.allow.*'\('"):
            self.run_rule(profile={"hygiene": {"comments": {"mode": "none", "allow": ["("]}}})

    def test_path_with_spaces_and_unicode(self):
        stage(self.root, "src/dir one/café file.ts", "x;\n// note\n")
        self.assertEqual(self.rows(), [("error", "comment-added", "src/dir one/café file.ts", 2)])

    def test_triple_quoted_hash_line_is_a_known_false_positive_cleared_by_allow(self):
        stage(self.root, "src/t.py", 'DOC = """\n# Title in a string\n"""\n')
        self.assertEqual([row[3] for row in self.rows()], [2])
        profile = {"hygiene": {"comments": {"mode": "none", "allow": ["^# Title"]}}}
        self.assertEqual(self.rows(profile=profile), [])


class Cite(Repo):
    TEXT = "x;\n// see https://api.example.test/issues/12 for why\n// plain\n"

    def test_a_comment_citing_a_url_passes_by_default(self):
        stage(self.root, "src/a.ts", self.TEXT)
        self.assertEqual([row[3] for row in self.rows()], [3])

    def test_cite_false_reports_the_url_comment_too(self):
        stage(self.root, "src/a.ts", self.TEXT)
        profile = {"hygiene": {"comments": {"mode": "none", "cite": False}}}
        self.assertEqual([row[3] for row in self.rows(profile=profile)], [2, 3])

    def test_a_url_in_code_is_code(self):
        stage(self.root, "src/b.py", 'u = "http://x"\nv = "https://api.example.test"  # see link\n')
        profile = {"hygiene": {"comments": {"mode": "none", "cite": False}}}
        self.assertEqual(self.rows(profile=profile), [])


class Base(Repo):
    def test_base_mode_reads_commits_since_the_merge_base(self):
        stage(self.root, "src/a.ts", "// old\n")
        rev = self.commit()
        self.add_all()
        self.commit("work")
        self.assertEqual(self.rows(mode="base", rev=rev), EXPECTED)

    def test_base_mode_ignores_uncommitted_and_main_side_changes(self):
        stage(self.root, "src/a.ts", "x;\n")
        self.commit()
        git(self.root, "checkout", "-q", "-b", "work")
        stage(self.root, "src/b.ts", "// mine\n")
        self.commit("work")
        git(self.root, "checkout", "-q", "main")
        stage(self.root, "src/m.ts", "// main side\n")
        self.commit("main side")
        git(self.root, "checkout", "-q", "work")
        stage(self.root, "src/b.ts", "// mine\n// staged only\n")
        self.assertEqual(self.rows(mode="base", rev="main"), [("error", "comment-added", "src/b.ts", 1)])


if __name__ == "__main__":
    unittest.main()
