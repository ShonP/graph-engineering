"""Golden checks for the loop-speed contracts from the 2026-10-09 session retro.

Stdlib only, like test_implementer_budget.py. Pins: the implementer's fix-round
test scope (C7) and progress checkpoint (C6), the quick gate before DONE (the
12 push-time-only failures), and the retro agent writing its report early under
a raised turn cap (both retro agents stopped at 40 turns mid-analysis).
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

CHECKPOINT_PATH = "git rev-parse --path-format=absolute --git-path graph-checkpoint.md"
ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTER = ROOT / "agents" / "implementer.md"
RETRO = ROOT / "agents" / "retro.md"
DOD = ROOT / "skills" / "process" / "definition-of-done" / "SKILL.md"
TEMPLATE = ROOT / "templates" / "graph-profile.yaml"


def section(text, heading):
    match = re.search(rf"(?ms)^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text)
    return match.group(1) if match else ""


def turns(path):
    return int(re.search(r"(?m)^maxTurns: (\d+)$", path.read_text()).group(1))


class ImplementerFixRounds(unittest.TestCase):
    def test_fix_rounds_run_targeted_tests_then_one_full_suite(self):
        fix = section(IMPLEMENTER.read_text(), "Fix rounds")
        self.assertIn("targeted tests on the files and classes the findings name", fix)
        self.assertIn("exactly one full suite at the end of the round", fix)
        self.assertIn("wait-run.sh --full", fix)


class ImplementerCheckpoint(unittest.TestCase):
    def test_checkpoint_at_85_percent_of_turns(self):
        box = section(IMPLEMENTER.read_text(), "Time-box")
        for token in ("85%", CHECKPOINT_PATH, "outside the working tree", "last test command"):
            with self.subTest(token=token):
                self.assertIn(token, box)

    def test_no_surface_puts_the_checkpoint_in_the_working_tree(self):
        # Review F2: an untracked checkpoint at the worktree root makes the never-forced remove fail.
        for path in (IMPLEMENTER, ROOT / "docs" / "engine" / "run.md"):
            with self.subTest(path=path.name):
                self.assertNotIn(".graph-checkpoint.md", path.read_text())

    def test_a_checkpoint_at_the_git_path_does_not_block_worktree_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, tree = Path(tmp) / "repo", Path(tmp) / "tree"
            git = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
            subprocess.run([*git, "init", "-q", str(repo)], check=True)
            subprocess.run([*git, "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "base"], check=True)
            subprocess.run([*git, "-C", str(repo), "worktree", "add", "-q", str(tree)], check=True)
            where = subprocess.run(["git", "-C", str(tree), "rev-parse", "--path-format=absolute",
                                    "--git-path", "graph-checkpoint.md"],
                                   check=True, capture_output=True, text=True).stdout.strip()
            Path(where).write_text("base: x\nnext: y\n")
            status = subprocess.run(["git", "-C", str(tree), "status", "--short"],
                                    check=True, capture_output=True, text=True).stdout
            self.assertEqual(status, "", "the checkpoint must not be an untracked file")
            removed = subprocess.run(["git", "-C", str(repo), "worktree", "remove", str(tree)],
                                     capture_output=True, text=True)
            self.assertEqual(removed.returncode, 0, removed.stderr)

    def test_turn_count_matches_the_frontmatter_cap(self):
        cap = turns(IMPLEMENTER)
        self.assertIn(f"about {int(cap * 0.85)} of your {cap} turns", IMPLEMENTER.read_text())


class QuickGateBeforeDone(unittest.TestCase):
    def test_definition_of_done_runs_the_declared_quick_gate(self):
        text = DOD.read_text()
        self.assertIn("`gates.quick`", text)
        self.assertIn("before reporting `DONE`", text)

    def test_implementer_report_names_the_quick_gate(self):
        report = section(IMPLEMENTER.read_text(), "Report")
        self.assertIn("`gates.quick`", report)

    def test_template_declares_the_key_empty(self):
        gates = re.search(r"(?ms)^gates:\n(.*?)(?=^\S)", TEMPLATE.read_text()).group(1)
        self.assertRegex(gates, r'(?m)^  quick: ""')


class RetroWritesEarly(unittest.TestCase):
    def test_turn_cap_raised_past_40(self):
        self.assertGreaterEqual(turns(RETRO), 100)

    def test_report_written_early_and_refined(self):
        text = RETRO.read_text()
        self.assertIn("Write `<run>/retro.md` early", text)
        self.assertIn("refine it", text)


class NoEmDash(unittest.TestCase):
    def test_touched_files_hold_no_em_dash(self):
        for path in (IMPLEMENTER, RETRO, DOD, ROOT / "docs" / "engine" / "run.md"):
            with self.subTest(path=path.name):
                self.assertNotIn("\u2014", path.read_text())


if __name__ == "__main__":
    unittest.main()
