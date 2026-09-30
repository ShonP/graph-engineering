"""common.version: only plan.json widens to schema 2; run.json, state and receipt stores stay at 1.

Every artifact below is SYNTHETIC (helpers.fixture and inline dicts), not a real run.
"""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import fixture
from graph_control.common import Invalid, version
from graph_control.run import Run
from graph_control.state import event, store_items, validate_attempts

ONLY_ONE = "schema_version must be 1$"


class SchemaVersionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def test_default_allows_only_one(self):
        self.assertEqual(version(1), 1)
        for value in (2, 0, True, "1"):
            with self.subTest(value=value), self.assertRaisesRegex(Invalid, ONLY_ONE):
                version(value)

    def test_allowed_set_widens_explicitly(self):
        self.assertEqual(version(2, frozenset({1, 2})), 2)
        with self.assertRaisesRegex(Invalid, "schema_version must be 1 or 2"):
            version(3, frozenset({1, 2}))

    def test_run_json_still_requires_one(self):  # AC-W4-SS-05
        data, _, _ = fixture(self.dir)
        with self.assertRaisesRegex(Invalid, ONLY_ONE):
            Run.parse({**data, "schema_version": 2})

    def test_receipt_store_still_requires_one(self):  # AC-W4-SS-05
        store = self.dir / "receipts.json"
        store.write_text(json.dumps({"schema_version": 2, "receipts": []}))
        with self.assertRaisesRegex(Invalid, ONLY_ONE):
            store_items(store)

    def test_event_state_and_attempts_still_require_one(self):  # AC-W4-SS-05
        state = self.dir / "events.json"
        state.write_text(json.dumps({"schema_version": 2, "tasks": {}}))
        with self.assertRaisesRegex(Invalid, ONLY_ONE):
            event(state, {"task_id": "T1", "sequence": 1, "kind": "progress", "summary": "running"})
        with self.assertRaisesRegex(Invalid, ONLY_ONE):
            validate_attempts({"schema_version": 2, "max_fix_rounds": 3, "task_ids": ["T1"], "attempts": []})


if __name__ == "__main__":
    unittest.main()
