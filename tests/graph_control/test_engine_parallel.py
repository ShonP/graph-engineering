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
from test_playbooks import ENGINE, engine_text, steps

ROOT = Path(__file__).resolve().parents[2]


class EngineParallelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = engine_text()
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
            "git worktree add -b <run-id>-<task> <path> <run branch head SHA>",
            "git merge --no-ff <run-id>-<task>",
            "`bootstrap:`",
            "GRAPH_RUN_ID",
            "git merge-base --is-ancestor <base sha> HEAD",
            "BLOCKED",
            "plan order",
            "decision card",
            "git merge --no-ff",
            "scripts/worktree-gc.sh --apply --base <run branch> --prefix <run-id>-",
        ))
        self.assertIn("keeps the run worktree", self.steps[2])

    def test_ac_w3_ep_01_gc_is_always_scoped_to_the_run(self):
        # Unscoped, --apply removes other sessions' freshly cut worktrees (fix round 1, blocking).
        calls = re.findall(r"worktree-gc\.sh[^`]*", self.text)
        self.assertTrue(calls)
        for call in calls:
            with self.subTest(call=call):
                if "--apply" in call:
                    self.assertIn("--prefix <run-id>-", call)
                    self.assertIn("--base <run branch>", call)
        self.assertNotIn("At run end, run", self.steps[2])

    def test_ac_w3_ep_01_task_branches_key_on_the_full_run_id(self):
        # <run8> is a UUIDv7's timestamp head, shared by runs opened within ~65 s: as a
        # branch or gc key it lets one run delete another's fresh worktree (fix round 2).
        for token in ("-b <run8>", "--no-ff <run8>", "--prefix <run8>"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.text)

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
            "2 lanes",
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

    def test_ac_w3_ep_03_qa_lanes_always_have_a_lead_agent(self):
        # The engine never owns a qa runtime: two flat leaves under the engine raced on `down`.
        (leads,) = [line for line in self.steps[4].splitlines() if "**Leads.**" in line]
        qa = leads.split("Review:")[0]
        self.assertRegex(qa, r"2 lanes[^;.]*`qa-lead`")
        self.assertNotIn("dispatched flat", qa)
        self.assertNotIn("two `qa` leaves", qa)

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
        self.assertLessEqual(len(ENGINE.read_text().splitlines()), 250)

    def test_engine_is_generic(self):
        lowered = self.text.lower()
        for name in ("koach", "fitness", "pnpm", "xcodegen", "xcodebuild", "supabase"):
            with self.subTest(name=name):
                self.assertNotIn(name, lowered)


if __name__ == "__main__":
    unittest.main()
