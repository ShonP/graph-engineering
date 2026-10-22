"""The `task-gate` command over SYNTHETIC run directories.

Task ids, briefs, reports and evidence paths are invented shapes, not a real run's artifacts.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import dump, plan_data
from graph_control import cli
from graph_control.commands import iter_commands

EVIDENCE = "docs/ux/changes/x.png"
REQUIRED = "REQUIRED skills: graph-engineering:uv, graph-engineering:backend-rules\n"
LOADED = "skills_loaded: graph-engineering:uv, graph-engineering:backend-rules\n"
PARTIAL_REASON = ("PARTIAL never gates: mark it superseded once its green commit's gate passes; "
                  "T1b carries the rest")


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


class TaskGate(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.run = self.repo / ".graph" / "run-1"
        (self.run / "tasks").mkdir(parents=True)
        data = {**plan_data(), "schema_version": 2}
        data["cases"][0]["evidence"] = EVIDENCE
        dump(self.run / "plan.json", data)
        self.brief(f"# T1\n\n{REQUIRED}\n## Steps\n")
        self.evidence(self.repo)
        self.report_path = self.repo / "report.md"

    def brief(self, body):
        (self.run / "tasks" / "T1.md").write_text(body)

    def evidence(self, root):
        path = root / EVIDENCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")

    def gate(self, report, *extra):
        self.report_path.write_text(report)
        return invoke(["task-gate", str(self.run), "--task", "T1", "--report", str(self.report_path), *extra])

    def blocked(self, report, reason, *extra):
        self.assertEqual(self.gate(report, *extra), (1, {"status": "BLOCKED", "reason": reason}))

    def test_registered_as_plugin(self):
        self.assertIn("task-gate", [module.NAME for module in iter_commands()])

    def test_ac_s9_accept_done_and_done_with_concerns_gate(self):
        for status in ("DONE", "DONE_WITH_CONCERNS"):
            with self.subTest(status=status):
                self.assertEqual(self.gate(f"Status: {status}\n\nwork\n\n{LOADED}"),
                                 (0, {"status": "PASS", "task": "T1", "gated": True}))

    def test_status_line_shapes(self):
        for line in ("DONE", "**Status:** DONE", "status: DONE.", "## STATUS DONE", "- DONE - all green"):
            with self.subTest(line=line):
                self.assertEqual(self.gate(f"{line}\n{LOADED}")[0], 0)

    def test_first_status_line_wins(self):
        self.blocked(f"Status: BLOCKED\nDONE\n{LOADED}", "status BLOCKED does not gate")

    def test_ac_s9_skills_missing_skill_blocks(self):
        self.blocked("Status: DONE\nskills_loaded: graph-engineering:uv\n",
                     "skills not loaded: graph-engineering:backend-rules")

    def test_last_skills_loaded_line_counts(self):
        self.blocked(f"DONE\n{LOADED}skills_loaded: graph-engineering:uv\n",
                     "skills not loaded: graph-engineering:backend-rules")
        self.assertEqual(self.gate(f"DONE\nskills_loaded: graph-engineering:uv\n`{LOADED.strip()}`\n")[0], 0)

    def test_no_skills_loaded_line_misses_every_skill(self):
        self.blocked("DONE\n", "skills not loaded: graph-engineering:uv, graph-engineering:backend-rules")

    def test_required_list_continues_and_takes_markup(self):
        self.brief("**REQUIRED skills:** `graph-engineering:uv`,\n  graph-engineering:backend-rules.\n\nprose\n")
        self.blocked("DONE\nskills_loaded: graph-engineering:uv\n",
                     "skills not loaded: graph-engineering:backend-rules")

    def test_brief_without_required_list_blocks(self):
        self.brief("# T1\n\nthe REQUIRED skills: line is missing here\n")
        self.blocked(f"DONE\n{LOADED}", "brief has no REQUIRED skills line")

    def test_ac_s9_evidence_missing_evidence_blocks(self):
        (self.repo / EVIDENCE).unlink()
        self.blocked(f"DONE\n{LOADED}", f"case AC-1: evidence {EVIDENCE} missing")

    def test_root_is_where_evidence_is_read(self):
        root = self.repo / "worktree"
        root.mkdir()
        self.blocked(f"DONE\n{LOADED}", f"case AC-1: evidence {EVIDENCE} missing", "--root", str(root))
        self.evidence(root)
        (self.repo / EVIDENCE).unlink()
        self.assertEqual(self.gate(f"DONE\n{LOADED}", "--root", str(root))[0], 0)

    def test_ac_s9_partial_is_superseded_not_gated(self):
        self.blocked(f"Status: PARTIAL\ngreen_commit: abc1234\ndone_cases: AC-1\n{LOADED}", PARTIAL_REASON)

    def test_other_statuses_and_none_block(self):
        for status in ("BLOCKED", "NEEDS_CONTEXT", "NEEDS_SETUP", "ESCALATE"):
            with self.subTest(status=status):
                self.blocked(f"Status: {status}\n{LOADED}", f"status {status} does not gate")
        for report in (f"all good\n{LOADED}", f"Status: done\n{LOADED}"):
            with self.subTest(report=report):
                self.blocked(report, "report has no status line")

    def test_ac_s9_accept_every_failure_is_listed_at_once(self):
        (self.repo / EVIDENCE).unlink()
        self.blocked("Status: PARTIAL\ngreen_commit: abc1234\nskills_loaded: graph-engineering:uv\n",
                     "; ".join([PARTIAL_REASON, "skills not loaded: graph-engineering:backend-rules",
                                f"case AC-1: evidence {EVIDENCE} missing"]))

    def test_unknown_task_blocks(self):
        self.report_path.write_text(f"DONE\n{LOADED}")
        code, result = invoke(["task-gate", str(self.run), "--task", "T9", "--report", str(self.report_path)])
        self.assertEqual((code, result["status"]), (1, "BLOCKED"))
        self.assertIn("T9", result["reason"])


if __name__ == "__main__":
    unittest.main()
