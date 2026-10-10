"""qa-lanes: the lead waits on per-lane `.done` markers, never on its own turn ending.

Every fixture here is synthetic: invented lane names, row ids, paths and shas
that stand for the shape a qa leaf writes, not a real qa run.
"""

import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli
from graph_control.findings import Findings

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "skills/process/qa-verification/templates"
SHA = "c" * 40


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


def findings_doc(verdict="PASS", findings=()):
    return {"schema_version": 1, "verdict": verdict, "reviewed": {"base": SHA, "head": SHA},
            "findings": list(findings)}


class Lanes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.qa = Path(self.tmp.name) / "qa"
        self.qa.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def leaf(self, name, rows=3, verified=2, failed=1, blocked=0, findings=None, **overrides):
        lane = name
        report = self.qa / f"{lane}.md"
        report.write_text("AC-1 | VERIFIED\n")
        path = self.qa / f"{lane}-findings.json"
        path.write_text(json.dumps(findings_doc() if findings is None else findings))
        marker = {"schema_version": 1, "lane": lane, "round": 1, "rows": rows, "verified": verified,
                  "failed": failed, "blocked": blocked, "report": str(report), "findings": str(path),
                  **overrides}
        (self.qa / f"{lane}.done").write_text(json.dumps(marker))

    def checkpoint(self, lane, **overrides):
        doc = {"schema_version": 1, "lane": lane, "round": 1, "rows_done": ["AC-1"], "next_row": "AC-2",
               "remaining_rows": ["AC-2", "AC-3"], "drivers": [str(self.qa / "drive.sh")],
               "fixtures": [], **overrides}
        (self.qa / f"{lane}.checkpoint.json").write_text(json.dumps(doc))

    def run_lanes(self, *lanes, extra=(), round_id=1):
        return invoke(["qa-lanes", str(self.qa), "--lanes", ",".join(lanes), "--round", str(round_id), *extra])

    def age(self, name, seconds_ago):
        path = self.qa / name
        stamp = path.stat().st_mtime - seconds_ago
        os.utime(path, (stamp, stamp))

    def test_a_marker_from_an_earlier_round_is_not_done(self):
        # Review F1: round 1's web.done must not stand in for a round-2 leaf that never finished.
        self.leaf("web")
        code, out = self.run_lanes("web", round_id=2)
        self.assertEqual(code, 75, out)
        self.assertEqual((out["running"], out["stale"], out["done"]), (["web"], ["web"], {}))

    def test_a_checkpoint_from_an_earlier_round_is_not_this_rounds(self):
        self.checkpoint("web")
        code, out = self.run_lanes("web", round_id=2)
        self.assertEqual(code, 75, out)
        self.assertEqual((out["running"], out["checkpointed"]), (["web"], {}))

    def test_a_checkpoint_newer_than_done_means_not_done(self):
        # Review F1: the leaf finished once, then a later leaf of the same round stopped at its budget.
        self.leaf("web", round=2)
        self.age("web.done", 60)
        self.checkpoint("web", round=2)
        code, out = self.run_lanes("web", round_id=2)
        self.assertEqual(code, 75, out)
        self.assertIn("web", out["checkpointed"])
        self.assertEqual(out["done"], {})

    def test_done_newer_than_its_checkpoint_is_done(self):
        # The continuation leaf finished the rows the checkpoint left.
        self.checkpoint("web", round=2)
        self.age("web.checkpoint.json", 60)
        self.leaf("web", round=2)
        code, out = self.run_lanes("web", round_id=2)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["checkpointed"], {})

    def test_a_marker_without_a_round_is_refused(self):
        self.leaf("web")
        marker = json.loads((self.qa / "web.done").read_text())
        del marker["round"]
        (self.qa / "web.done").write_text(json.dumps(marker))
        self.assertEqual(self.run_lanes("web")[0], 1)

    def test_round_must_be_positive(self):
        self.leaf("web")
        self.assertEqual(self.run_lanes("web", round_id=0)[0], 1)

    def test_a_checkpoint_with_no_remaining_rows_is_refused(self):
        # Review F3: with nothing left the leaf writes <lane>.done; an empty checkpoint would pend forever.
        self.checkpoint("web", rows_done=["AC-1", "AC-2"], next_row=None, remaining_rows=[])
        code, out = self.run_lanes("web")
        self.assertEqual(code, 1, out)
        self.assertIn("remaining", out["reason"])

    def test_all_done_is_pass_with_counts(self):
        self.leaf("web")
        self.leaf("ios-1", rows=20, verified=20, failed=0)
        code, out = self.run_lanes("web", "ios-1")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["done"]["web"], {"rows": 3, "verified": 2, "failed": 1, "blocked": 0})
        self.assertEqual(out["running"], [])

    def test_a_lane_without_marker_is_pending_exit_75(self):
        # The observed bug: the lead returned while a leaf still ran. No marker = not finished.
        self.leaf("web")
        code, out = self.run_lanes("web", "ios-1")
        self.assertEqual(code, 75, out)
        self.assertEqual(out["status"], "PENDING")
        self.assertEqual(out["running"], ["ios-1"])

    def test_checkpoint_without_marker_is_reported_for_continuation(self):
        self.checkpoint("ios-2")
        code, out = self.run_lanes("ios-2")
        self.assertEqual(code, 75, out)
        self.assertEqual(out["checkpointed"], {"ios-2": {"next_row": "AC-2", "remaining_rows": ["AC-2", "AC-3"]}})
        self.assertEqual(out["running"], [])

    def test_counts_must_add_up(self):
        self.leaf("web", rows=3, verified=3, failed=1)
        code, out = self.run_lanes("web")
        self.assertEqual(code, 1, out)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertIn("web", out["reason"])

    def test_marker_lane_must_match_its_file(self):
        self.leaf("web", lane="api")
        code, out = self.run_lanes("web")
        self.assertEqual(code, 1, out)

    def test_marker_findings_must_validate(self):
        # Two leaves wrote findings the validator rejected; the marker check catches it before the merge.
        self.leaf("web", findings={"schema_version": 1, "verdict": "INCOMPLETE",
                                   "reviewed": "AC-1 round 2", "findings": []})
        code, out = self.run_lanes("web")
        self.assertEqual(code, 1, out)
        self.assertIn("web-findings.json", out["reason"])

    def test_marker_report_must_exist(self):
        self.leaf("web", report=str(self.qa / "missing.md"))
        code, out = self.run_lanes("web")
        self.assertEqual(code, 1, out)

    def test_checkpoint_rows_cannot_be_both_done_and_remaining(self):
        self.checkpoint("ios-2", rows_done=["AC-2"])
        code, out = self.run_lanes("ios-2")
        self.assertEqual(code, 1, out)

    def test_checkpoint_next_row_is_the_first_remaining(self):
        # A continuation starts at next_row; one outside remaining_rows would skip or repeat rows.
        self.checkpoint("ios-2", next_row="AC-9")
        code, out = self.run_lanes("ios-2")
        self.assertEqual(code, 1, out)

    def test_wait_is_bounded(self):
        code, out = invoke(["qa-lanes", str(self.qa), "--lanes", "web", "--round", "1", "--wait", "271"])
        self.assertEqual(code, 1, out)
        code, out = self.run_lanes("web", extra=("--wait", "1"))
        self.assertEqual(code, 75, out)

    def test_duplicate_or_empty_lane_ids_are_refused(self):
        self.assertEqual(self.run_lanes("web", "web")[0], 1)
        self.assertEqual(self.run_lanes("")[0], 1)


