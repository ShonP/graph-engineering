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
        self.assertEqual(homes, [DOD])

    def test_agents_point_to_the_rule_without_restating_it(self):
        for role in ("implementer", "implementer-simple", "reviewer"):
            line = next(l for l in (AGENTS / f"{role}.md").read_text(encoding="utf-8").splitlines()
                        if "code-comment rule" in l or "code comment" in l)
            with self.subTest(role=role):
                self.assertIn("`definition-of-done`", line)
                self.assertNotIn("licence", line)

    def test_the_dataclass_exemption_is_a_directive_not_prose(self):
        text = DOD.read_text(encoding="utf-8")
        self.assertIn("# graph: allow-dataclass <reason-id>", text)
        house = (SKILLS / "python" / "pydantic-house-rules" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("# graph: allow-dataclass <reason-id>", house)
        self.assertNotIn("# framework adapter exception:", house)

    def test_no_skill_asks_for_explanatory_comments(self):
        hygiene = (SKILLS / "ios" / "swiftui-pro" / "references" / "hygiene.md").read_text(encoding="utf-8")
        self.assertNotIn("comments should be present", hygiene)


if __name__ == "__main__":
    unittest.main()
