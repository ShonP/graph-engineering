"""AC-QA-SELFCHECK: every qa that writes a findings file validates it, leaf or not.

Stdlib only, so it runs with plain `python3 -m unittest discover -s tests/agents`.
"""

import re
import unittest
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[2] / "agents"
CHECK = "uv run <plugin-root>/scripts/graph-control.py findings <path>"
LEAF_PARAGRAPHS = ("**Leaf mode.**", "**Leaf files.**")


def paragraphs(name):
    return [block.strip() for block in (AGENTS / name).read_text(encoding="utf-8").split("\n\n")]


class QaSelfCheck(unittest.TestCase):
    def test_qa_validates_every_findings_file_outside_the_leaf_paragraphs(self):
        unconditional = [block for block in paragraphs("qa.md")
                         if CHECK in block and not block.startswith(LEAF_PARAGRAPHS)]
        self.assertEqual(len(unconditional), 1, "qa.md: one unconditional findings self-check sentence")
        self.assertRegex(unconditional[0], r"every findings file you write")
        self.assertRegex(unconditional[0], r"until it exits 0")

    def test_qa_names_the_check_once(self):
        text = (AGENTS / "qa.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("graph-control.py findings"), 1)

    def test_qa_lead_merge_step_still_validates_the_merged_file(self):
        lines = (AGENTS / "qa-lead.md").read_text(encoding="utf-8").splitlines()
        step = next(line for line in lines if re.match(r"5\. \*\*Merge from disk", line))
        self.assertIn(CHECK, step)
        self.assertIn("until it exits 0", step)


if __name__ == "__main__":
    unittest.main()
