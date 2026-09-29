import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import dump, fixture
from graph_control.common import Invalid, load
from graph_control.state import event, record, store_items, validate_attempts

CLI = Path(__file__).resolve().parents[2] / "scripts" / "graph-control.py"


class StateTests(unittest.TestCase):
    def test_fix_limit_requires_replan_not_round_reset(self):
        data = {"schema_version": 1, "max_fix_rounds": 3, "task_ids": ["T1"], "attempts": [
            {"task_id": "T1", "round": number, "decision": "fix", "candidate": f"sha-{number}",
             "reason": "finding", "hypothesis": f"h-{number}", "outcome": "failed"}
            for number in range(1, 5)]}
        with self.assertRaisesRegex(Invalid, "fix limit exceeded"):
            validate_attempts(data)
        data["attempts"][-1]["decision"] = "replan"
        self.assertEqual(validate_attempts(data)["requires_replan"], ["T1"])
        data["attempts"].append({**data["attempts"][0], "round": 5})
        with self.assertRaisesRegex(Invalid, "new approved plan"):
            validate_attempts(data)

    def test_two_failed_hypotheses_require_fresh_diagnosis(self):
        data = {"schema_version": 1, "max_fix_rounds": 3, "task_ids": ["T1"], "attempts": [
            {"task_id": "T1", "round": number, "decision": "fix", "candidate": f"sha-{number}",
             "reason": "finding", "hypothesis": "same", "outcome": "failed"} for number in range(1, 4)]}
        with self.assertRaisesRegex(Invalid, "failed twice"):
            validate_attempts(data)
        data["attempts"][-1]["hypothesis"] = "new diagnosis"
        validate_attempts(data)

    def test_progress_coalesces_and_terminal_events_wake(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.json"
            for number, kind in enumerate(("progress", "yielded", "completed", "failed", "decision"), 1):
                result = event(path, {"task_id": "T1", "sequence": number, "kind": kind, "summary": "current"})
                self.assertEqual(result["wake"], kind in {"completed", "failed", "decision"})
            self.assertEqual(len(load(path)["tasks"]), 1)
            with self.assertRaisesRegex(Invalid, "increase"):
                event(path, {"task_id": "T1", "sequence": 1, "kind": "progress", "summary": "stale"})

    def test_duplicate_json_fields_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"a": 1, "a": 2}')
            with self.assertRaisesRegex(Invalid, "duplicate JSON"):
                load(path)

    def test_cli_end_to_end_and_wrong_candidate_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, receipts, _ = fixture(root)
            manifest = root / "run.json"
            dump(manifest, run)
            store = root / "receipts.json"
            for receipt in receipts:
                path = root / "receipt.json"
                dump(path, receipt)
                result = subprocess.run([sys.executable, str(CLI), "record-receipt", str(manifest), str(path),
                                         "--store", str(store)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            command = [sys.executable, str(CLI), "verify", str(manifest), "--store", str(store)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            (Path(run["candidate"]["sources"][0]["root"]) / "app.py").write_text("broken")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
