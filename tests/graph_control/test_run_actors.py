"""Actor-id rule: a role-prefixed id naming another run is rejected, legacy ids warn.

Every id below is SYNTHETIC (invented hex), not from a real run.
"""

import copy
import tempfile
import unittest
from pathlib import Path

from helpers import fixture
from graph_control.common import Invalid
from graph_control.run import Run, actor_id, foreign_actor_ids, legacy_actor_ids

RUN_ID = "01a16429-bd22-7850-b231-66dfb8161418"
ROLES = ("plan", "implement", "review", "qa", "verify")


class RunActorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.run, _, _ = fixture(Path(temp.name))
        self.run["id"] = RUN_ID

    def with_ids(self, ids):
        run = copy.deepcopy(self.run)
        for actor, new in zip(run["actors"], ids):
            actor["id"] = new
        return run

    def test_foreign_run_id_is_rejected(self):
        run = self.with_ids(["plan-01a15ebc-a611", "implement-agent", "review-agent", "qa-agent", "verify-agent"])
        with self.assertRaises(Invalid) as caught:
            Run.parse(run)
        self.assertIn("plan-01a15ebc-a611", str(caught.exception))
        self.assertIn(RUN_ID, str(caught.exception))

    def test_legacy_ids_parse_and_warn(self):
        own = f"implement-{RUN_ID}-t3"
        ids = ["worker-session-id", "3f1c2b9e-8d4a-4c1e-9f2b-7a6d5e4c3b2a", "implement-agent", own, "verify-agent"]
        parsed = Run.parse(self.with_ids(ids))
        self.assertEqual(legacy_actor_ids(RUN_ID, ids), ids[:3] + ["verify-agent"])
        self.assertNotIn(own, legacy_actor_ids(RUN_ID, ids))
        self.assertEqual(parsed.warnings, [f"legacy actor id {i}: not derived from run {RUN_ID}"
                                           for i in ids[:3] + ["verify-agent"]])

    def test_legacy_list_excludes_role_prefixed(self):
        ids = ["worker-session-id", "3f1c2b9e-8d4a-4c1e-9f2b-7a6d5e4c3b2a", "implement-agent",
               f"implement-{RUN_ID}-t3"]
        self.assertEqual(legacy_actor_ids(RUN_ID, ids), ids[:3])

    def test_actor_id_round_trips(self):
        self.assertEqual(actor_id("qa", RUN_ID), f"qa-{RUN_ID}")
        self.assertEqual(actor_id("qa", RUN_ID, "t3"), f"qa-{RUN_ID}-t3")
        for role in ROLES:
            self.assertEqual(foreign_actor_ids(RUN_ID, [actor_id(role, RUN_ID), actor_id(role, RUN_ID, "x1")]), [])

    def test_short_prefix_of_this_run_is_own(self):
        self.assertEqual(foreign_actor_ids(RUN_ID, [f"plan-{RUN_ID[:13]}", f"plan-{RUN_ID}"]), [])

    def test_other_run_with_suffix_is_foreign(self):
        other = "review-01a15ebc-a611-7000-8000-0123456789ab-t2"
        self.assertEqual(foreign_actor_ids(RUN_ID, [other, "review-agent"]), [other])

    def test_uppercase_hex_is_legacy_not_foreign(self):
        self.assertEqual(foreign_actor_ids(RUN_ID, ["plan-01A15EBC-A611"]), [])
        self.assertEqual(legacy_actor_ids(RUN_ID, ["plan-01A15EBC-A611"]), ["plan-01A15EBC-A611"])

    def test_fixture_run_has_only_legacy_warnings(self):
        parsed = Run.parse(self.run)
        self.assertEqual(len(parsed.warnings), 5)


if __name__ == "__main__":
    unittest.main()
