import re
import unittest

from test_research_planning import GenericText, flat, section
from test_roster_policy import ROOT, split

PLANNER = ROOT / "agents" / "planner.md"
RESEARCHER = ROOT / "agents" / "researcher.md"
REVIEWER = ROOT / "agents" / "reviewer.md"
EDGE_CASES = ("empty", "limits", "invalid input", "failures", "permissions", "concurrency", "time")


class PlannerReuse(GenericText):
    def setUp(self):
        _, self.body = split(PLANNER)
        self.goal = flat(section(self.body, "## Goal node"))
        self.plan = flat(section(self.body, "## Plan node"))

    def test_goal_impact_question_asks_for_similar_code_and_levels(self):
        self.assertRegex(self.goal, r"impact question[^.]*code in this repo already does something similar")
        self.assertRegex(self.goal, r"levels the repo has")

    def test_plan_reuse_inside_the_repo(self):
        for phrase in (
            "**Reuse inside the repo.**",
            "lightly refactor",
            "highest level",
            "one change high up serves",
            "never extract for a single consumer",
            "`## Reuse and level`",
            "reuse|adapt|refactor-to-share|new",
            "`n/a - no new capability`",
        ):
            self.assertIn(phrase, self.plan)
        self.assertRegex(self.plan, r"refactor-to-share is its own task ahead of its consumers")

    def test_edge_cases_join_the_acceptance_case_sentence(self):
        match = re.search(r"Include composed failures[^.]*\.", self.plan)
        self.assertIsNotNone(match)
        for case in EDGE_CASES:
            self.assertIn(case, match.group(0))

    def test_planner_stays_generic_and_short(self):
        self.assert_generic(self.body, "planner")
        self.assertLess(len(PLANNER.read_text().split("\n")), 250)


class ResearcherReuse(GenericText):
    def test_impact_mode_lists_similar_code_and_levels(self):
        _, body = split(RESEARCHER)
        (line,) = [ln for ln in body.split("\n") if ln.startswith("- **impact** - ")]
        self.assertIn("existing similar code (file:line)", line)
        self.assertIn("levels the repo has", line)
        self.assertIn("workspace manifests", line)
        self.assert_generic(line, "researcher impact")

    def test_tech_mode_stays_external(self):
        _, body = split(RESEARCHER)
        (line,) = [ln for ln in body.split("\n") if ln.startswith("- **tech** - ")]
        self.assertNotIn("similar code", line)


class ReviewerReuse(GenericText):
    def test_reviewer_flags_reuse_and_edge_case_misses(self):
        _, body = split(REVIEWER)
        text = flat(section(body, "## Reviewing"))
        self.assertRegex(text, r"re-implements something the plan said to reuse")
        self.assertIn("single consumer", text)
        self.assertRegex(text, r"misses an edge case the plan listed")
        self.assert_generic(body, "reviewer")


if __name__ == "__main__":
    unittest.main()
