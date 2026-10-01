"""Golden checks for the qa verdict rules, the harness contract and the qa agent.

Stdlib only; run by scripts/check-skill-scripts.sh. Guards AC-W2-QA-01.
"""

import json
import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
REPORT_KEYS = {"run_id", "candidate", "runtime_instance", "cases", "executed", "skipped", "exit_code"}


def read(path):
    return path.read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text)


SKILL = read(SKILL_DIR / "SKILL.md")
CONTRACT_PATH = SKILL_DIR / "references" / "harness-contract.md"
AGENT = read(ROOT / "agents" / "qa.md")


class VerdictRules(unittest.TestCase):
    def test_three_statuses_and_any_other_reads_blocked(self):
        text = flat(SKILL)
        for needle in (
            "exactly `VERIFIED`, `FAILED` or `BLOCKED`",
            "reads as `BLOCKED`",
            "A `FAILED` sub-check fails its row",
        ):
            self.assertIn(needle, text)

    def test_verdict_line(self):
        text = flat(SKILL)
        for needle in (
            "`PASS` only when every required row is `VERIFIED`",
            "`FAIL INCOMPLETE: <row ids>` when any row is `FAILED`",
            "otherwise `INCOMPLETE: <row ids>`",
        ):
            self.assertIn(needle, text)

    def test_other_statuses_only_in_the_rule_text(self):
        lines = [line for line in SKILL.splitlines() if "N/A" in line or "NOT RUN" in line]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("reads as `BLOCKED`", lines[0])

    def test_once_per_merge_unit(self):
        text = flat(SKILL)
        for needle in ("once per merge unit or wave", "stood up once", "never once per task"):
            self.assertIn(needle, text)

    def test_findings_file_uses_the_review_protocol_schema(self):
        text = flat(SKILL)
        self.assertIn('"schema_version": 1', text)
        self.assertIn("an empty `findings` list", text)
        self.assertNotIn("`[]` when there is nothing", text)

    def test_runtime_command_points_at_the_contract(self):
        for needle in ("references/harness-contract.md", "templates/qa-harness.sh"):
            self.assertIn(needle, SKILL)


class HarnessContract(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CONTRACT_PATH.is_file(), CONTRACT_PATH)
        self.text = flat(read(CONTRACT_PATH))

    def test_required_duties(self):
        for needle in (
            "GRAPH_RUN_ID", "worktree root", "first argument", ".graph/<run>/qa/<case-id>/",
            "Teardown always runs", "playwright-cli", "axe", "GE_HARNESS_HOOKS",
            "ge_setup", "ge_checks", "ge_teardown", "uncommitted",
        ):
            self.assertIn(needle, self.text)

    def test_app_helpers_stay_in_the_consumer(self):
        for needle in ("login", "throwaway", "consuming repo", "run directory"):
            self.assertIn(needle, self.text)

    def test_report_example_has_exactly_the_contract_keys(self):
        block = re.search(r"```json\n(.*?)```", read(CONTRACT_PATH), re.S)
        self.assertIsNotNone(block)
        doc = json.loads(block.group(1))
        self.assertEqual(set(doc), REPORT_KEYS)
        self.assertEqual(set(doc["candidate"]), {"revision", "dirty_sha256"})
        self.assertEqual(set(doc["cases"][0]), {"id", "status", "evidence"})


class QaAgent(unittest.TestCase):
    def test_agent_points_at_merge_unit_and_contract(self):
        text = flat(AGENT)
        self.assertIn("once per merge unit", text)
        self.assertIn("references/harness-contract.md", text)


if __name__ == "__main__":
    unittest.main()
