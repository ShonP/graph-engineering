"""skills-check: a dispatch's REQUIRED skills against the child's `skills_loaded:` line.

Skill names here are SYNTHETIC or plugin names. A qualified name is proven only by
the identical qualified name; there is no host built-in list.
"""

import contextlib
import io
import json
import unittest

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli, skills
from graph_control.common import Invalid
from graph_control.skills import missing, names


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
        for value in ("", " ", ", ,", "skills_loaded:"):
            with self.subTest(value=value):
                self.assertEqual(names(value), ())

    def test_the_whole_return_line_is_accepted(self):
        self.assertEqual(names("skills_loaded: graph-engineering:bruno, superpowers:test-driven-development"),
                         ("graph-engineering:bruno", "superpowers:test-driven-development"))

    def test_backticks_annotations_and_case_are_tolerated(self):
        line = ("`skills_loaded: `Graph-Engineering:Bruno` (preloaded),  `superpowers:test-driven-development`"
                " (invoked, twice) , graph-engineering:prior-art`")
        self.assertEqual(names(line), ("graph-engineering:bruno", "superpowers:test-driven-development",
                                       "graph-engineering:prior-art"))

    def test_malformed_names_are_invalid(self):
        for value in ("two words", "graph-engineering:", ":", "a;b", "-rf", "a:b:c", "graph.engineering:x", "_x"):
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

    def test_a_qualified_name_is_proven_only_by_the_identical_qualified_name(self):
        required = ("graph-engineering:security-review",)
        self.assertEqual(missing(required, ("security-review",)), list(required))
        self.assertEqual(missing(required, ("other-plugin:security-review",)), list(required))
        self.assertEqual(missing(required, ("graph-engineering:security-review",)), [])

    def test_a_bare_loaded_name_proves_only_a_bare_required_name(self):
        self.assertEqual(missing(("house-style",), ("house-style",)), [])
        self.assertEqual(missing(("house-style",), ("graph-engineering:house-style",)), ["house-style"])

    def test_no_static_host_snapshot(self):
        self.assertFalse(hasattr(skills, "HOST_BUILTINS"))

    def test_nothing_required_is_nothing_missing(self):
        self.assertEqual(missing((), ()), [])

    def test_no_skills_loaded_line_misses_every_required_skill_in_order(self):
        self.assertEqual(missing(("b:two", "a:one"), ()), ["b:two", "a:one"])


class Command(unittest.TestCase):
    def test_pass_exits_0_when_every_required_skill_loaded(self):
        code, out = invoke(["skills-check", "--required", "graph-engineering:bruno",
                            "--loaded", "graph-engineering:bruno (preloaded), graph-engineering:prior-art"])
        self.assertEqual((code, out), (0, {"status": "PASS", "required": 1, "missing": []}))

    def test_missing_skills_exit_1_naming_them(self):
        code, out = invoke(["skills-check", "--required", "graph-engineering:bruno,graph-engineering:security-review",
                            "--loaded", "security-review"])
        self.assertEqual((code, out), (1, {"status": "SKILLS_MISSING",
                                           "missing": ["graph-engineering:bruno", "graph-engineering:security-review"]}))

    def test_malformed_input_is_blocked_with_exit_2_naming_the_line_format(self):
        for flag in ("--loaded", "--required"):
            argv = {"--required": "graph-engineering:bruno", "--loaded": "graph-engineering:bruno", flag: "not a name"}
            with self.subTest(flag=flag):
                code, out = invoke(["skills-check", *(item for pair in argv.items() for item in pair)])
                self.assertEqual((code, out["status"]), (2, "BLOCKED"))
                self.assertIn("'not a name'", out["reason"])
                self.assertIn("skills_loaded: <plugin>:<skill>", out["reason"])


if __name__ == "__main__":
    unittest.main()
