import copy
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from helpers import fixture
from graph_control.common import Invalid
from graph_control.receipts import Receipt, verify
from graph_control.run import Run


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data, self.receipts, self.now = fixture(Path(self.temp.name))
        self.run = Run.parse(self.data)

    def test_complete_independent_acceptance(self):
        self.assertEqual(verify(self.run, self.data, self.receipts, self.now)["checks"], 4)

    def test_failures_cannot_prove_pass(self):
        changes = [dict(executed=0), dict(skipped=1), dict(exit_code=1), dict(status="BLOCKED"),
                   dict(cases=[]), dict(cases=[{"id": "AC-1", "status": "SKIPPED"}]),
                   dict(findings={"blocking": 0, "important": 1}), dict(model="wrong-model"),
                   dict(actor="implement-agent"), dict(actor=""), dict(run_sha256="0" * 64),
                   dict(argv=["lint"]), dict(cwd="/wrong/worktree")]
        for change in changes:
            with self.subTest(change=change):
                items = copy.deepcopy(self.receipts)
                items[2].update(change)
                with self.assertRaises(Invalid):
                    verify(self.run, self.data, items, self.now)

    def test_latest_failure_wins_over_previous_pass(self):
        failure = copy.deepcopy(self.receipts[2])
        failure.update(status="FAIL", exit_code=1)
        failure["observed_at"] = (self.now + timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(Invalid, "did not pass"):
            verify(self.run, self.data, self.receipts + [failure], self.now + timedelta(seconds=1))

    def test_older_pass_cannot_overwrite_newer_failure(self):
        failure = copy.deepcopy(self.receipts[2])
        failure.update(status="FAIL", exit_code=1, observed_at=(self.now + timedelta(seconds=1)).isoformat())
        with self.assertRaisesRegex(Invalid, "observations must increase"):
            verify(self.run, self.data, self.receipts + [failure, self.receipts[2]], self.now + timedelta(seconds=1))

    def test_wrong_revision_or_runtime_cannot_reuse_receipt(self):
        for key in ("revision", "dirty_sha256"):
            items = copy.deepcopy(self.receipts)
            items[2]["candidate"]["sources"][0][key] = "0" * (40 if key == "revision" else 64)
            with self.assertRaisesRegex(Invalid, "identity mismatch"):
                verify(self.run, self.data, items, self.now)
        items = copy.deepcopy(self.receipts)
        items[2]["candidate"]["runtime"] = "0" * 64
        with self.assertRaisesRegex(Invalid, "identity mismatch"):
            verify(self.run, self.data, items, self.now)

    def test_expired_future_and_modified_logs(self):
        for moment in (self.now + timedelta(seconds=601), self.now - timedelta(seconds=1)):
            with self.assertRaisesRegex(Invalid, "expired|future"):
                verify(self.run, self.data, self.receipts, moment)
        Path(self.receipts[0]["log_path"]).write_text("changed")
        with self.assertRaisesRegex(Invalid, "modified"):
            verify(self.run, self.data, self.receipts, self.now)

    def test_missing_checks_and_duplicate_cases(self):
        with self.assertRaisesRegex(Invalid, "missing required"):
            verify(self.run, self.data, self.receipts[:-1], self.now)
        duplicate = copy.deepcopy(self.receipts[0])
        duplicate["cases"] *= 2
        with self.assertRaisesRegex(Invalid, "duplicate"):
            Receipt.parse(duplicate)

    def test_role_and_lint_remapping_rejected(self):
        for change in (dict(kind="test"), dict(argv=["ruff", "check"]), dict(argv=["npm", "run", "lint"])):
            data = copy.deepcopy(self.data)
            data["checks"][2].update(change)
            with self.assertRaises(Invalid):
                Run.parse(data)


if __name__ == "__main__":
    unittest.main()
