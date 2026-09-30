"""Golden checks for the qa lead, its qa leaves and the lead trigger.

Stdlib only; run by scripts/check-skill-scripts.sh. Guards AC-W3-QL-01..04.
The behaviour check is the owner's release check R5 (one qa-lead run on a
3-lane fixture app); these greps pin the contract that run relies on.
"""

import re
import subprocess
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
LEAD_PATH = ROOT / "agents" / "qa-lead.md"
LEAF_PATH = ROOT / "agents" / "qa.md"
SKILL_PATH = SKILL_DIR / "SKILL.md"
LEAF_LINE = "leaf mode: the runtime is up and owned by the lead - never run up, seed or down"
TOOLS = ["Read", "Grep", "Glob", "Bash", "Write", "Agent", "Skill"]


def read(path):
    return path.read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text)


def split(path):
    """(frontmatter lines, body) of an agent file."""
    lines = read(path).split("\n")
    end = lines.index("---", 1)
    return lines[1:end], "\n".join(lines[end + 1:])


def field(head, key):
    for line in head:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def block_list(head, key):
    start = head.index(f"{key}:")
    items = []
    for line in head[start + 1:]:
        if not line.startswith("  - "):
            break
        items.append(line[4:].strip())
    return items


class Case(unittest.TestCase):
    def has(self, text, *needles):
        for needle in needles:
            self.assertTrue(needle in text, f"missing {needle!r}")


class LeadFrontmatter(unittest.TestCase):  # AC-W3-QL-01
    def test_lead_exists(self):
        self.assertTrue(LEAD_PATH.is_file(), LEAD_PATH)

    def test_shape(self):
        head, _ = split(LEAD_PATH)
        self.assertEqual(field(head, "name"), "qa-lead")
        self.assertEqual(field(head, "model"), "sonnet")
        self.assertEqual(field(head, "maxTurns"), "150")
        tools = [t.strip() for t in field(head, "tools").strip("[]").split(",")]
        self.assertEqual(tools, TOOLS)
        self.assertEqual(block_list(head, "skills"), ["graph-engineering:qa-verification"])

    def test_frontmatter_check_passes(self):
        run = subprocess.run(["bash", str(ROOT / "scripts" / "check-agent-frontmatter.sh"), str(ROOT)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertNotIn("qa-lead.md", run.stdout)

    def test_leaves_cannot_nest(self):
        head, _ = split(LEAF_PATH)
        self.assertNotIn("Agent", field(head, "tools"))


class LeadProtocol(Case):  # AC-W3-QL-02
    def setUp(self):
        self.body = flat(split(LEAD_PATH)[1])

    def test_one_message_foreground_homogeneous(self):
        self.has(self.body, "in ONE message", "run_in_background: false",
                 "subagent_type: graph-engineering:qa", "model: sonnet", "homogeneous",
                 "`<run8>:qa-<lane>`", "at most 4 lanes", "Never end a turn with children outstanding")

    def test_leaf_prompt_parts(self):
        self.has(self.body, LEAF_LINE, "case IDs", "base URLs", "`.graph/<run>/qa/<lane>/`",
                 "`.graph/<run>/qa/<lane>.md`", "`.graph/<run>/qa/<lane>-findings.json`",
                 "scripts/lane-run.sh")

    def test_file_reports_merged_from_disk(self):
        self.has(self.body, "from disk", "`.graph/<run>/qa.md`", "`.graph/<run>/qa-findings.json`",
                 "1,500 tokens", "agent id")

    def test_runtime_once_then_teardown_last(self):
        order = [self.body.find(n) for n in (
            "Stand the runtime up once", "in ONE message", "from disk", "`down` as your last call")]
        self.assertNotIn(-1, order, order)
        self.assertEqual(order, sorted(order))
        self.has(self.body, "GRAPH_RUN_ID")


class Leaf(Case):  # AC-W3-QL-03
    def setUp(self):
        self.body = flat(split(LEAF_PATH)[1])

    def test_leaf_mode_paragraph(self):
        self.has(self.body, "**Leaf mode.**", f"`{LEAF_LINE}`", "owned by the lead", "report path",
                 "never `qa.md` or `qa-findings.json`")

    def test_wait_run_line(self):
        self.has(self.body, "hooks/scripts/wait-run.sh")


class Trigger(Case):  # AC-W3-QL-04
    def setUp(self):
        self.text = flat(read(SKILL_PATH))

    def test_lead_trigger(self):
        self.has(read(SKILL_PATH), "## Lead and leaves")
        self.has(self.text, "2+ platforms", "~8+ criteria", "3+ lanes", "`qa-lead`", "2 lanes",
                 "flat", "1 surface", "`runtime.command`", LEAF_LINE)


class Generic(unittest.TestCase):
    def test_no_em_dash_retired_tier_or_consumer_names(self):
        for path in (LEAD_PATH, LEAF_PATH, SKILL_PATH):
            text = read(path)
            self.assertNotIn(chr(0x2014), text, path.name)
            for word in ("fable", "koach", "fitness", "supabase"):
                self.assertNotIn(word, text.lower(), f"{path.name}: {word}")

    def test_lead_under_line_budget(self):
        self.assertLess(len(read(LEAD_PATH).splitlines()), 250)


if __name__ == "__main__":
    unittest.main()
