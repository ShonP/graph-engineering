"""Panel review by diff slice: reviewer-lead, reviewer leaf mode, review-protocol Panel.

Golden greps over prompt text (AC-W3-RP-01..04); the behavioural half is the
owner's release check R5. Stdlib only, like the rest of tests/agents.
"""

import re
import unittest
from pathlib import Path

from test_roster_policy import split

ROOT = Path(__file__).resolve().parents[2]
LEAD = ROOT / "agents/reviewer-lead.md"
REVIEWER = ROOT / "agents/reviewer.md"
PROTOCOL = ROOT / "skills/process/review-protocol/SKILL.md"
VERDICT = "`PASS|CHANGES-REQUESTED blocking=<n> important=<m> findings=<path>`"
LEAF_FILE = "`.graph/<run>/review/<slice>.json`"
# App names and stack tools that would tie the panel to one consumer repo.
CONSUMER_SPECIFIC = ("koach", "fitness", "supabase", "pnpm", "xcodebuild", "swiftui", "nestjs", "fastapi")


def flat(text):
    """Prose with its line wrapping removed, so a check does not depend on where a line breaks."""
    return " ".join(text.split())


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if match is None:
        raise AssertionError(f"no `## {heading}` section")
    return match.group(1)


class ReviewerLead(unittest.TestCase):
    def setUp(self):
        self.fm, body = split(LEAD)
        self.body = flat(body)

    def has(self, *needles):
        for needle in needles:
            with self.subTest(needle=needle):
                self.assertIn(needle, self.body)

    def test_frontmatter(self):  # AC-W3-RP-01
        self.assertEqual(self.fm["name"], "reviewer-lead")
        self.assertEqual(self.fm["model"], "opus")
        self.assertEqual(self.fm["maxTurns"], "120")
        self.assertEqual(self.fm["tools"], ["Read", "Grep", "Glob", "Bash", "Write", "Agent", "Skill"])
        self.assertEqual(self.fm["skills"], split(REVIEWER)[0]["skills"])

    def test_leaves_cannot_nest(self):  # AC-W3-RP-01: only the lead gets Agent
        self.assertNotIn("Agent", split(REVIEWER)[0]["tools"])

    def test_dispatch_is_one_message_of_opus_leaves(self):  # AC-W3-RP-02
        self.has("at most 4 slices", "ONE message", "`subagent_type: graph-engineering:reviewer`",
                 "`model: opus`", "never a cheaper leaf", "`run_in_background: false`",
                 "`<run8>:review-<slice>`", LEAF_FILE)

    def test_leaf_prompt_carries_the_slice_contract(self):  # AC-W3-RP-02
        self.has("file list", "every REQUIRED lens", "acceptance criteria", "findings schema")

    def test_one_read_per_leaf(self):  # AC-W3-RP-02
        self.has("one read", "no per-lens leaves", "no verifier leaves")

    def test_merge_dedupe_refute_from_files(self):  # AC-W3-RP-02
        self.has("Merge", "same `file`", "within 3", "same `rule`", "reproduce", "findings.json",
                 "from its file, never from its reply")

    def test_return_names_each_leaf(self):  # AC-W3-RP-02
        self.has("agent id", "leaf file", VERDICT)


class ReviewerLeafMode(unittest.TestCase):
    def test_leaf_mode(self):  # AC-W3-RP-03
        body = flat(section(REVIEWER.read_text(encoding="utf-8"), "Leaf mode"))
        for needle in ("reviewer-lead", "only the slice", LEAF_FILE, "path the dispatch names",
                       "every REQUIRED lens", VERDICT):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)


class ProtocolPanel(unittest.TestCase):
    def setUp(self):
        self.body = flat(section(PROTOCOL.read_text(encoding="utf-8"), "Panel"))

    def test_trigger(self):  # AC-W3-RP-04
        for needle in ("`panel`", "2,000 changed lines", "120k diff tokens", "`reviewer-lead`",
                       "explicit lens list", "reproduces every blocking finding"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.body)

    def test_dedupe_and_refute_rules(self):  # AC-W3-RP-04
        for needle in ("same `file`", "within 3", "same `rule`", "does not reproduce", "no verifier leaves"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.body)


class Style(unittest.TestCase):
    def test_no_em_dash_and_short_files(self):
        for path in (LEAD, REVIEWER, PROTOCOL, Path(__file__).resolve()):
            with self.subTest(path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(chr(0x2014), text)
                self.assertLess(len(text.splitlines()), 250)

    def test_generic_for_every_stack(self):
        texts = {
            "reviewer-lead": LEAD.read_text(encoding="utf-8"),
            "reviewer Leaf mode": section(REVIEWER.read_text(encoding="utf-8"), "Leaf mode"),
            "review-protocol Panel": section(PROTOCOL.read_text(encoding="utf-8"), "Panel"),
        }
        for where, text in texts.items():
            for word in CONSUMER_SPECIFIC:
                with self.subTest(where=where, word=word):
                    self.assertNotIn(word, text.lower())


if __name__ == "__main__":
    unittest.main()
