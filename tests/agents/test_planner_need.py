import unittest

from test_research_planning import GenericText, flat, section
from test_roster_policy import ROOT, split

PLANNER = ROOT / "agents" / "planner.md"
PRODUCT_SPEC = ROOT / "skills" / "process" / "product-spec" / "SKILL.md"
NEED_LINE = "`<surface>: user <who>; trigger <measured signal>; run <command>`"
VALIDATE = "`graph-control validate-plan <plan> --profile <profile> --root <worktree>`"


class PlannerNeed(GenericText):
    def setUp(self):
        _, self.body = split(PLANNER)
        self.goal = flat(section(self.body, "## Goal node"))
        self.plan = flat(section(self.body, "## Plan node"))

    def test_goal_requires_a_user_line(self):
        self.assertIn("`user: <named user in a named situation>`", self.goal)
        self.assertNotIn("who it is for", self.goal)

    def test_plan_need_section_per_new_surface(self):
        self.assertIn("`## Need`", self.plan)
        self.assertIn(NEED_LINE, self.plan)
        self.assertIn("`n/a - no new surface`", self.plan)
        self.assertRegex(self.plan, r"new surface \(app, package, tool dir, provider or integration\)")
        self.assertLess(self.plan.index("`## Reuse and level`"), self.plan.index("`## Need`"))

    def test_plan_measure_section_for_a_swap(self):
        self.assertIn("`## Measure`", self.plan)
        self.assertRegex(self.plan, r"provider, model or runtime-dependency swap")
        self.assertRegex(self.plan, r"limit measured before the change \(command and value\), never assumed")

    def test_plan_json_keys_and_validator(self):
        self.assertRegex(self.plan, r"`plan\.json` `need` and `measure`")
        self.assertIn(VALIDATE, self.plan)

    def test_planner_stays_generic(self):
        self.assert_generic(self.body, "planner")


class ProductSpecNeed(GenericText):
    def test_completeness_checklist_has_a_need_row(self):
        text = PRODUCT_SPEC.read_text(encoding="utf-8")
        (para,) = [p for p in text.split("\n\n") if p.startswith("**Completeness checklist.**")]
        para = flat(para)
        self.assertRegex(para, r"need \(a named user and the command that runs it\)")
        self.assert_generic(text, "product-spec")


if __name__ == "__main__":
    unittest.main()
