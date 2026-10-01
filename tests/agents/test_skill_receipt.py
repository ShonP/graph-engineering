"""Skill receipt: every roster agent that can be handed REQUIRED skills reports what it loaded,
and the engine compares that line against the dispatch with `graph-control skills-check`.

Evidence for the rule (30 days of sessions): 15 of 102 subagents that edited .tsx
never loaded a React or TanStack skill, and dispatches that REQUIRED `bruno`
loaded it 1 of 3 times. Stdlib only.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents"
RUN = ROOT / "docs" / "engine" / "run.md"
SENTENCE = ("Your return also carries one line, `skills_loaded: <comma-separated names>`, naming every skill "
            "you invoked or had preloaded, each fully qualified as it loaded (`graph-engineering:bruno`, never "
            "bare `bruno`; a skill with no plugin stays bare); the engine checks it against the REQUIRED skills "
            "your dispatch named, exact name for exact name.")
# Every roster agent with the Skill tool: the engine may name REQUIRED skills for any of them.
RECEIPT_AGENTS = ("implementer", "implementer-simple", "reviewer", "reviewer-lead", "qa", "qa-lead",
                  "researcher", "researcher-spike", "ux-designer", "planner")


def flat(text):
    return re.sub(r"\s+", " ", text)


def report(name):
    body = (AGENTS / f"{name}.md").read_text()
    match = re.search(r"^## Report\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S)
    return flat(match.group(1)) if match else ""


class Receipt(unittest.TestCase):
    def test_every_skill_capable_agent_states_the_receipt_once(self):
        for name in RECEIPT_AGENTS:
            with self.subTest(agent=name):
                self.assertIn(SENTENCE, report(name))
                self.assertEqual(flat((AGENTS / f"{name}.md").read_text()).count(SENTENCE), 1)

    def test_the_receipt_agents_are_exactly_those_with_the_skill_tool(self):
        with_skill = {path.stem for path in AGENTS.glob("*.md")
                      if re.search(r"^tools: \[[^\]]*\bSkill\b", path.read_text(), flags=re.M)}
        self.assertEqual(with_skill, set(RECEIPT_AGENTS))

    def test_the_engine_runs_skills_check_and_marks_a_miss(self):
        text = flat(RUN.read_text())
        for token in ("skills_loaded:", "graph-control skills-check --required", "--loaded", "Exit 1",
                      "SKILLS_MISSING: <names>", "re-dispatch once", "Exit 2", "BLOCKED",
                      "`skills_loaded: <plugin>:<skill>, ...`", "goes to the owner"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_the_rule_is_one_short_bullet_in_dispatch_discipline(self):
        # At most 5 rendered lines of about 120 characters: the engine reads it every run.
        step4 = RUN.read_text().split("\n4. **Dispatch discipline.**", 1)[1].split("\n5. **", 1)[0]
        rule = [line for line in step4.split("\n") if "skills-check" in line]
        self.assertEqual(len(rule), 1)
        self.assertLessEqual(len(rule[0]), 600)


if __name__ == "__main__":
    unittest.main()
