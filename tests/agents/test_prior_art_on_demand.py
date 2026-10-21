import re
import unittest

from test_roster_policy import AGENTS, ROOT, split

TEMPLATE = ROOT / "templates" / "graph-profile.yaml"
DOD = "graph-engineering:definition-of-done"
PRIOR_ART = "graph-engineering:prior-art"
ON_DEMAND = "only when the brief flags a library or design choice"


def always_impl():
    text = TEMPLATE.read_text(encoding="utf-8")
    (row,) = re.findall(r"(?m)^  always:\n(?:    #.*\n)*    impl: \[(.*)\]", text)
    return [name.strip() for name in row.split(",")]


class PriorArtOnDemand(unittest.TestCase):
    def test_template_always_row_no_longer_loads_prior_art_into_implementers(self):
        self.assertNotIn(PRIOR_ART, always_impl())
        self.assertIn("graph-engineering:review-testing-rules", always_impl())

    def test_planner_keeps_prior_art_preloaded(self):
        fm, _ = split(AGENTS / "planner.md")
        self.assertIn(PRIOR_ART, fm["skills"])

    def test_implementers_load_prior_art_only_when_the_brief_flags_a_choice(self):
        for role in ("implementer", "implementer-simple"):
            with self.subTest(role=role):
                _, body = split(AGENTS / f"{role}.md")
                self.assertIn(ON_DEMAND, body)


class ImplementerPreloads(unittest.TestCase):
    def test_implementer_preloads_only_definition_of_done(self):
        fm, _ = split(AGENTS / "implementer.md")
        self.assertEqual(fm["skills"], [DOD])

    def test_implementer_still_names_the_triage_route(self):
        _, body = split(AGENTS / "implementer.md")
        for needle in ("`impact-map`", "Skill tool", "NEEDS_CONTEXT", "followups.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)


if __name__ == "__main__":
    unittest.main()
