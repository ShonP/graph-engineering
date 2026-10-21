"""hygiene literals rule: stray copies of a single-owner fact, scope, skips and the doctor rows."""

import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone

from hygiene_fixture import commit_at, make_repo, stage, write_profile
from graph_control import cli
from graph_control.hygiene import Context, doctor_rows, iter_rules
from graph_control.hygiene.config import parse
from graph_control.hygiene.scope import staged, tracked

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
HOST = "api.example.test"
ROW = {"id": "app-host", "pattern": r"api\.example\.test", "owner": ["config/**"], "allow": ["docs/**"]}


def profile(*rows):
    return {"hygiene": {"literals": list(rows)}}


def row(pattern, ident="app-host"):
    return {**ROW, "id": ident, "pattern": pattern}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = make_repo(tmp.name)
        self.rule = {rule.ID: rule for rule in iter_rules()}["literals"]

    def run_rule(self, config, mode="tracked"):
        listing = {"staged": staged, "tracked": tracked}[mode]
        ctx = Context(root=self.root, config=parse(config), mode=mode, now=NOW, files=tuple(listing(self.root)))
        return self.rule.run(ctx)

    def findings(self, config, mode="tracked"):
        return [(item.level, item.id, item.path, item.line) for item in self.run_rule(config, mode)]

    def doctor(self, config, quick=False):
        return [entry for entry in doctor_rows(config, self.root, quick) if entry[1].startswith("hygiene-literal")]


class Contract(Base):
    def test_rule_is_discovered_quick_with_its_modes(self):
        self.assertEqual(self.rule.MODES, frozenset({"staged", "base", "tracked", "doctor"}))
        self.assertIs(self.rule.QUICK, True)


class Stray(Base):
    def setUp(self):
        super().setUp()
        stage(self.root, "config/hosts.ts", f"export const HOST = '{HOST}'\n")
        stage(self.root, "src/a.ts", f"a\nb\nc\nfetch('https://{HOST}/v1')\n")
        stage(self.root, "docs/x.md", f"The app talks to {HOST}.\n")
        stage(self.root, "tests/fixtures/f.json", f'{{"host": "{HOST}"}}\n')

    def test_only_the_stray_copy_is_an_error(self):
        self.assertEqual(self.findings(profile(ROW)), [("error", "literal-stray", "src/a.ts", 4)])

    def test_message_names_place_row_and_owner_but_never_the_text(self):
        [finding] = self.run_rule(profile(ROW))
        self.assertIn("src/a.ts:4", finding.message)
        self.assertIn("app-host", finding.message)
        self.assertIn("config/**", finding.message)
        self.assertNotIn(HOST, finding.message + finding.fix)

    def test_no_rows_is_off(self):
        self.assertEqual(self.findings({}), [])
        self.assertEqual(self.findings(profile()), [])

    def test_default_test_skips(self):
        for path in ("pkg/tests/b.ts", "src/test_b.py", "src/b.test.ts", "pkg/fixtures/b.json"):
            stage(self.root, path, f"{HOST}\n")
        self.assertEqual(self.findings(profile(ROW)), [("error", "literal-stray", "src/a.ts", 4)])

    def test_allow_defaults_to_nothing(self):
        bare = {key: value for key, value in ROW.items() if key != "allow"}
        self.assertEqual(self.findings(profile(bare)),
                         [("error", "literal-stray", "docs/x.md", 1), ("error", "literal-stray", "src/a.ts", 4)])

    def test_each_row_reports_its_own_id(self):
        second = {"id": "consent-version", "pattern": r"consent-v[0-9]+", "owner": ["legal/**"]}
        stage(self.root, "src/c.ts", "x\nconsent-v7\n")
        found = [(item.id, item.path, item.line, "consent-version" in item.message) for item in
                 self.run_rule(profile(ROW, second))]
        self.assertEqual(found, [("literal-stray", "src/a.ts", 4, False), ("literal-stray", "src/c.ts", 2, True)])

    def test_binary_files_are_skipped(self):
        stage(self.root, "src/blob.bin", b"\x00" + HOST.encode() + b"\x00")
        self.assertEqual(self.findings(profile(ROW)), [("error", "literal-stray", "src/a.ts", 4)])

    def test_lines_over_the_bound_are_skipped(self):
        stage(self.root, "src/at.ts", HOST.rjust(4096, "x") + "\n")
        stage(self.root, "src/over.ts", HOST.rjust(4097, "x") + "\n")
        self.assertEqual(self.findings(profile(ROW)),
                         [("error", "literal-stray", "src/a.ts", 4), ("error", "literal-stray", "src/at.ts", 1)])


class Scope(Base):
    def setUp(self):
        super().setUp()
        stage(self.root, "config/hosts.ts", f"{HOST}\n")
        stage(self.root, "src/old.ts", f"{HOST}\n")
        commit_at(self.root, "base", 1, NOW)

    def test_staged_sees_only_staged_files(self):
        stage(self.root, "src/new.ts", f"x\n{HOST}\n")
        self.assertEqual(self.findings(profile(ROW), "staged"), [("error", "literal-stray", "src/new.ts", 2)])

    def test_owner_status_comes_from_the_glob_not_the_scope(self):
        stage(self.root, "config/more.ts", f"{HOST}\n")
        self.assertEqual(self.findings(profile(ROW), "staged"), [])

    def test_cli_fails_on_a_stray_copy(self):
        write_profile(self.root, "hygiene:\n  literals:\n    - id: app-host\n      pattern: 'api\\.example\\.test'\n"
                                 "      owner: [config/**]\n")
        stage(self.root, "src/new.ts", f"{HOST}\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["hygiene", "--root", str(self.root), "--staged", "--only", "literals"])
        result = json.loads(out.getvalue())
        self.assertEqual((code, result["status"]), (1, "FAIL"))
        self.assertEqual([(f["level"], f["id"], f["path"], f["line"]) for f in result["findings"]],
                         [("error", "literal-stray", "src/new.ts", 1)])
        self.assertNotIn(HOST, out.getvalue().replace(str(self.root), ""))


class Doctor(Base):
    def test_a_sound_pattern_has_no_row_full_and_quick(self):
        for quick in (False, True):
            with self.subTest(quick=quick):
                self.assertEqual(self.doctor(profile(ROW), quick), [])
        self.assertEqual(self.doctor({}), [])

    def test_nested_quantifier_warns(self):
        [(level, ident, message, fix)] = self.doctor(profile(row("(a+)+", "nested-row")), quick=True)
        self.assertEqual((level, ident), ("warn", "hygiene-literal-nested"))
        self.assertIn("nested-row", message)
        self.assertTrue(fix)

    def test_invalid_and_empty_matching_patterns_are_errors(self):
        for pattern in ("(", "x*", "^"):
            with self.subTest(pattern=pattern):
                [(level, ident, message, fix)] = self.doctor(profile(row(pattern, "broken-row")), quick=True)
                self.assertEqual((level, ident), ("error", "hygiene-literal-regex"))
                self.assertIn("broken-row", message)
                self.assertTrue(fix)

    def test_run_reports_a_broken_pattern_instead_of_skipping_it(self):
        stage(self.root, "src/a.ts", "anything\n")
        self.assertEqual(self.findings(profile(row("(", "broken-row"), ROW)),
                         [("error", "hygiene-literal-regex", None, None)])


if __name__ == "__main__":
    unittest.main()
