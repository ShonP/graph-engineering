import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = (ROOT / "docs" / "engine" / "run.md").read_text()
LAND = (ROOT / "docs" / "engine" / "land.md").read_text()
INIT = (ROOT / "commands" / "graph-init.md").read_text()


def step(text, number):
    match = re.search(rf"(?ms)^{number}\. \*\*.*?(?=^\d+\. \*\*|\Z)", text)
    return match.group(0) if match else ""


def paragraph(text, label):
    match = re.search(rf"(?m)^ *\*\*{re.escape(label)}\.\*\*.*$", text)
    return match.group(0) if match else ""


class EngineGate(unittest.TestCase):
    def test_repo_gate_runs_hygiene_and_gate_checks_after_the_test(self):
        gate = step(RUN, 3)
        test = gate.index("run the configured test through")
        for needle in (
            "graph-control hygiene --root <run worktree> --base <run base>",
            "python3 <plugin-root>/hooks/scripts/gate_checks.py <run worktree>",
        ):
            with self.subTest(needle=needle):
                self.assertGreater(gate.find(needle), test)

    def test_gate_verdicts(self):
        gate = step(RUN, 3)
        for needle in ("`FAIL` or exit 2 is a red gate", "exit 77", "`advisory ... blocks from <date>`", "to the ledger"):
            with self.subTest(needle=needle):
                self.assertIn(needle, gate)


class EngineFix(unittest.TestCase):
    def test_fix_rounds_require_receiving_code_review(self):
        fix = step(RUN, 7)
        self.assertIn("`superpowers:receiving-code-review`", fix)
        self.assertIn("reproduce or cite a finding before applying it", fix)


class EngineRunEnd(unittest.TestCase):
    def test_run_end_hygiene_after_the_scoped_gc(self):
        end = step(RUN, 10)
        report = end.index("**Report.**")
        command = end.find("graph-control hygiene --root <main checkout> --run-end <run-id> --branch <run branch>")
        self.assertGreater(command, -1)
        self.assertLess(command, report)
        self.assertLess(end.find("worktree-gc.sh"), command)
        self.assertLess(end.find("git fetch"), command)
        self.assertGreater(end.find("worktree-gc.sh"), -1)

    def test_run_end_verdict_and_no_deletion(self):
        end = step(RUN, 10)
        for needle in ("`RUN-END: CLEAN|DIRTY (<n>)`", "run-report.md", "DIRTY makes the run `PARTIAL`", "nothing is deleted"):
            with self.subTest(needle=needle):
                self.assertIn(needle, end)


class EngineLand(unittest.TestCase):
    def test_pr_body_paths_checked_before_pr_and_push(self):
        land = step(LAND, 9)
        needle = "graph-control hygiene --root <run worktree> --text .graph/<run>/merge.md --only docs"
        check = land.find(needle)
        self.assertGreater(check, -1)
        self.assertLess(check, land.index("gh pr create"))
        self.assertLess(check, land.index("git push origin HEAD:<default>"))
        self.assertIn("fix the exhibit, not the check", land)

    def test_ephemeral_docs_deleted_in_the_same_pr(self):
        land = step(LAND, 9)
        self.assertIn("`hygiene.docs.ephemeral`", land)
        self.assertIn("this run created are deleted in the same PR", land)


class InitProposals(unittest.TestCase):
    def test_quick_gate_names_the_human_side_media_check(self):
        quick = paragraph(INIT, "Quick gate")
        self.assertIn("commit guard needs no setup", quick)
        self.assertIn("`check-added-large-files`", quick)
        self.assertIn("human-side equivalent", quick)

    def test_docs_and_surfaces_roots_come_from_evidence(self):
        docs = step(INIT, 7)
        for needle in ("`hygiene.docs.roots`", "existing doc", "`hygiene.docs.ephemeral`", "plans", "`hygiene.surfaces.roots`", "workspace"):
            with self.subTest(needle=needle):
                self.assertIn(needle, docs)

    def test_checks_only_for_tools_already_in_dev_dependencies(self):
        checks = step(INIT, 9)
        for needle in ("`checks`", "`blocking`", "dev dependencies", "jscpd", "knip", "vulture", "periphery"):
            with self.subTest(needle=needle):
                self.assertIn(needle, checks)
        self.assertIn("a native no-comments lint (ruff, eslint) comes before `hygiene.comments`", checks)

    def test_each_proposal_waits_for_approval(self):
        for number in (7, 9):
            with self.subTest(step=number):
                self.assertIn("written only on approval", step(INIT, number))


if __name__ == "__main__":
    unittest.main()
