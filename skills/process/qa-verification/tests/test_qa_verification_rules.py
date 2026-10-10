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
        for needle in ("once per merge unit", "stood up once", "never once per task"):
            self.assertIn(needle, text)
        self.assertNotIn("or wave", text)

    def test_findings_file_uses_the_review_protocol_schema(self):
        text = flat(SKILL)
        self.assertIn('"schema_version": 1', text)
        self.assertIn("an empty `findings` list", text)
        self.assertNotIn("`[]` when there is nothing", text)

    def test_runtime_command_points_at_the_contract(self):
        for needle in ("references/harness-contract.md", "templates/qa-harness.sh"):
            self.assertIn(needle, SKILL)


STANDALONE_RULES = (
    "If `runtime.none` holds a reason, skip this step", "public surface",
    "fresh shell", "`GRAPH_RUN_ID=<the run id from your dispatch>`", "`${GRAPH_RUN_ID:?}` fails loudly",
    "`runtime.env`", "never write their values",
    "isolation check", "exits 0",
    "`lsof -nP -iTCP:<port> -sTCP:LISTEN`", "A taken port is `BLOCKED`",
    "`-p ge-${GRAPH_RUN_ID:?}`",
    "`curl -fsS --max-time 5 --retry <n> --retry-delay 2 --retry-max-time <timeout> "
    "--retry-connrefused --retry-all-errors <url>`",
    "`health.expect`", "run its `command`", "then run `seed`",
    "Run `down` as its own final call, whatever the outcome", "Never a `trap`",
    "an empty `up`, `baseUrl` or `health`", "not exported", "health never passing",
    "README / CLAUDE.md only to fill a gap", "seeded, deterministic data", "never a shared environment",
    "`post-deploy` node", "`post-deploy-verification`", "no hostile probes",
)
STEP_LINE_CAP = 400


def stand_up_step():
    return SKILL.split("2. **Stand the system up", 1)[1].split("\n3. **Verify each criterion", 1)[0]


def standalone_block():
    return flat(stand_up_step().split("**Standalone runtime.**", 1)[1].split("**Compose isolation check.**", 1)[0])


class StandaloneRuntime(unittest.TestCase):
    def test_every_rule_survives(self):
        block = standalone_block()
        for needle in STANDALONE_RULES:
            with self.subTest(needle=needle):
                self.assertIn(needle, block)

    def test_rules_run_in_order(self):
        block = standalone_block()
        order = ["isolation check", "`lsof", "Run `up`", "then run `seed`", "Run `down`"]
        positions = [block.index(needle) for needle in order]
        self.assertEqual(positions, sorted(positions))

    def test_no_narration_and_short_lines(self):
        step = stand_up_step()
        self.assertNotIn("(spiked)", step)
        long_lines = [line[:60] for line in step.splitlines() if len(line) > STEP_LINE_CAP]
        self.assertEqual(long_lines, [])


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
