"""skills-check: a dispatch's REQUIRED skills against the child's `skills_loaded:` line.

Skill names here are SYNTHETIC or plugin names; the host built-in list is the
witnessed one in graph_control/skills.py.
"""

import contextlib
import io
import json
import unittest

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli
from graph_control.common import Invalid
from graph_control.skills import HOST_BUILTINS, missing, names


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


class Names(unittest.TestCase):
    def test_comma_separated_trimmed_and_deduplicated_in_order(self):
        self.assertEqual(names(" graph-engineering:bruno, prior-art ,,bruno-x, prior-art"),
                         ("graph-engineering:bruno", "prior-art", "bruno-x"))

    def test_empty_value_is_no_names(self):
        for value in ("", " ", ", ,"):
            with self.subTest(value=value):
                self.assertEqual(names(value), ())

    def test_the_whole_return_line_is_accepted(self):
        self.assertEqual(names("skills_loaded: graph-engineering:bruno, superpowers:test-driven-development"),
                         ("graph-engineering:bruno", "superpowers:test-driven-development"))

    def test_malformed_names_are_invalid(self):
        for value in ("two words", "graph-engineering:", ":", "a;b", "-rf"):
            with self.subTest(value=value), self.assertRaises(Invalid):
                names(value)


class Missing(unittest.TestCase):
    def test_all_required_loaded_is_nothing_missing(self):
        self.assertEqual(missing(("graph-engineering:bruno", "superpowers:test-driven-development"),
                                 ("superpowers:test-driven-development", "graph-engineering:bruno")), [])

    def test_a_required_skill_absent_from_the_line_is_missing(self):
        # The measured failure: `bruno` REQUIRED, loaded 1 of 3 times.
        self.assertEqual(missing(("graph-engineering:bruno", "graph-engineering:prior-art"),
                                 ("graph-engineering:prior-art",)), ["graph-engineering:bruno"])

    def test_qualified_and_bare_names_compare_by_the_part_after_the_last_colon(self):
        self.assertEqual(missing(("graph-engineering:bruno",), ("bruno",)), [])
        self.assertEqual(missing(("bruno",), ("graph-engineering:bruno",)), [])

    def test_a_bare_host_builtin_name_does_not_prove_the_plugin_skill_loaded(self):
        self.assertIn("security-review", HOST_BUILTINS)
        required = ("graph-engineering:security-review",)
        self.assertEqual(missing(required, ("security-review",)), ["graph-engineering:security-review"])
        self.assertEqual(missing(required, ("graph-engineering:security-review",)), [])

    def test_nothing_required_is_nothing_missing(self):
        self.assertEqual(missing((), ()), [])

    def test_no_skills_loaded_line_misses_every_required_skill_in_order(self):
        self.assertEqual(missing(("b:two", "a:one"), ()), ["b:two", "a:one"])


class Command(unittest.TestCase):
    def test_pass_when_every_required_skill_loaded(self):
        code, out = invoke(["skills-check", "--required", "graph-engineering:bruno",
                            "--loaded", "bruno, graph-engineering:prior-art"])
        self.assertEqual((code, out), (0, {"status": "PASS", "required": 1, "missing": []}))

    def test_missing_skills_exit_1_naming_them(self):
        code, out = invoke(["skills-check", "--required", "graph-engineering:bruno,graph-engineering:security-review",
                            "--loaded", "security-review"])
        self.assertEqual((code, out), (1, {"status": "SKILLS_MISSING",
                                           "missing": ["graph-engineering:bruno", "graph-engineering:security-review"]}))

    def test_malformed_input_is_blocked(self):
        code, out = invoke(["skills-check", "--required", "graph-engineering:bruno", "--loaded", "not a name"])
        self.assertEqual((code, out["status"]), (1, "BLOCKED"))


if __name__ == "__main__":
    unittest.main()
