"""Golden checks for the retro skill: fast path, classes.md, guard-first promotion.

Stdlib only. AC-W4-RG-01: the skill states the engine's fast path, reads
`.graph/<run>/classes.md`, promotes a recurring class as an executable guard
first (test fixture, semgrep rule in impact-map's sibling.yaml shape, lint
configuration), keeps a prose rule line only as the fallback and proposes its
removal once the guard lands, and reports the lint-tier share as a number.
The skill is a prompt, so the checks are on the contract phrases it carries.
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "process" / "retro" / "SKILL.md"
CHECK = ROOT / "scripts" / "check-skill-frontmatter.sh"
CONSUMER_WORDS = ("supabase", "swiftui", "nestjs")
WORD_BUDGET = 800


def flat(text):
    """Prose with its line wrapping removed, so a check does not depend on where a line breaks."""
    return " ".join(text.split())


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if match is None:
        raise AssertionError(f"no `## {heading}` section")
    return flat(match.group(1))


class RetroSkill(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text()
        self.method = section(self.text, "Method")

    def test_fast_path_is_written_by_the_engine_without_a_dispatch(self):
        body = section(self.text, "Fast path")
        for needle in ("one-line", "retro.md", "not dispatched", "No leaks"):
            self.assertIn(needle, body)

    def test_classes_md_is_an_input(self):
        body = section(self.text, "Inputs")
        for needle in ("`.graph/<run>/classes.md`", "after each review or qa round"):
            self.assertIn(needle, body)

    def test_recurring_class_is_promoted_as_a_guard_first(self):
        for needle in ("recurs", "twice or more", "earlier run's `retro.md`", "executable guard",
                       "as a diff into the repo", "test fixture", "semgrep rule", "`sibling.yaml`",
                       "lint configuration"):
            self.assertIn(needle, self.method)

    def test_prose_is_the_fallback_and_removed_once_its_guard_lands(self):
        self.assertIn("only the fallback", self.method)
        self.assertRegex(self.method, r"propos\w+ (deleting|removing) [^.]*prose line[^.]*guard lands")

    def test_lint_tier_share_is_reported_as_a_number(self):
        self.assertIn("lint-tier share", self.method)
        self.assertIn("`lint-tier share: <k>/<n> (<pct>%)`", self.method)
        self.assertIn("over all findings", self.method)

    def test_description_does_not_steer_toward_prose_rules(self):
        description = flat(self.text.split("---")[1])
        self.assertNotIn("a line for a repo rule pack", description)
        self.assertTrue(description.startswith("name: retro description: Use "), description)

    def test_generic_lean_and_free_of_em_dashes(self):
        lowered = self.text.lower()
        for word in CONSUMER_WORDS:
            self.assertNotIn(word, lowered)
        self.assertNotIn(chr(0x2014), self.text)
        self.assertLessEqual(len(self.text.split()), WORD_BUDGET)

    def test_frontmatter_check_passes(self):
        result = subprocess.run(["bash", str(CHECK), str(ROOT)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
