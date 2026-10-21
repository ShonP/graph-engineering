"""hygiene private-names rule: unconfigured visibility, hits in scope and the doctor row."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from hygiene_fixture import commit_at, make_repo, stage, write_profile
from graph_control import cli
from graph_control.hygiene import Context, doctor_rows, iter_rules
from graph_control.hygiene.config import parse
from graph_control.hygiene.scope import staged, tracked

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
RULE = Path(__file__).resolve().parents[2] / "scripts" / "graph_control" / "hygiene" / "private_names.py"


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = make_repo(self.tmp)
        self.xdg = self.tmp / "xdg"
        self.xdg.mkdir()
        self.listed = self.xdg / "graph-engineering" / "private-names.txt"
        env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.xdg)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GRAPH_PRIVATE_NAMES", None)
        self.rule = {rule.ID: rule for rule in iter_rules()}["private-names"]

    def names_file(self, text):
        self.listed.parent.mkdir(parents=True, exist_ok=True)
        self.listed.write_text(text, encoding="utf-8")

    def findings(self, profile=None, mode="staged"):
        listing = {"staged": staged, "tracked": tracked}[mode]
        ctx = Context(root=self.root, config=parse(profile or {}), mode=mode, now=NOW,
                      files=tuple(listing(self.root)))
        return [(item.level, item.id, item.path, item.line) for item in self.rule.run(ctx)]

    def doctor(self, profile=None, quick=False):
        return [row for row in doctor_rows(profile or {}, self.root, quick) if row[1].startswith("private-name")]

    def invoke(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["hygiene", "--root", str(self.root), *argv, "--only", "private-names"])
        return code, json.loads(out.getvalue())


class Contract(Base):
    def test_rule_is_discovered_quick_with_its_modes(self):
        self.assertEqual(self.rule.MODES, frozenset({"staged", "base", "tracked", "doctor"}))
        self.assertIs(self.rule.QUICK, True)

    def test_the_matcher_is_imported_not_copied(self):
        source = RULE.read_text(encoding="utf-8")
        for copied in ("re.compile", "finditer", "fnmatch", "def names", "def seam", "def parse"):
            self.assertNotIn(copied, source)
        self.assertIn("check-private-names.py", source)


class Unconfigured(Base):
    def test_level_follows_the_profile_key(self):
        stage(self.root, "a.md", "clean\n")
        cases = [({}, [("warn", "private-names-unconfigured", None, None)]),
                 ({"hygiene": {"privateNames": "warn"}}, [("warn", "private-names-unconfigured", None, None)]),
                 ({"hygiene": {"privateNames": "error"}}, [("error", "private-names-unconfigured", None, None)]),
                 ({"hygiene": {"privateNames": "off"}}, [])]
        for profile, expected in cases:
            with self.subTest(profile=profile):
                self.assertEqual(self.findings(profile), expected)

    def test_finding_names_both_list_sources(self):
        [finding] = self.rule.run(Context(root=self.root, config=parse({}), mode="staged", now=NOW))
        self.assertIn("GRAPH_PRIVATE_NAMES", finding.fix)
        self.assertIn(str(self.listed), finding.fix)

    def test_a_comment_only_list_is_unconfigured(self):
        self.names_file("# a comment\n\n")
        self.assertEqual(self.findings(), [("warn", "private-names-unconfigured", None, None)])
        os.environ["GRAPH_PRIVATE_NAMES"] = "# none"
        self.assertEqual(self.findings(), [("warn", "private-names-unconfigured", None, None)])

    def test_cli_staged_warns_by_default_and_fails_on_error(self):
        stage(self.root, "a.md", "clean\n")
        code, out = self.invoke("--staged")
        self.assertEqual((code, out["status"]), (0, "PASS"))
        self.assertEqual([(f["level"], f["id"]) for f in out["findings"]], [("warn", "private-names-unconfigured")])
        write_profile(self.root, "hygiene:\n  privateNames: error\n")
        code, out = self.invoke("--staged")
        self.assertEqual((code, out["status"]), (1, "FAIL"))
        self.assertEqual([(f["level"], f["id"]) for f in out["findings"]], [("error", "private-names-unconfigured")])

    def test_doctor_warns_full_and_quick_with_a_fix_naming_both_sources(self):
        for quick in (False, True):
            with self.subTest(quick=quick):
                [(level, ident, message, fix)] = self.doctor(quick=quick)
                self.assertEqual((level, ident), ("warn", "private-names-unconfigured"))
                self.assertIn("GRAPH_PRIVATE_NAMES", fix)
                self.assertIn(str(self.listed), fix)
                self.assertTrue(message)

    def test_doctor_level_follows_the_key_and_off_has_no_row(self):
        self.assertEqual([row[0] for row in self.doctor({"hygiene": {"privateNames": "error"}})], ["error"])
        self.assertEqual(self.doctor({"hygiene": {"privateNames": "off"}}), [])

    def test_doctor_has_no_row_once_a_list_is_configured(self):
        self.names_file("acmewidget\n")
        self.assertEqual(self.doctor(), [])


class Configured(Base):
    def setUp(self):
        super().setUp()
        self.names_file("acmewidget\n")
        stage(self.root, "old.md", "uses acmewidget\n")
        commit_at(self.root, "base", 1, NOW)

    def test_staged_reports_only_the_new_hit_without_the_name(self):
        stage(self.root, "src/new.py", "x = 1\nAcmeWidget()\n")
        [finding] = self.rule.run(Context(root=self.root, config=parse({}), mode="staged", now=NOW,
                                          files=tuple(staged(self.root))))
        self.assertEqual((finding.level, finding.id, finding.path, finding.line),
                         ("error", "private-name", "src/new.py", 2))
        self.assertIn("src/new.py:2", finding.message)
        self.assertNotIn("acmewidget", (finding.message + finding.fix).lower())

    def test_tracked_reports_every_hit(self):
        stage(self.root, "src/new.py", "x = 1\nAcmeWidget()\n")
        self.assertEqual(self.findings(mode="tracked"),
                         [("error", "private-name", "old.md", 1), ("error", "private-name", "src/new.py", 2)])

    def test_a_clean_scope_has_no_finding(self):
        stage(self.root, "b.md", "clean\n")
        self.assertEqual(self.findings(), [])

    def test_path_hit_has_no_line(self):
        stage(self.root, "acmewidget/a.md", "clean\n")
        self.assertEqual(self.findings(), [("error", "private-name", "acmewidget/a.md", None)])

    def test_allow_globs_are_honoured_in_scope(self):
        self.names_file("acmewidget allow=vendor/*\n")
        stage(self.root, "vendor/a.md", "acmewidget\n")
        stage(self.root, "b.md", "acmewidget\n")
        self.assertEqual(self.findings(), [("error", "private-name", "b.md", 1)])

    def test_binary_file_text_is_skipped(self):
        stage(self.root, "blob.bin", b"\x00acmewidget\x00")
        self.assertEqual(self.findings(), [])

    def test_off_silences_hits(self):
        stage(self.root, "b.md", "acmewidget\n")
        self.assertEqual(self.findings({"hygiene": {"privateNames": "off"}}), [])
        self.assertEqual(self.findings({"hygiene": {"privateNames": "error"}}), [("error", "private-name", "b.md", 1)])


if __name__ == "__main__":
    unittest.main()
