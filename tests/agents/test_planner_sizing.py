"""Golden checks for planner sizing and the documented `ready` and budget-key contracts.

The planner prose must carry the sizing rules (estimate, path cap, critical-path depth, proof
tasks, per-task namespaces, the budget line in every brief), and docs/graph-controls.md must
describe `ready` and the optional task budget keys exactly as the validator enforces them.
Stdlib only: the plan modules import nothing outside the standard library.
"""

import json
import re
import sys
import unittest

from test_roster_policy import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from graph_control.plan import Plan  # noqa: E402
from graph_control.plan_budget import MAX_ESTIMATE_MIN, MAX_WRITABLE_PATHS, PROOF  # noqa: E402

PLANNER = ROOT / "agents" / "planner.md"
CONTROLS = ROOT / "docs" / "graph-controls.md"
POLLING = re.compile(r"sleep\s+\d|while\b.*\bsleep|until\b.*;\s*do|\bpoll\b", re.I)


def flat(text):
    return re.sub(r"\s+", " ", text)


def fenced_json_after(text, heading):
    return json.loads(re.search(re.escape(heading) + r".*?```json\n(.*?)```", text, re.S).group(1))


class PlannerSizing(unittest.TestCase):  # AC-PS-1
    def setUp(self):
        self.text = flat(PLANNER.read_text(encoding="utf-8"))

    def test_estimate_and_split(self):
        ranges = re.findall(r"`estimate_min` \((\d+)-(\d+)\)", self.text)
        self.assertTrue(ranges)
        self.assertEqual(set(ranges), {("1", str(MAX_ESTIMATE_MIN))})
        self.assertRegex(self.text, rf"cannot fit in {MAX_ESTIMATE_MIN} minutes is split")

    def test_path_cap(self):
        self.assertIn(f"at most {MAX_WRITABLE_PATHS} `writable_paths`", self.text)
        self.assertRegex(self.text, r"`path_cap_reason`[^.]*gate")

    def test_critical_path_depth(self):
        self.assertIn("contract tasks first, consumers fan out", self.text.lower())
        self.assertRegex(self.text, r"critical-path depth[^.]*longest `depends_on` chain")
        self.assertRegex(self.text, r"`validate-plan` prints[^.]*`critical_path`")

    def test_build_and_proof_are_separate_tasks(self):
        self.assertIn("`proof: full_device|cluster`", self.text)
        self.assertRegex(self.text, r"produces no contract")
        self.assertRegex(self.text, r"builders use focused tests")

    def test_per_task_namespaces(self):
        self.assertIn("`GRAPH_RUN_ID`", self.text)
        self.assertIn("`docs/engine/lanes.md`", self.text)

    def test_every_brief_states_its_budget(self):
        self.assertRegex(self.text, r"(?i)every brief states its budget[^.]*45-minute time-box")
        self.assertIn("`wait-run.sh --full`", self.text)

    def test_gate_shows_depth_next_to_task_count(self):
        self.assertRegex(self.text, r"plan gate shows the critical-path depth next to the task count")

    def test_no_polling_advice(self):
        self.assertIsNone(POLLING.search(self.text))


class ControlsReady(unittest.TestCase):  # AC-PS-1
    def setUp(self):
        self.doc = CONTROLS.read_text(encoding="utf-8")
        (self.bullet,) = [line for line in self.doc.split("\n") if line.startswith("- `ready ")]

    def test_command_listed(self):
        self.assertIn("uv run scripts/graph-control.py ready /absolute/run/plan.json --done <ids> "
                      "[--running <ids>] [--max-width 4]", self.doc)

    def test_json_keys(self):
        for key in ("ready", "running", "remaining", "critical_path", "max_width"):
            self.assertIn(f"`{key}`", self.bullet)

    def test_ordering_and_blocked_cases(self):
        self.assertIn("longest remaining chain first, then plan order", self.bullet)
        for needle in ("`unknown task id", "both done and running", "`validate-plan` message"):
            self.assertIn(needle, self.bullet)

    def test_waves_is_display_only(self):
        (waves,) = [line for line in self.doc.split("\n") if line.startswith("- `waves ")]
        self.assertRegex(waves, r"display only[^.]*schedules with `ready`")

    def test_validate_plan_prints_critical_path(self):
        self.assertRegex(flat(self.doc), r"`validate-plan`[^.]*`critical_path`")


class ControlsBudgetKeys(unittest.TestCase):  # AC-PS-1
    def setUp(self):
        self.doc = CONTROLS.read_text(encoding="utf-8")
        self.schema = flat(self.doc.split("## Plan schema", 1)[1].split("\n## ", 1)[0])

    def test_old_all_required_sentence_is_gone(self):
        self.assertNotIn("All fields in this example are required in both versions", self.schema)

    def test_optional_keys_and_rules(self):
        for key in ("estimate_min", "path_cap_reason", "proof"):
            self.assertIn(f"`{key}`", self.schema)
        self.assertIn(f"1 to {MAX_ESTIMATE_MIN}", self.schema)
        self.assertIn(f"more than {MAX_WRITABLE_PATHS} `writable_paths`", self.schema)
        for value in sorted(PROOF):
            self.assertIn(f"`{value}`", self.schema)

    def test_budget_example_validates(self):
        plan = fenced_json_after(self.doc, "## Plan schema")
        budget = fenced_json_after(self.doc, "### Task budget (version 2)")
        self.assertEqual(budget["schema_version"], 2)
        plan["schema_version"] = 2
        rows = {row["id"]: row for row in plan["tasks"]}
        for row in budget["tasks"]:
            rows[row.pop("id")].update(row)
        parsed = Plan.parse(plan)
        self.assertTrue(any(task.estimate_min for task in parsed.tasks))


if __name__ == "__main__":
    unittest.main()
