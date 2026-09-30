"""Risk table: profile `risk:` rows validated, then matched on changed paths and added lines.

Paths and rows are SYNTHETIC (no real repo); the glob dialect is the one the
profile template names, wcmatch GLOBSTAR | BRACE | DOTGLOB.
"""

import importlib.util
import unittest

import helpers  # noqa: F401 - puts scripts/ on sys.path

if importlib.util.find_spec("wcmatch") is None:  # the PEP 723 pin; scripts/run-all-tests.sh installs it
    raise unittest.SkipTest("needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

from graph_control.common import Invalid  # noqa: E402
from graph_control.risk import Row, classify, load_rows  # noqa: E402

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
            "neither paths nor keywords": {"risk": [{"id": "x", "paths": [], "keywords": []}]},
            "duplicate id": {"risk": [{"id": "x", "paths": ["a/**"]}, {"id": "x", "keywords": ["k"]}]},
        }
        for name, profile in bad.items():
            with self.subTest(name), self.assertRaises(Invalid):
                load_rows(profile)


class Classify(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows(ROWS)

    def test_no_match_is_an_empty_list(self):
        self.assertEqual(classify(["src/app.py"], "print('ok')", self.rows), [])

    def test_path_glob_matches_and_ids_come_back_sorted(self):
        got = classify(["services/api/auth/login.py", "db/migrations/0001.sql"], "", self.rows)
        self.assertEqual(got, ["auth", "db-schema"])

    def test_keyword_in_added_text_matches_case_insensitively(self):
        self.assertEqual(classify(["src/app.py"], "config.api_key = read()", self.rows), ["credentials-and-access"])
        self.assertEqual(classify(["src/app.py"], "-----BEGIN PRIVATE KEY-----", self.rows),
                         ["credentials-and-access"])

    def test_either_paths_or_keywords_match_a_row(self):
        self.assertEqual(classify(["src/web/page.tsx"], "set(SESSION_TOKEN)", self.rows), ["auth"])


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
