"""checks-expiry: doctor rows for advisory graph-checks.json checks near or past their expires date."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import hygiene_fixture  # noqa: F401
from graph_control.hygiene import Context, iter_rules
from graph_control.hygiene import checks_expiry as rule
from graph_control.hygiene.config import parse

NOW = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)


class ChecksExpiry(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def rows(self, *checks, raw=None):
        path = self.root / ".claude" / "graph-checks.json"
        if checks or raw is not None:
            path.parent.mkdir(exist_ok=True)
            path.write_text(raw if raw is not None else json.dumps({"version": 1, "checks": list(checks)}))
        ctx = Context(root=self.root, config=parse({}), mode="doctor", now=NOW)
        self.assertEqual(rule.run(ctx), [])
        return rule.doctor(ctx)

    def advisory(self, ident, expires):
        return {"id": ident, "argv": ["jscpd", "."], "mode": "advisory", "expires": expires}

    def test_contract(self):
        self.assertEqual((rule.ID, rule.MODES, rule.QUICK), ("checks-expiry", frozenset({"doctor"}), True))
        self.assertIn("checks-expiry", [module.ID for module in iter_rules()])

    def test_expired_and_today_are_errors(self):
        for expires in ("2026-10-20", "2026-10-21"):
            with self.subTest(expires):
                [(level, ident, message, fix)] = self.rows(self.advisory("dup-code", expires))
                self.assertEqual((level, ident), ("error", "check-expired"))
                self.assertIn("dup-code", message)
                self.assertIn(expires, message)
                self.assertTrue(fix)

    def test_within_seven_days_warns(self):
        for expires, days in (("2026-10-22", "1 day"), ("2026-10-28", "7 days")):
            with self.subTest(expires):
                [(level, ident, message, fix)] = self.rows(self.advisory("dup-code", expires))
                self.assertEqual((level, ident), ("warn", "check-expiring"))
                self.assertIn(f"dup-code starts blocking on {expires} (in {days})", message)
                self.assertTrue(fix)

    def test_nothing_to_report(self):
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.rows(self.advisory("dup-code", "2026-10-29")), [])
        self.assertEqual(self.rows({"id": "types", "argv": ["mypy", "."], "mode": "blocking"}), [])
        self.assertEqual(self.rows(raw="{"), [])
        self.assertEqual(self.rows(raw=json.dumps({"version": 1, "test": {"argv": ["make"]}})), [])

    def test_one_row_per_check_in_order(self):
        rows = self.rows(self.advisory("dup-code", "2026-10-01"), self.advisory("later", "2027-01-01"),
                         self.advisory("dead-code", "2026-10-25"))
        self.assertEqual([(level, ident) for level, ident, _, _ in rows],
                         [("error", "check-expired"), ("warn", "check-expiring")])
        self.assertIn("dead-code", rows[1][2])


if __name__ == "__main__":
    unittest.main()
