import re
import unittest

from test_roster_policy import AGENTS, SKILLS, split

DOD = SKILLS / "process" / "definition-of-done" / "SKILL.md"
DOD_NAME = "graph-engineering:definition-of-done"
RULE = re.compile(r"no (code )?comments|comments? (only|unless)", re.I)
COMMENT_DUTY = re.compile(r"carries a comment|Document every property", re.I)
EXTERNAL_WHY = {"pydantic-house-rules"}


class NoCommentsRule(unittest.TestCase):
    def test_definition_of_done_holds_the_rule_and_its_allowlist(self):
        text = DOD.read_text(encoding="utf-8")
        for needle in ("**No code comments.**", "tool directives", "licence header", "check-no-new-comments.py"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_reviewers_are_told_to_flag_added_comments(self):
        text = DOD.read_text(encoding="utf-8")
        self.assertRegex(text, r"Reviewers flag each added comment as Important")

    def test_every_writer_and_reviewer_preloads_the_home(self):
        for role in ("implementer", "implementer-simple", "reviewer", "reviewer-lead"):
            with self.subTest(role=role):
                fm, _ = split(AGENTS / f"{role}.md")
                self.assertIn(DOD_NAME, fm["skills"])

    def test_every_house_skill_that_requires_comments_is_a_named_exception(self):
        text = DOD.read_text(encoding="utf-8")
        self.assertIn("a comment a routed house skill requires", text)
        demanding = {p.parent.name for p in SKILLS.rglob("SKILL.md")
                     if COMMENT_DUTY.search(p.read_text(encoding="utf-8"))}
        self.assertEqual(demanding - EXTERNAL_WHY, {"helm", "ruff"})
        for name in demanding - EXTERNAL_WHY:
            with self.subTest(skill=name):
                self.assertIn(f"`{name}`", text)

    def test_the_rule_has_exactly_one_home(self):
        homes = [p for p in sorted(SKILLS.rglob("SKILL.md")) + sorted(AGENTS.glob("*.md"))
                 if RULE.search(p.read_text(encoding="utf-8"))]
        pointers = [AGENTS / "implementer-simple.md", AGENTS / "implementer.md"]
        self.assertEqual(homes, [DOD] + pointers)
        for pointer in pointers:
            self.assertIn("`definition-of-done`", next(
                line for line in pointer.read_text(encoding="utf-8").splitlines() if RULE.search(line)))


if __name__ == "__main__":
    unittest.main()
