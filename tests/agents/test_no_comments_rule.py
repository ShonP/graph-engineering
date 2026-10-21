import re
import unittest

from test_roster_policy import AGENTS, SKILLS, split

DOD = SKILLS / "process" / "definition-of-done" / "SKILL.md"
DOD_NAME = "graph-engineering:definition-of-done"
RULE = re.compile(r"no (code )?comments|comments? (only|unless)", re.I)


class NoCommentsRule(unittest.TestCase):
    def test_definition_of_done_holds_the_rule_and_its_one_exception(self):
        text = DOD.read_text(encoding="utf-8")
        for needle in ("**No code comments.**", "upstream issue", "section banners", "docstrings"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_reviewers_are_told_to_flag_added_comments(self):
        text = DOD.read_text(encoding="utf-8")
        self.assertRegex(text, r"Reviewers flag each added comment[^.]*Nit")

    def test_every_writer_and_reviewer_preloads_the_home(self):
        for role in ("implementer", "implementer-simple", "reviewer", "reviewer-lead"):
            with self.subTest(role=role):
                fm, _ = split(AGENTS / f"{role}.md")
                self.assertIn(DOD_NAME, fm["skills"])

    def test_the_rule_has_exactly_one_home(self):
        homes = [p for p in sorted(SKILLS.rglob("SKILL.md")) + sorted(AGENTS.glob("*.md"))
                 if RULE.search(p.read_text(encoding="utf-8"))]
        self.assertEqual(homes, [DOD])


if __name__ == "__main__":
    unittest.main()
