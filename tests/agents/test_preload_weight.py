"""Byte ceilings and preload lists for the skills agents preload on every dispatch.

Stdlib only. Guards AC-DOD-SHRINK and AC-SIMPLE-PRELOAD.
"""

import unittest

from test_roster_policy import AGENTS, SKILLS, split

DOD = SKILLS / "process" / "definition-of-done" / "SKILL.md"
DOD_CEILING = 6200


class PreloadWeight(unittest.TestCase):
    def test_definition_of_done_stays_under_its_ceiling(self):
        size = len(DOD.read_bytes())
        self.assertLessEqual(size, DOD_CEILING, f"definition-of-done is {size} bytes")

    def test_implementer_simple_preloads_only_definition_of_done(self):
        fm, _ = split(AGENTS / "implementer-simple.md")
        self.assertEqual(fm["skills"], ["graph-engineering:definition-of-done"])

    def test_implementer_simple_still_names_the_triage_route(self):
        _, body = split(AGENTS / "implementer-simple.md")
        for needle in ("`impact-map`", "Skill tool", "NEEDS_CONTEXT", "followups.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)


if __name__ == "__main__":
    unittest.main()