class Templates(unittest.TestCase):
    """The leaf templates emit exactly what the validators accept."""

    def fill(self, name, lane="web"):
        text = (TEMPLATES / name).read_text().replace("<lane>", lane)
        return json.loads(re.sub(r"<[a-z ]+sha>", SHA, text))

    def test_qa_findings_template_validates(self):
        parsed = Findings.parse(self.fill("qa-findings.json"))
        self.assertEqual(parsed.verdict, "FAIL")
        self.assertEqual({item.severity for item in parsed.findings}, {"important"})

    def test_done_and_checkpoint_templates_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            qa = Path(tmp)
            (qa / "web.md").write_text("row\n")
            (qa / "web-findings.json").write_text(json.dumps(self.fill("qa-findings.json")))
            done = self.fill("lane.done.json")
            done.update(report=str(qa / "web.md"), findings=str(qa / "web-findings.json"))
            (qa / "web.done").write_text(json.dumps(done))
            (qa / "ios-1.checkpoint.json").write_text(json.dumps(self.fill("lane.checkpoint.json", "ios-1")))
            code, out = invoke(["qa-lanes", str(qa), "--lanes", "web,ios-1", "--round", "1"])
        self.assertEqual(code, 75, out)
        self.assertIn("web", out["done"])
        self.assertIn("ios-1", out["checkpointed"])


if __name__ == "__main__":
    unittest.main()
