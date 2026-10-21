import unittest

from test_roster_policy import AGENTS, SKILLS

REVIEW_TESTING = SKILLS / "rules" / "review-testing-rules" / "SKILL.md"
FRONTEND = SKILLS / "rules" / "frontend-rules" / "SKILL.md"
HOMES = {
    "never commit on the default branch in the main checkout": REVIEW_TESTING,
    "remove the worktree and its branch": REVIEW_TESTING,
    "Scaffold with the official CLI": REVIEW_TESTING,
    "`.env.example`": REVIEW_TESTING,
    "never only in a report, PR body or chat": REVIEW_TESTING,
    "adjacent issues follow `impact-map`": REVIEW_TESTING,
    "CI secrets doc, if the repo has one": REVIEW_TESTING,
    "past ~250 LOC": REVIEW_TESTING,
    "loading, empty and error state": FRONTEND,
    "disabled while its request is pending": FRONTEND,
    "Missing is not zero": FRONTEND,
}


def documents():
    return sorted(SKILLS.rglob("SKILL.md")) + sorted(AGENTS.glob("*.md"))


class LiftedRules(unittest.TestCase):
    def test_each_lifted_rule_has_exactly_one_home(self):
        docs = {path: path.read_text(encoding="utf-8") for path in documents()}
        for needle, home in HOMES.items():
            with self.subTest(needle=needle):
                self.assertEqual([p for p, text in docs.items() if needle in text], [home])


if __name__ == "__main__":
    unittest.main()
