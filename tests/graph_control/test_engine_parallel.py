"""Contract checks for the engine's parallel execution: waves, worktrees, leads, retries, estimates.

The engine is prose, so these tests pin the load-bearing rules by the tokens a
reader (and a grep) keys on. Case ids are the wave 3 acceptance rows
(AC-W3-EP-*). The engine is generic: nothing here may name one consumer's
stack, app or paths.
"""
import re
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from test_playbooks import steps

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "commands" / "graph-ship.md"


class EngineParallelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = ENGINE.read_text()
        cls.steps = steps(cls.text)
        cls.execution = "".join(cls.steps[n] for n in (2, 3, 4))

    def assert_tokens(self, body, tokens):
        for token in tokens:
            with self.subTest(token=token):
                self.assertIn(token, body)

    def test_ac_w3_ep_01_per_task_worktrees_from_the_run_branch(self):
        self.assert_tokens(self.steps[2], (
            "superpowers:using-git-worktrees",
            "2+ writers",
            "git worktree add -b <run8>-<task> <path> <run branch head SHA>",
            "`bootstrap:`",
            "GRAPH_RUN_ID",
            "git merge-base --is-ancestor <base sha> HEAD",
            "BLOCKED",
            "plan order",
            "decision card",
            "scripts/worktree-gc.sh --apply",
        ))
        self.assertIn("keeps the run worktree", self.steps[2])

    def test_ac_w3_ep_01_host_isolation_is_never_offered(self):
        self.assertIsNone(re.search(r"isolation\W{0,3}worktree", self.text))

    def test_ac_w3_ep_02_waves_host_check_one_message_gate_lanes(self):
        self.assert_tokens(self.steps[3], (
            "graph-control waves <run>/plan.json --max-width <n>",
            "at most 4 concurrent opus writers",
            "graph-control host-check --root <run worktree> --profile <profile>",
            "decision card",
            "ONE message",
            "run_in_background: false",
            "same agent type",
            "only the prompt",
            "No pipelining",
            "fix loop exits",
            "once per wave",
            "graph-control check <root> --reuse",
            "hooks/scripts/wait-run.sh",
            "`lanes:`",
            "scripts/lane-run.sh <lane> --slots <n> -- <cmd>",
        ))

    def test_ac_w3_ep_03_lead_triggers_and_depth(self):
        self.assert_tokens(self.steps[4], (
            "`qa-lead`",
            "2+ platforms",
            "~8+ criteria",
            "3+ lanes",
            "two `qa` leaves",
            "`reviewer-lead`",
            "~2,000 changed lines",
            "~120k diff tokens",
            "explicit lens list",
            "blocker reproduction",
            "only at depth 1",
            "never have the Agent tool",
            "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2",
            "/graph-init",
            "child ids",
            "report paths",
        ))

    def test_ac_w3_ep_04_retries_and_429(self):
        self.assert_tokens(self.execution, (
            "5xx", "529", "429",
            "fresh from on-disk artifacts",
            "at most 3 attempts",
            "one ledger row each",
            "first 429",
            "stop new fan-out",
            "checkpoint the ledger",
            "reset time",
            "--resume",
            "No heartbeat nudges",
            "status line",
        ))

    def test_ac_w3_ep_04_estimate_and_actuals(self):
        self.assert_tokens(self.execution, (
            "plan gate",
            "scripts/session_usage.py",
            "--medians",
            "30 days",
            "wall time",
            "--run <run8>",
            "2x",
        ))

    def test_ac_w3_ep_05_file_stays_within_budget(self):
        self.assertLessEqual(len(self.text.splitlines()), 250)

    def test_engine_is_generic(self):
        lowered = self.text.lower()
        for name in ("koach", "fitness", "pnpm", "xcodegen", "xcodebuild", "supabase"):
            with self.subTest(name=name):
                self.assertNotIn(name, lowered)


if __name__ == "__main__":
    unittest.main()
