"""Contract checks for ready-set dispatch, state-built resumes, fix-round test scope and the engine wakeup.

The engine is prose, so these tests pin the load-bearing rules by the tokens a
reader (and a grep) keys on. Source: the 2026-10-09 session retro (A3, A4, C6,
C7): wave barriers cost 60+ min per feature chain, a resume written as prose
re-oriented the agent from scratch, fix rounds re-ran a full suite per finding,
and a turn that ended with only background work left the run idle for 62 min.
Nothing here may name one consumer's stack, app or paths.
"""
import re
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from test_playbooks import engine_text, steps

ROOT = Path(__file__).resolve().parents[2]


class ReadySetDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.steps = steps(engine_text())

    def assert_tokens(self, body, tokens):
        for token in tokens:
            with self.subTest(token=token):
                self.assertIn(token, body)

    def test_a_task_dispatches_the_moment_its_dependencies_are_gated(self):
        self.assert_tokens(self.steps[3], (
            "the moment its last `depends_on` task is `gated`",
            "never wait for a sibling",
            "No wave barrier",
        ))

    def test_ledger_rows_time_each_task_from_dispatch_to_gate(self):
        self.assert_tokens(self.steps[3], (
            "- <ts> dispatch <task> <agent>",
            "- <ts> merged <task> <merge sha>",
            "- <ts> gated <task>",
            "ready lag",
        ))

    def test_the_wave_view_stays_display_only(self):
        self.assertIn("`waves` stays a display aid only", self.steps[3])


class ResumeFromState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.steps = steps(engine_text())
        cls.execution = "".join(cls.steps[n] for n in (3, 4))

    def test_the_resume_message_is_built_from_git_state(self):
        for token in (
            "Resume from state, not prose",
            "git -C <worktree> log --oneline <base sha>..HEAD",
            "git -C <worktree> status --short",
            "last test command",
            "done_cases",
            "--git-path graph-checkpoint.md",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.execution)

    def test_a_prose_continue_is_forbidden(self):
        self.assertIn('never "continue where you stopped"', self.execution)


class FixRoundTestScope(unittest.TestCase):
    def test_fix_round_dispatch_scopes_tests_to_the_findings(self):
        fix = steps(engine_text())[7]
        self.assertIn("targeted tests on the files and classes the findings name", fix)
        self.assertIn("exactly one full suite at the end of the round", fix)


class EngineWakeup(unittest.TestCase):
    def test_a_turn_ending_on_background_work_schedules_a_wakeup(self):
        body = "".join(steps(engine_text())[n] for n in (3, 4))
        for token in (
            "Fallback wakeup",
            "every in-flight item is in the background",
            "10 minutes",
            "- <ts> wake",
            "No heartbeat nudges",
        ):
            with self.subTest(token=token):
                self.assertIn(token, body)

    def test_the_wakeup_never_kills_a_child(self):
        body = "".join(steps(engine_text())[n] for n in (3, 4))
        wake = re.search(r"\*\*Fallback wakeup\.\*\*(.*?)(?=\n\n|\Z)", body, re.S)
        self.assertIsNotNone(wake)
        self.assertIn("never kills", wake.group(1))


if __name__ == "__main__":
    unittest.main()
