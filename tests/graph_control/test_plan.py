import copy
import unittest

from helpers import plan_data
from graph_control.common import Invalid
from graph_control.plan import Plan


class PlanTests(unittest.TestCase):
    def test_valid_plan(self):
        self.assertEqual(Plan.parse(plan_data()).tasks[0].id, "T1")

    def test_synthetic_witness_cannot_prove_real_coverage(self):
        data = plan_data()
        data["cases"][0]["requires_real"] = True
        with self.assertRaisesRegex(Invalid, "real evidence"):
            Plan.parse(data)

    def consumer(self):
        data = plan_data()
        second = copy.deepcopy(data["tasks"][0])
        second.update(id="FE4", produces=[], consumes=[{"id": "stage", "fields": ["status"]}],
                      writable_paths=["app/downstream/**"])
        data["tasks"].append(second)
        return data

    def test_fe4_requires_fe3_producer_dependency(self):
        with self.assertRaisesRegex(Invalid, "missing dependency"):
            Plan.parse(self.consumer())

    def test_transitive_producer_is_sufficient(self):
        data = self.consumer()
        data["tasks"][1]["depends_on"] = ["T1"]
        Plan.parse(data)

    def test_missing_wire_total(self):
        data = self.consumer()
        data["tasks"][1]["depends_on"] = ["T1"]
        data["tasks"][1]["consumes"][0]["fields"].append("fan_out_planned")
        with self.assertRaisesRegex(Invalid, "missing fields"):
            Plan.parse(data)

    def test_unknown_and_cyclic_dependencies(self):
        for dependencies in (["UNKNOWN"], ["T1"]):
            with self.subTest(dependencies=dependencies):
                data = plan_data()
                data["tasks"][0]["depends_on"] = dependencies
                with self.assertRaisesRegex(Invalid, "cyclic or unknown"):
                    Plan.parse(data)

    def test_unordered_writes_rejected(self):
        data = self.consumer()
        data["tasks"][1].update(consumes=[], writable_paths=["app/stage/status.py"])
        with self.assertRaisesRegex(Invalid, "overlap"):
            Plan.parse(data)

    def test_intra_segment_glob_overlap(self):
        data = self.consumer()
        data["tasks"][0]["writable_paths"] = ["repo/foo*"]
        data["tasks"][1].update(consumes=[], writable_paths=["repo/foobar.py"])
        with self.assertRaisesRegex(Invalid, "overlap"):
            Plan.parse(data)

    def test_stateful_task_needs_composed_transition(self):
        data = plan_data()
        data["tasks"][0]["stateful"] = True
        with self.assertRaisesRegex(Invalid, "composed transition"):
            Plan.parse(data)
        data["cases"][0]["transitions"] = ["schema_invalid", "lab_unreachable"]
        Plan.parse(data)

    def test_unknown_case_and_contract(self):
        data = plan_data()
        data["tasks"][0]["case_ids"] = ["UNKNOWN"]
        with self.assertRaisesRegex(Invalid, "unknown acceptance"):
            Plan.parse(data)
        data = self.consumer()
        data["tasks"][1]["consumes"][0]["id"] = "UNKNOWN"
        with self.assertRaisesRegex(Invalid, "missing producer"):
            Plan.parse(data)

    def test_duplicate_producer_and_unknown_fields(self):
        data = self.consumer()
        data["tasks"][1]["produces"] = data["tasks"][0]["produces"]
        with self.assertRaisesRegex(Invalid, "multiple producers"):
            Plan.parse(data)
        data = plan_data()
        data["approved"] = True
        with self.assertRaisesRegex(Invalid, "unknown fields"):
            Plan.parse(data)

    def test_empty_oracle_rejected(self):
        data = plan_data()
        data["cases"][0]["oracle"] = ""
        with self.assertRaises(Invalid):
            Plan.parse(data)


if __name__ == "__main__":
    unittest.main()
