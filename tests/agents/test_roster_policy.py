"""Golden checks for the roster agents' frontmatter and prompt contracts.

Stdlib only, so it runs with plain `python3 -m unittest discover -s tests/agents`.
Each test names the acceptance row it guards (AC-W1-AG-*).
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents"
SKILLS = ROOT / "skills"

TIERS = {
    "implementer": "opus",
    "reviewer": "opus",
    "reviewer-lead": "opus",
    "planner": "opus",
    "ux-designer": "opus",
    "implementer-simple": "sonnet",
    "researcher": "sonnet",
    "researcher-spike": "sonnet",
    "qa": "sonnet",
    "qa-lead": "sonnet",
    "retro": "sonnet",
}
MAX_TURNS = {
    "implementer": 200, "implementer-simple": 60, "qa": 400, "qa-lead": 150, "retro": 40,
    "researcher-spike": 25, "reviewer-lead": 120,
}
# Fields a plugin agent honors, minus isolation (it branches from the default
# branch, not the run branch). permissionMode, hooks, mcpServers and
# initialPrompt are ignored for plugin agents, so they are rejected here too.
ALLOWED_KEYS = {
    "name", "description", "model", "effort", "maxTurns", "tools",
    "disallowedTools", "skills", "memory", "background", "omitClaudeMd", "color",
}
SHARED_BLOCK = (
    "Return at most 1,500 tokens: status, commits or artifact paths, case IDs and "
    "results, blockers. Keep logs in run artifacts. Report every suite you ran as "
    "`<command>: exit=<n> complete|partial`. Never wait with sleep or until loops. "
    "For a command that takes longer than one call, use run_in_background only if "
    "your dispatch says you run in the background; otherwise make one blocking call "
    "with an explicit timeout (at most 600000 ms). Never end your turn while you "
    "still need a result."
)
SHARED_BLOCK_AGENTS = (
    "implementer", "implementer-simple", "qa", "researcher", "researcher-spike",
)
REVIEWER_LENSES = {
    "review-protocol": "# Review protocol",
    "security-review": "# Security review",
    "privacy-review": "# Privacy review",
    "definition-of-done": "# Definition of done",
}


def split(path):
    """(frontmatter dict, body text). Lists come back as lists of strings."""
    lines = path.read_text(encoding="utf-8").split("\n")
    assert lines[0].strip() == "---", f"{path.name}: no frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    fm, key = {}, None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s*(\S.*?)\s*$", line)
        if item and key:
            fm[key].append(item.group(1))
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        assert m, f"{path.name}: unparsed frontmatter line {line!r}"
        key, value = m.group(1), m.group(2)
        if value.startswith("["):
            fm[key] = [v.strip() for v in value.strip("[]").split(",") if v.strip()]
        elif value == "":
            fm[key] = []
        else:
            fm[key] = value
    return fm, "\n".join(lines[end + 1:])


def roster():
    return {p.stem: split(p) for p in sorted(AGENTS.glob("*.md"))}


class RosterPolicy(unittest.TestCase):
    def setUp(self):
        self.agents = roster()

    def has(self, text, needle, who):
        self.assertTrue(needle in text, f"{who}: missing {needle!r}")

    def lacks(self, text, needle, who):
        self.assertFalse(needle in text, f"{who}: must not contain {needle!r}")

    def test_roster_is_exactly_the_tiered_set(self):
        self.assertEqual(set(self.agents), set(TIERS))

    def test_models_follow_the_tier_table(self):  # AC-W1-AG-01
        for name, (fm, _) in self.agents.items():
            self.assertEqual(fm.get("model"), TIERS[name], name)

    def test_name_matches_file(self):
        for name, (fm, _) in self.agents.items():
            self.assertEqual(fm.get("name"), name)

    def test_only_plugin_honored_keys(self):
        for name, (fm, _) in self.agents.items():
            self.assertLessEqual(set(fm), ALLOWED_KEYS, name)

    def test_every_skill_is_plugin_qualified(self):  # AC-W1-AG-02
        for name, (fm, _) in self.agents.items():
            for skill in fm.get("skills", []):
                self.assertTrue(skill.startswith("graph-engineering:"), f"{name}: {skill}")

    def test_turn_caps(self):  # AC-W1-AG-03
        for name, cap in MAX_TURNS.items():
            self.assertEqual(self.agents[name][0].get("maxTurns"), str(cap), name)

    def test_retro_has_fixed_tools_and_skill(self):  # AC-W1-AG-03
        fm, body = self.agents["retro"]
        self.assertEqual(fm["tools"], ["Read", "Grep", "Glob", "Bash", "Write"])
        self.assertNotIn("Skill", fm["tools"])
        self.assertEqual(fm["skills"], ["graph-engineering:retro"])
        for needle in ("retro.md", "300 words", "never edit"):
            self.has(body, needle, "retro")

    def test_qa_verdict_rule(self):  # AC-W1-AG-04
        body = self.agents["qa"][1]
        for needle in (
            "`INCOMPLETE: <row ids>`", "NOT RUN", "SKIPPED", "N/A",
            "cannot be moved out as a side defect",
        ):
            self.has(body, needle, "qa")

    def test_reviewer_contract(self):  # AC-W1-AG-04
        fm, body = self.agents["reviewer"]
        self.assertIn("Write", fm["tools"])
        for needle in (
            "lenses:", "NEEDS_SETUP", "no full test suites",
            "`PASS|CHANGES-REQUESTED blocking=<n> important=<m> findings=<path>`",
            *(f"`{heading}`" for heading in REVIEWER_LENSES.values()),
        ):
            self.has(body, needle, "reviewer")

    def test_reviewer_lens_headings_match_the_skills(self):
        for skill, heading in REVIEWER_LENSES.items():
            (path,) = SKILLS.glob(f"*/{skill}/SKILL.md")
            first = next(
                line for line in path.read_text(encoding="utf-8").split("\n")
                if line.startswith("# ")
            )
            self.assertEqual(first, heading, path)

    def test_shared_block_verbatim(self):  # AC-W1-AG-05
        for name in SHARED_BLOCK_AGENTS:
            self.assertEqual(self.agents[name][1].count(SHARED_BLOCK), 1, name)

    def test_no_sleep_polling_advice(self):  # AC-W1-AG-05
        polling = re.compile(r"sleep\s+\d|while\b.*\bsleep|until\b.*;\s*do|\bpoll\b", re.I)
        for name, (_, body) in self.agents.items():
            self.assertIsNone(polling.search(body), name)

    def test_planner_has_no_merge_or_retro_node(self):  # AC-W1-AG-06
        fm, body = self.agents["planner"]
        self.assertNotRegex(body, r"(?m)^## (Merge|Retro) node")
        self.has(fm["description"], "goal and plan nodes", "planner")

    def test_no_retired_tier_or_em_dash(self):  # AC-W1-AG-06
        for path in AGENTS.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.lacks(text.lower(), "fable", path.name)
            self.lacks(text, chr(0x2014), path.name)

    def test_implementers_write_through_edit_and_try_before_asking(self):
        for name in ("implementer", "implementer-simple"):
            body = self.agents[name][1]
            for needle in (
                "never heredocs or `sed -i`", "owner-only", "messages to real people",
            ):
                self.has(body, needle, name)


if __name__ == "__main__":
    unittest.main()
