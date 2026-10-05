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
            "Every implementer task gets its own worktree",
            "git worktree add -b <run-id>-<task> <path> <run branch head SHA>",
            "git merge --no-ff <run-id>-<task>",
            "`bootstrap:`",
            "GRAPH_RUN_ID",
            "git merge-base --is-ancestor <base sha> HEAD",
            "BLOCKED",
            "completion order",
            "decision card",
            "git merge --no-ff",
            "scripts/worktree-gc.sh --apply --base <run branch> --prefix <run-id>-",
        ))
        self.assertIn("keeps the run worktree", self.steps[2])
        self.assertNotIn("plan order", self.steps[2])

    def test_ac_en_1_merges_serialize_and_a_conflict_parks_only_its_chain(self):
        # Two tasks finishing together merge back to back and share one gate.
        self.assert_tokens(self.steps[2], (
            "own fix loop exits",
            "Merges are serialized by the engine",
            "back to back",
            "share one repo gate",
            "parks that task and its dependents only",
            "other ready tasks keep running",
        ))

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

    def test_ac_en_1_merge_removes_only_its_own_worktree(self):
        # The scoped gc removes any clean worktree behind the run tip, so on a ready queue it can
        # delete a sibling task's fresh worktree before its implementer writes.
        self.assert_tokens(self.steps[2], (
            "git worktree remove <path>",
            "git branch -d <run-id>-<task>",
            "only once, when no task is running",
        ))
        self.assertNotIn("--force", self.steps[2])
        self.assertNotIn("branch -D", self.steps[2])

    def test_ac_w3_ep_01_task_branches_key_on_the_full_run_id(self):
        # <run8> is a UUIDv7's timestamp head, shared by runs opened within ~65 s: as a
        # branch or gc key it lets one run delete another's fresh worktree (fix round 2).
        for token in ("-b <run8>", "--no-ff <run8>", "--prefix <run8>"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.text)

    def test_ac_w3_ep_01_host_isolation_is_never_offered(self):
        self.assertIsNone(re.search(r"isolation\W{0,3}worktree", self.text))

    def test_ac_w3_ep_02_ready_queue_host_check_background_gate_lanes(self):
        self.assert_tokens(self.steps[3], (
            "graph-control ready <run>/plan.json --done <ids> --running <ids> --max-width <n>",
            "Semaphore, not barrier: at most 4 concurrent writers",
            "Reviewers and qa do not",
            "graph-control host-check --root <run worktree> --profile <profile>",
            "decision card",
            "run_in_background: true",
            "recompute the ready set and fill free slots",
            "same agent type",
            "only the prompt",
            "its own review leg",
            "its own fix loop (step 7) in its own worktree, then merges",
            "Repo gate per merge batch",
            "Dependents are released only after the gate passes",
            "graph-control check <root> --reuse",
            "hooks/scripts/wait-run.sh --full",
            "`lanes:`",
            "scripts/lane-run.sh <lane> --slots <n> -- <cmd>",
        ))

    def test_ac_en_1_no_wave_barrier_survives(self):
        for token in ("No pipelining", "once per wave", "Implementation waves", "run_in_background: false",
                      "the next wave waits"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.text)
        self.assertIn("display aid", self.steps[3])

    def test_ac_en_1_host_cap_and_gate_queue(self):
        # Observed on this repo's own run: the host cap also binds reviewers and qa, and a merge
        # into the run worktree while its gate runs corrupts the gate.
        self.assert_tokens(self.steps[3], (
            "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS",
            "writers plus reviewers and qa",
            "queue behind a running gate",
        ))

    def test_ac_en_1_qa_is_batched_per_merge_unit(self):
        self.assert_tokens(self.steps[3], (
            "one qa leg per merge unit",
            "after its last task merges",
            "count as done when the last task merged and the qa loop exited",
        ))

    def test_ac_en_1_elapsed_check_never_kills(self):
        self.assert_tokens(self.steps[3], (
            "the engine's own dispatch time in the ledger, not the agent's self-report",
            "60 minutes",
            "over budget",
            "`over-budget <task> <min>`",
            "never kills or pre-empts",
        ))

    def test_ac_en_1_lanes_point_at_the_host_resource_rule(self):
        self.assert_tokens(self.steps[3], ("docs/engine/lanes.md", "Host resource lanes", "per-task namespace"))

    def test_ac_en_1_partial_becomes_a_remainder_task(self):
        self.assert_tokens(self.steps[4], (
            "`PARTIAL`", "`green_commit`", "`done_cases`", "`remaining_cases`", "`remaining_scope`",
            "`elapsed_min`", "`depends_on: [<id>]`", "`estimate_min` <= 45", "tasks/<id>b.md",
            "validate-plan", "validate-briefs", "readiness preflight", "plan hash changed",
            "`- <ts> PARTIAL <id> -> <id>b (<k> cases left)`", "not a fix round",
            "A remainder of a remainder is a decision card",
        ))

    def test_ac_en_1_partial_with_nothing_green(self):
        # green_commit equal to the dispatch base means nothing was green.
        self.assert_tokens(self.steps[4], (
            "`green_commit` equal to the dispatch base SHA",
            "counts as merged with no change",
            "`<id>b` is ready at once",
        ))

    def test_ac_en_1_ids_per_writer_dispatch(self):
        self.assert_tokens(self.steps[4], (
            "`<run-id>-t<n>`", "`<run-id>-t<n>b`", "`<run-id>-t<n>-r<N>`", "full-suite count",
        ))

    def test_ac_en_1_estimate_uses_the_critical_path(self):
        self.assertIn("critical path <d>", self.steps[4])
        self.assertNotIn("<waves> waves", self.text)

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
