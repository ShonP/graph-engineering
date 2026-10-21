import unittest

from test_roster_policy import AGENTS, ROOT, split

BRIEF_DRIVEN = ("researcher-spike", "retro")
KEEPS_CLAUDE_MD = ("implementer", "implementer-simple", "planner", "reviewer", "reviewer-lead", "ux-designer",
                   "researcher", "qa", "qa-lead")
RUN = ROOT / "docs" / "engine" / "run.md"


class OmitClaudeMd(unittest.TestCase):
    def test_brief_driven_agents_skip_claude_md_and_say_so_to_any_dispatcher(self):
        for role in BRIEF_DRIVEN:
            with self.subTest(role=role):
                fm, body = split(AGENTS / f"{role}.md")
                self.assertEqual(fm.get("omitClaudeMd"), "true")
                self.assertIn("Launched without CLAUDE.md, so the dispatch must carry everything it needs",
                              fm["description"])
                self.assertIn("## No CLAUDE.md", body)
                self.assertIn("project invariants", body)
                self.assertIn("NEEDS_CONTEXT", body)

    def test_every_other_agent_keeps_claude_md(self):
        for role in KEEPS_CLAUDE_MD:
            with self.subTest(role=role):
                fm, _ = split(AGENTS / f"{role}.md")
                self.assertNotIn("omitClaudeMd", fm)

    def test_the_engine_dispatch_shape_carries_what_claude_md_held(self):
        text = RUN.read_text(encoding="utf-8")
        self.assertIn("(`omitClaudeMd: true`: `researcher-spike`, `retro`)", text)
        self.assertRegex(text, r"rule packs[^.]*project invariants")


if __name__ == "__main__":
    unittest.main()
