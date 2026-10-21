"""Design competencies: Taste Skill and Vercel's Web Interface Guidelines replace ui-ux-pro-max.

Stdlib only. Guards AC-UX-TASTE-WIG.
"""

import re
import subprocess
import unittest

from test_roster_policy import AGENTS, ROOT, SKILLS, split

UX = SKILLS / "ux"
WIG = UX / "web-interface-guidelines"
TASTE = UX / "taste"
TEMPLATE = ROOT / "templates" / "graph-profile.yaml"
REMOVED = "ui-ux-pro-max"
HISTORY = ("docs/superpowers/", "CHANGELOG.md")
SELF = "tests/agents/test_ux_design_skills.py"
DESCRIPTION_CEILING = 300
PRECEDENCE = "design tokens"


def description(path):
    fm, _ = split(path)
    return fm["description"]


def git_blob_sha(path):
    out = subprocess.run(
        ["git", "hash-object", str(path)], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


class RemovedSkill(unittest.TestCase):
    def test_vendored_database_is_gone(self):
        self.assertFalse((UX / REMOVED).exists())

    def test_nothing_outside_history_names_it(self):
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "grep", "-l", REMOVED, "--", "."],
            capture_output=True, text=True,
        ).stdout.split()
        live = [p for p in tracked if not p.startswith(HISTORY) and p != SELF]
        self.assertEqual(live, [], f"{REMOVED} still referenced in {live}")


class NewSkills(unittest.TestCase):
    def test_descriptions_stay_short(self):
        for skill in (WIG, TASTE):
            with self.subTest(skill=skill.name):
                text = description(skill / "SKILL.md")
                self.assertLessEqual(len(text), DESCRIPTION_CEILING, text)
                self.assertTrue(text.startswith("Use when"), text)

    def test_repo_design_system_wins(self):
        for skill in (WIG, TASTE):
            with self.subTest(skill=skill.name):
                _, body = split(skill / "SKILL.md")
                self.assertIn(PRECEDENCE, body)

    def test_guidelines_are_vendored_byte_for_byte_at_the_pin(self):
        source = (WIG / "SOURCE.md").read_text(encoding="utf-8")
        pinned = re.search(r"AGENTS\.md blob: ([0-9a-f]{40})", source)
        self.assertIsNotNone(pinned, "SOURCE.md must record the upstream AGENTS.md blob sha")
        self.assertEqual(git_blob_sha(WIG / "AGENTS.md"), pinned.group(1))
        self.assertIn("MIT License", (WIG / "LICENSE").read_text(encoding="utf-8"))

    def test_taste_points_at_the_maintained_upstream_plugin(self):
        _, body = split(TASTE / "SKILL.md")
        for needle in (
            '"repo": "Leonxlnx/taste-skill"',
            '"taste-skill@taste-skill": true',
            "taste-skill:design-taste-frontend",
            ".claude/settings.json",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)
        self.assertFalse((TASTE / "references").exists())

    def test_taste_install_is_pinned_to_the_recorded_tag(self):
        source = (TASTE / "SOURCE.md").read_text(encoding="utf-8")
        tag = re.search(r"^- Tag: (v\d+\.\d+\.\d+)$", source, re.M)
        self.assertIsNotNone(tag, "SOURCE.md must record the pinned tag")
        self.assertRegex(source, r"(?m)^- Commit: [0-9a-f]{40}\b")
        pin = f'"ref": "{tag.group(1)}"'
        for path in (TASTE / "SKILL.md", ROOT / "README.md"):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(pin, text)
                self.assertNotIn("/plugin marketplace add Leonxlnx/taste-skill", text)


class Routing(unittest.TestCase):
    def test_design_phase_loads_taste_beside_ux_journey(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        design = re.search(r"^\s+design: \[(.*)\]$", text, re.M).group(1)
        self.assertIn("graph-engineering:ux-journey", design)
        self.assertIn("graph-engineering:taste", design)

    def test_web_ui_rows_route_the_guidelines(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        react = text.split("depends on react (react-dom, next, ...)", 1)[1].split("- when:", 1)[0]
        self.assertIn("graph-engineering:web-interface-guidelines", react)
        self.assertIn("graph-engineering:taste", react.split("review:", 1)[1].split("\n", 1)[0])

    def test_ux_designer_fallback_names_the_new_skills(self):
        _, body = split(AGENTS / "ux-designer.md")
        for needle in ("`taste`", "`web-interface-guidelines`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)


if __name__ == "__main__":
    unittest.main()
