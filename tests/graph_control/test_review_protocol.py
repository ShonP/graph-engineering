"""review-protocol and reviewer.md carry the findings.json contract (AC-W2-FD-04).

The JSON example in the skill is a golden case: it must validate with the same
parser the engine runs, so the documented schema cannot drift from the code.
"""

import json
import re
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.findings import Findings

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/process/review-protocol/SKILL.md"
REVIEWER = ROOT / "agents/reviewer.md"
RETURN_LINE = "`PASS|CHANGES-REQUESTED blocking=<n> important=<m> findings=<path>`"
PIPE_FORMAT = "severity | file:line"
EM_DASH = chr(0x2014)


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if match is None:
        raise AssertionError(f"no `## {heading}` section")
    return match.group(1)


def flat(text):
    """Prose with its line wrapping removed, so a check does not depend on where a line breaks."""
    return " ".join(text.split())


class ReviewProtocol(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text()

    def test_schema_example_validates(self):
        blocks = re.findall(r"```json\n(.*?)```", self.text, re.S)
        self.assertEqual(len(blocks), 1, "exactly one json example")
        example = blocks[0].replace("<base sha>", "a" * 40).replace("<head sha>", "b" * 40)
        self.assertEqual(Findings.parse(json.loads(example)).verdict, "CHANGES-REQUESTED")

    def test_findings_section_replaces_the_pipe_format(self):
        body = flat(section(self.text, "Findings file"))
        for needle in ("findings.json", "qa-findings.json", "graph-control.py findings <path>", "0.8", RETURN_LINE):
            self.assertIn(needle, body)
        self.assertNotIn(PIPE_FORMAT, self.text)

    def test_route_semantics(self):
        body = section(self.text, "Routes")
        for route, goes_to in [("patch", "fix loop"), ("bad_plan", "plan diff"),
                               ("intent_gap", "decision card"), ("defer", "followups.md")]:
            with self.subTest(route):
                self.assertRegex(body, rf"`{route}`[^\n]*{re.escape(goes_to)}")

    def test_re_review_input(self):
        body = flat(section(self.text, "Re-review"))
        for needle in ("open blocking and important findings", "<last reviewed head>..HEAD", "not the whole branch"):
            self.assertIn(needle, body)

    def test_round_three_escalates_one_tier(self):
        body = flat(section(self.text, "Re-review"))
        self.assertIn("Round 3 escalates one tier", body)
        for needle in ("`implementer-simple`", "`implementer`", "systematic-debugging", "opus"):
            self.assertIn(needle, body)

    def test_instruction_paths_decide_depth(self):
        body = flat(section(self.text, "Review depth"))
        for needle in ("instructionPaths", "full review", "`lint`", "no LLM review",
                       "by file type", "never by directory", "requirements.txt",
                       "`agent-control`", "no reviewer is dispatched", "lint.argv", "review receipt"):
            self.assertIn(needle, body)


class Reviewer(unittest.TestCase):
    def test_report_points_to_the_schema_and_keeps_the_return_line(self):
        body = flat(section(REVIEWER.read_text(), "Report"))
        for needle in ("findings.json", "review-protocol", "Write tool", "graph-control findings", RETURN_LINE):
            self.assertIn(needle, body)
        self.assertNotIn(PIPE_FORMAT, body)


class Style(unittest.TestCase):
    def test_no_em_dashes(self):
        scripts = ROOT / "scripts/graph_control"
        tests = Path(__file__).resolve().parent
        for path in (SKILL, REVIEWER, scripts / "findings.py", scripts / "commands/findings.py",
                     tests / "test_findings.py", Path(__file__).resolve()):
            with self.subTest(path.name):
                self.assertNotIn(EM_DASH, path.read_text())


if __name__ == "__main__":
    unittest.main()
