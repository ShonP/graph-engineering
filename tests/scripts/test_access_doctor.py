"""access-doctor.py: the shipped template parses and validates; bad rows are named."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("access_doctor", ROOT / "scripts" / "access-doctor.py")
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


def row(**overrides):
    base = {
        "id": "deploy", "what": "w", "holds": "h", "role": "r", "who": ["g"],
        "owner_only": False, "check": "true", "request": "ask", "pipeline": "", "status": "active",
    }
    return {**base, **overrides}


class ValidateTest(unittest.TestCase):
    def test_template_is_valid(self):
        rows = yaml.safe_load((ROOT / "templates" / "access.yaml").read_text())["rows"]
        self.assertEqual(doctor.validate(rows), [])

    def test_missing_field_is_named(self):
        broken = row()
        del broken["role"]
        self.assertIn("deploy: missing role", doctor.validate([broken]))

    def test_duplicate_id(self):
        self.assertIn("deploy: duplicate id", doctor.validate([row(), row()]))

    def test_empty_check_needs_owner_only(self):
        self.assertTrue(doctor.validate([row(check="")]))
        self.assertEqual(doctor.validate([row(check="", who=[], owner_only=True)]), [])

    def test_bad_status(self):
        self.assertTrue(doctor.validate([row(status="done")]))


class ProbeTest(unittest.TestCase):
    def test_passing_and_failing_checks(self):
        self.assertIsNone(doctor.probe(row(check=f"{sys.executable} -c pass")))
        self.assertIn("exited 1", doctor.probe(row(check=f"{sys.executable} -c 'raise SystemExit(1)'")))

    def test_requested_rows_are_not_probed(self):
        self.assertIsNone(doctor.probe(row(check="false", status="requested")))


class MainTest(unittest.TestCase):
    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp, "good.yaml")
            good.write_text(yaml.safe_dump({"rows": [row()]}))
            bad = Path(tmp, "bad.yaml")
            bad.write_text(yaml.safe_dump({"rows": [row(status="x")]}))
            self.assertEqual(doctor.main([str(good)]), 0)
            self.assertEqual(doctor.main([str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
