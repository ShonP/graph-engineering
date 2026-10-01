"""Risk table: profile `risk:` rows validated, then matched on changed paths and added lines.

Paths and rows are SYNTHETIC (no real repo); the glob dialect is the one the
profile template names, wcmatch GLOBSTAR | BRACE | DOTGLOB.
"""

import importlib.util
import unittest
from pathlib import Path

import yaml

import helpers  # noqa: F401 - puts scripts/ on sys.path

if importlib.util.find_spec("wcmatch") is None:  # the PEP 723 pin; scripts/run-all-tests.sh installs it
    raise unittest.SkipTest("needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

from graph_control.common import Invalid  # noqa: E402
from graph_control.risk import SHAPE, Row, classify, load_rows  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "graph-profile.yaml"

ROWS = {"risk": [
    {"id": "db-schema", "paths": ["**/{migrations,schemas}/**"]},
    {"id": "infra", "paths": [".github/**", "**/*.tf"]},
    {"id": "credentials-and-access", "keywords": ["API_KEY", "private key"]},
    {"id": "auth", "paths": ["**/auth/**"], "keywords": ["session_token"]},
]}


class LoadRows(unittest.TestCase):
    def test_rows_parse_in_order_with_defaults(self):
        rows = load_rows(ROWS)
        self.assertEqual([row.id for row in rows], ["db-schema", "infra", "credentials-and-access", "auth"])
        self.assertEqual(rows[0], Row("db-schema", ("**/{migrations,schemas}/**",), ()))
        self.assertEqual(rows[2].paths, ())

    def test_absent_or_null_risk_is_no_rows(self):
        for profile in ({}, {"risk": None}, {"risk": []}):
            with self.subTest(profile=profile):
                self.assertEqual(load_rows(profile), ())

    def test_types_are_validated(self):
        bad = {
            "not a list": {"risk": {"id": "x"}},
            "row not a mapping": {"risk": ["db"]},
            "missing id": {"risk": [{"paths": ["a/**"]}]},
            "empty id": {"risk": [{"id": " ", "paths": ["a/**"]}]},
            "paths not a list": {"risk": [{"id": "x", "paths": "a/**"}]},
            "keyword not text": {"risk": [{"id": "x", "keywords": [3]}]},
            "unknown field": {"risk": [{"id": "x", "paths": ["a/**"], "glob": "b"}]},
            "duplicate id": {"risk": [{"id": "x", "paths": ["a/**"]}, {"id": "x", "keywords": ["k"]}]},
        }
        for name, profile in bad.items():
            with self.subTest(name), self.assertRaises(Invalid):
                load_rows(profile)

    def test_only_a_list_of_rows_is_accepted_and_every_other_shape_names_it(self):
        # One accepted shape, the template's; doctor reports the same message depth raises.
        shapes = {
            "mapping keyed by id": {"risk": {"db-schema": {"paths": ["migrations/**"]}}},
            "bare ids": {"risk": ["db-schema"]},
            "row without an id": {"risk": [{"paths": ["a/**"]}]},
            "a string": {"risk": "db-schema"},
        }
        for name, profile in shapes.items():
            with self.subTest(name), self.assertRaises(Invalid) as caught:
                load_rows(profile)
            self.assertIn(SHAPE, str(caught.exception))
        with self.assertRaises(Invalid) as caught:
            load_rows(shapes["mapping keyed by id"])
        self.assertIn("not a mapping", str(caught.exception))


class PlaceholderRows(unittest.TestCase):
    """The template ships rows the repo or the engine fills: they load and match nothing."""

    def test_a_row_with_no_paths_or_keywords_loads_and_matches_nothing(self):
        rows = load_rows({"risk": [{"id": "public-copy", "paths": [], "keywords": []}, {"id": "outside-the-run"}]})
        self.assertEqual([row.id for row in rows], ["public-copy", "outside-the-run"])
        self.assertEqual(classify(["site/index.html"], "anything", rows), [])

    def test_the_shipped_template_rows_load(self):
        rows = load_rows(yaml.safe_load(TEMPLATE.read_text()))
        self.assertIn("public-copy", [row.id for row in rows])
        self.assertIn("outside-the-run", [row.id for row in rows])

    def test_template_keywords_skip_ui_code_that_shares_their_letters(self):
        rows = load_rows(yaml.safe_load(TEMPLATE.read_text()))
        added = ('<span className="truncate">{name}</span>\nonDrop={() => drop (item)}\n'
                 '<p className="truncate text-sm">Drag and drop the file</p>')
        self.assertEqual(classify(["web/src/Card.tsx"], added, rows), [])
        for sql in ("TRUNCATE TABLE users;", "truncate table users;", "Delete From users where id = 1;",
                    "drop schema app cascade;", "DROP DATABASE app;"):
            with self.subTest(sql=sql):
                self.assertEqual(classify(["src/db.py"], sql, rows), ["destructive"])
        striped = '<table className="table-striped" />\n// recharge, surcharge, discharge'
        self.assertEqual(classify(["web/src/Table.tsx"], striped, rows), [])
        self.assertEqual(classify(["src/pay.py"], "stripe.PaymentIntent.create(amount=1)", rows), ["spend"])


class Classify(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows(ROWS)

    def test_no_match_is_an_empty_list(self):
        self.assertEqual(classify(["src/app.py"], "print('ok')", self.rows), [])

    def test_path_glob_matches_and_ids_come_back_sorted(self):
        got = classify(["services/api/auth/login.py", "db/migrations/0001.sql"], "", self.rows)
        self.assertEqual(got, ["auth", "db-schema"])

    def test_keywords_match_literally_and_case_insensitively(self):
        # The profile contract: keywords match case-insensitively against added lines.
        for added in ("API_KEY = read()", "config.api_key = read()", "Api_Key: x", "-----BEGIN PRIVATE KEY-----"):
            with self.subTest(added=added):
                self.assertEqual(classify(["src/app.py"], added, self.rows), ["credentials-and-access"])
        self.assertEqual(classify(["src/app.py"], "apikey = read()", self.rows), [])

    def test_a_mixed_case_keyword_matches_every_casing(self):
        rows = load_rows({"risk": [{"id": "destructive", "keywords": ["Delete From"]}]})
        for added in ("DELETE FROM users;", "delete from users;", "dElEtE fRoM users;"):
            with self.subTest(added=added):
                self.assertEqual(classify(["src/db.py"], added, rows), ["destructive"])
        self.assertEqual(classify(["src/db.py"], "deleted_from = None", rows), [])

    def test_either_paths_or_keywords_match_a_row(self):
        self.assertEqual(classify(["src/web/page.tsx"], "set(session_token)", self.rows), ["auth"])


class GlobDialect(unittest.TestCase):
    """AC-W2-DP-04: brace, ** and dotfile globs behave like wcmatch GLOBSTAR|BRACE|DOTGLOB."""

    def matched(self, glob, path):
        return classify([path], "", load_rows({"risk": [{"id": "row", "paths": [glob]}]})) == ["row"]

    def test_brace_and_globstar(self):
        glob = "**/{migrations,schemas}/**"
        for path in ("migrations/0001.sql", "db/migrations/0001.sql", "api/schemas/v1/user.json"):
            with self.subTest(path=path):
                self.assertTrue(self.matched(glob, path))
        for path in ("migrationsx/0001.sql", "api/schemas", "db/migration/0001.sql"):
            with self.subTest(path=path):
                self.assertFalse(self.matched(glob, path))

    def test_dot_directories(self):
        self.assertTrue(self.matched(".github/**", ".github/workflows/ci.yml"))
        self.assertFalse(self.matched(".github/**", "src/.github/ci.yml"))
        self.assertTrue(self.matched("**/*.yml", ".github/workflows/ci.yml"))

    def test_single_star_stays_in_one_segment_and_case_matters(self):
        self.assertFalse(self.matched("*.tf", "infra/main.tf"))
        self.assertTrue(self.matched("**/*.tf", "main.tf"))
        self.assertFalse(self.matched("**/*.tf", "infra/MAIN.TF"))


if __name__ == "__main__":
    unittest.main()
