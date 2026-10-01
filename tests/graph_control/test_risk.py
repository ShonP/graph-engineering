"""Risk table: profile `risk:` rows validated, then matched on changed paths and added lines.

Paths and rows are SYNTHETIC (no real repo); the glob dialect is the one the
profile template names, wcmatch GLOBSTAR | BRACE | DOTGLOB.
"""

import importlib.util
import threading
import time
import unittest
from pathlib import Path

import yaml

import helpers  # noqa: F401 - puts scripts/ on sys.path

if importlib.util.find_spec("wcmatch") is None:  # the PEP 723 pin; scripts/run-all-tests.sh installs it
    raise unittest.SkipTest("needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

from graph_control.common import Invalid  # noqa: E402
from graph_control.risk import (LONG_LINE, SHAPE, BadPattern, Overrun, Row, classify, load_rows,  # noqa: E402
                                 nested, skipped_lines)

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
        self.assertEqual(nested(rows), [])  # no shipped regex backtracks exponentially

    def test_template_destructive_keywords_catch_sql_in_code(self):
        rows = load_rows(yaml.safe_load(TEMPLATE.read_text()))
        for line in ('cur.execute("TRUNCATE audit_log")', "TRUNCATE TABLE x", "ALTER TABLE users DROP COLUMN email",
                     'cur.execute("drop table x")', "conn.execute('drop table x')", "TRUNCATE TABLE users;",
                     'cur.execute("delete from users where 1=1")', 'cur.execute(f"delete from {table}")',
                     "alter table users drop column email", "DELETE FROM users WHERE id = 1;",
                     "DROP DATABASE app;", "DROP SCHEMA app CASCADE;", "DROP VIEW v;", "DROP INDEX i;",
                     "op.execute('truncate table audit')", "knex.raw(`drop table x`)", "    drop table x;"):
            with self.subTest(line=line):
                self.assertIn("destructive", classify(["src/db.py"], line, rows))

    def test_template_keywords_skip_ui_code_and_copy_that_share_their_letters(self):
        rows = load_rows(yaml.safe_load(TEMPLATE.read_text()))
        for path, line in (("web/src/Card.tsx", '<span className="truncate text-sm">{name}</span>'),
                           ("web/src/Card.tsx", "onDrop={() => drop(item)}"),
                           ("web/src/Card.tsx", "<p>Drag and drop the file</p>"),
                           ("web/src/locales/en.json", '"remove": "Delete from favorites",'),
                           ("web/src/locales/en.json", '"hint": "Drag and drop column headers",'),
                           ("web/src/flags.ts", "export const SHOULD_TRUNCATE = true;"),
                           ("src/config.py", 'TRUNCATE = "truncate"'),
                           ("web/src/Card.tsx", 'className="truncate text-sm"'),
                           ("web/src/Table.tsx", '<table className="table-striped" />'),
                           ("web/src/Pay.tsx", "// recharge, surcharge, discharge"),
                           ("src/pay.py", "# Payments are processed by Stripe.")):
            with self.subTest(line=line):
                self.assertEqual(classify([path], line, rows), [])
        self.assertEqual(classify(["src/pay.py"], "stripe.PaymentIntent.create(amount=1)", rows), ["spend"])


class Classify(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows(ROWS)

    def test_no_match_is_an_empty_list(self):
        self.assertEqual(classify(["src/app.py"], "print('ok')", self.rows), [])

    def test_path_glob_matches_and_ids_come_back_sorted(self):
        got = classify(["services/api/auth/login.py", "db/migrations/0001.sql"], "", self.rows)
        self.assertEqual(got, ["auth", "db-schema"])

    def test_keywords_match_literally_and_case_sensitively(self):
        # The profile contract: a keyword is spelled the way the code spells it.
        for added in ("API_KEY = read()", "-----BEGIN private key-----"):
            with self.subTest(added=added):
                self.assertEqual(classify(["src/app.py"], added, self.rows), ["credentials-and-access"])
        for added in ("config.api_key = read()", "Api_Key: x", "-----BEGIN PRIVATE KEY-----", "apikey = read()"):
            with self.subTest(added=added):
                self.assertEqual(classify(["src/app.py"], added, self.rows), [])

    def test_either_paths_or_keywords_match_a_row(self):
        self.assertEqual(classify(["src/web/page.tsx"], "set(session_token)", self.rows), ["auth"])


class RegexKeywords(unittest.TestCase):
    """A keyword starting with `re:` is a Python regex, compiled when the table is read."""

    def rows(self, *keywords):
        return load_rows({"risk": [{"id": "destructive", "keywords": list(keywords)}]})

    def test_a_re_keyword_is_a_python_regex(self):
        rows = self.rows(r"re:\b(?i:drop)\s+(?i:table)\b")
        for added in ("drop table x", "DROP  Table x", "conn.execute('Drop table x')"):
            with self.subTest(added=added):
                self.assertEqual(classify(["src/db.py"], added, rows), ["destructive"])
        for added in ("backdrop table", "drop tables", "drop the table"):
            with self.subTest(added=added):
                self.assertEqual(classify(["src/db.py"], added, rows), [])

    def test_a_regex_matches_within_one_added_line(self):
        self.assertEqual(classify(["src/db.py"], "x = 'drop'\ntable = 1", self.rows(r"re:drop\s+table")), [])

    def test_a_plain_keyword_with_regex_characters_stays_literal(self):
        rows = self.rows("stripe.")
        self.assertEqual(classify(["src/pay.py"], "stripe.Charge.create()", rows), ["destructive"])
        self.assertEqual(classify(["src/pay.py"], "stripes", rows), [])

    def test_an_invalid_or_empty_matching_regex_is_rejected_naming_row_and_keyword(self):
        for keyword in ("re:(", "re:", "re:a*"):
            with self.subTest(keyword=keyword), self.assertRaises(BadPattern) as caught:
                self.rows(keyword)
            self.assertIn("destructive", str(caught.exception))
            self.assertIn(repr(keyword), str(caught.exception))
        self.assertTrue(issubclass(BadPattern, Invalid))


class RegexBounds(unittest.TestCase):
    """A `re:` keyword runs on backtracking `re`: long lines are skipped and one call has a time budget."""

    def rows(self, *keywords):
        return load_rows({"risk": [{"id": "slow", "keywords": list(keywords)}]})

    def test_a_runaway_regex_on_one_short_line_is_cut_off_naming_the_row(self):
        start = time.monotonic()
        with self.assertRaises(Overrun) as caught:  # about 40 s uncut on CPython 3.12
            classify(["src/x.py"], "a" * 30 + "!", self.rows("re:(a+)+$"), budget=0.2)
        self.assertLess(time.monotonic() - start, 2)
        self.assertIn("risk row slow", str(caught.exception))
        self.assertTrue(issubclass(Overrun, Invalid))

    def test_off_the_main_thread_the_budget_is_checked_between_lines(self):
        caught = []

        def scan():
            try:
                classify(["src/x.py"], "\n".join(["a" * 16 + "!"] * 400), self.rows("re:(a+)+$"), budget=0.05)
            except Overrun as error:
                caught.append(error)

        worker = threading.Thread(target=scan)
        worker.start()
        worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(caught), 1)

    def test_regex_keywords_skip_lines_over_the_limit_and_count_them(self):
        rows = self.rows(r"re:drop\s+table", "API_KEY")
        line = "drop table x  # " + "y" * LONG_LINE
        self.assertEqual(classify(["src/db.py"], line, rows), [])
        self.assertEqual(skipped_lines(line + "\nshort", rows), 1)
        self.assertEqual(classify(["src/db.py"], line[:LONG_LINE], rows), ["slow"])  # at the limit: read
        self.assertEqual(classify(["src/db.py"], "API_KEY " + "y" * LONG_LINE, rows), ["slow"])  # literals: read
        self.assertEqual(skipped_lines(line, self.rows("API_KEY")), 0)  # nothing skipped without a regex

    def test_nested_quantifiers_are_flagged_for_doctor(self):
        rows = self.rows("re:(a+)+$", r"re:(\w*)*x", r"re:drop\s+table", "(a+)+")
        self.assertEqual(nested(rows), ["slow 're:(a+)+$'", "slow 're:(\\\\w*)*x'"])


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
