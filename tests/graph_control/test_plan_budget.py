import unittest

from helpers import plan_data
from graph_control.common import Invalid
from graph_control.plan import Plan
from graph_control.plan_budget import MAX_ESTIMATE_MIN, MAX_WRITABLE_PATHS, PROOF

PASS, BLOCKED = "PASS", "BLOCKED"


def paths(count):
    return [f"app/stage/file{index}.py" for index in range(count)]


def plan(schema=2, **task):
    data = plan_data()
    data["schema_version"] = schema
    data["tasks"][0].update(task)
    return data


# AC-PB-1: expected verdicts written before the implementation.
TABLE = [
    ("estimate 46", plan(estimate_min=46), BLOCKED, "T1.*estimate_min.*1-45"),
    ("estimate 0", plan(estimate_min=0), BLOCKED, "T1.*estimate_min.*1-45"),
    ("estimate string", plan(estimate_min="30"), BLOCKED, "T1.*estimate_min.*integer"),
    ("estimate bool", plan(estimate_min=True), BLOCKED, "T1.*estimate_min.*integer"),
    ("estimate float", plan(estimate_min=30.0), BLOCKED, "T1.*estimate_min.*integer"),
    ("estimate null", plan(estimate_min=None), BLOCKED, "T1.*estimate_min.*null"),
    ("estimate 1", plan(estimate_min=1), PASS, None),
    ("estimate 45", plan(estimate_min=45), PASS, None),
    ("9 paths, estimate, no reason", plan(estimate_min=30, writable_paths=paths(9)), BLOCKED,
     "T1.*9 writable_paths.*8.*path_cap_reason"),
    ("9 paths, estimate, reason",
     plan(estimate_min=30, writable_paths=paths(9), path_cap_reason="one generated tree"), PASS, None),
    ("9 paths, estimate, blank reason",
     plan(estimate_min=30, writable_paths=paths(9), path_cap_reason="  "), BLOCKED, "T1.*path_cap_reason.*text"),
    ("8 paths, estimate", plan(estimate_min=30, writable_paths=paths(8)), PASS, None),
    ("9 paths, no estimate", plan(writable_paths=paths(9)), PASS, None),
    ("proof cluster, produces", plan(estimate_min=30, proof="cluster"), BLOCKED, "T1.*proof cluster.*produces"),
    ("proof full_device, produces", plan(estimate_min=30, proof="full_device"), BLOCKED,
     "T1.*proof full_device.*produces"),
    ("proof cluster, empty produces", plan(estimate_min=30, proof="cluster", produces=[]), PASS, None),
    ("proof focused, produces", plan(estimate_min=30, proof="focused"), PASS, None),
    ("proof device (enum)", plan(estimate_min=30, proof="device", produces=[]), BLOCKED,
     "T1.*proof.*cluster.*focused.*full_device"),
    ("path_cap_reason without estimate", plan(path_cap_reason="one generated tree"), BLOCKED,
     "T1.*path_cap_reason.*need estimate_min"),
    ("proof without estimate", plan(proof="focused"), BLOCKED, "T1.*proof.*need estimate_min"),
    ("estimate in schema 1", plan(schema=1, estimate_min=30), BLOCKED, "T1.*estimate_min.*schema_version 2"),
    ("proof in schema 1", plan(schema=1, estimate_min=30, proof="focused"), BLOCKED, "T1.*schema_version 2"),
    ("schema 1 without keys", plan(schema=1, writable_paths=paths(9)), PASS, None),
    ("schema 2 without keys", plan(), PASS, None),
]


class PlanBudgetTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual((MAX_ESTIMATE_MIN, MAX_WRITABLE_PATHS), (45, 8))
        self.assertEqual(PROOF, frozenset({"focused", "full_device", "cluster"}))

    def test_verdict_table(self):
        for name, data, verdict, message in TABLE:
            with self.subTest(name):
                if verdict == PASS:
                    Plan.parse(data)
                else:
                    with self.assertRaisesRegex(Invalid, message):
                        Plan.parse(data)

    def test_fields_parsed_onto_task(self):
        task = Plan.parse(plan(estimate_min=30, writable_paths=paths(9), path_cap_reason="tree",
                               proof="cluster", produces=[])).tasks[0]
        self.assertEqual((task.estimate_min, task.path_cap_reason, task.proof), (30, "tree", "cluster"))

    def test_absent_fields_default_to_none(self):
        task = Plan.parse(plan()).tasks[0]
        self.assertEqual((task.estimate_min, task.path_cap_reason, task.proof), (None, None, None))

    def test_unknown_task_key_still_rejected(self):
        with self.assertRaisesRegex(Invalid, "unknown fields"):
            Plan.parse(plan(estimate_minutes=30))


if __name__ == "__main__":
    unittest.main()
