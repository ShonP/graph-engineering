"""plan_queue (ready set, tail length, critical path) and the `ready` command, over SYNTHETIC plans.

Task ids, paths and cases are invented shapes, not a real run's plan. GAME is a synthetic
reduction of a real run's dependency shape: three roots, a fan-out on one, a join of two.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import dump, plan_data
from graph_control import cli
from graph_control.commands import iter_commands
from graph_control.common import Invalid
from graph_control.plan import Plan
from graph_control.plan_queue import critical_path, ready_set, tail_length


def plan_of(*tasks):
    """A valid plan: one case owned by every task, one disjoint writable path per task."""
    data = plan_data()
    template = data["tasks"][0]
    data["tasks"] = [{**template, "id": key, "depends_on": list(needs), "produces": [],
                      "writable_paths": [f"app/{key.lower()}/**"]} for key, needs in tasks]
    return data


GAME_DEPS = {"T01": (), "T15": (), "T21": (), "T02": ("T01",), "T03": ("T01",), "T06": ("T01",),
             "T07": ("T01", "T15")}
GAME = plan_of(*GAME_DEPS.items())
CHAIN = plan_of(("A", ()), ("B", ("A",)), ("C", ("B",)), ("D", ()))
DIAMOND = plan_of(("A", ()), ("B", ("A",)), ("C", ("A",)), ("D", ("B", "C")))


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


class Depth(unittest.TestCase):
    def test_lone_task_is_one(self):
        self.assertEqual(critical_path(Plan.parse(plan_data())), 1)

    def test_chain_beats_independent_task(self):
        plan = Plan.parse(CHAIN)
        self.assertEqual(tail_length(plan), {"A": 3, "B": 2, "C": 1, "D": 1})
        self.assertEqual(critical_path(plan), 3)

    def test_diamond_counts_tasks_not_edges(self):
        plan = Plan.parse(DIAMOND)
        self.assertEqual(tail_length(plan), {"A": 3, "B": 2, "C": 2, "D": 1})
        self.assertEqual(critical_path(plan), 3)


class ReadySet(unittest.TestCase):
    def test_game_shape_starts_fanout_not_join(self):  # AC-RQ-1
        done, running = {"T01", "T21"}, {"T15"}
        expected = {key for key, needs in GAME_DEPS.items()
                    if key not in done | running and set(needs) <= done}
        self.assertEqual(expected, {"T02", "T03", "T06"})
        result = ready_set(Plan.parse(GAME), done, running, 4)
        self.assertEqual(set(result), expected)
        self.assertEqual(len(result), len(expected))
        self.assertNotIn("T07", result)
        self.assertEqual(result, ["T02", "T03", "T06"])  # equal tails fall back to plan order

    def test_longest_remaining_chain_first(self):
        plan = Plan.parse(plan_of(("D", ()), ("A", ()), ("B", ("A",))))
        self.assertEqual(ready_set(plan, set(), set(), 4), ["A", "D"])
        self.assertEqual(ready_set(plan, set(), set(), 1), ["A"])

    def test_truncated_to_free_slots(self):
        plan = Plan.parse(GAME)
        self.assertEqual(len(ready_set(plan, {"T01", "T21"}, {"T15"}, 3)), 2)
        self.assertEqual(ready_set(plan, {"T01", "T21"}, {"T15"}, 1), [])
        self.assertEqual(ready_set(plan, {"T01"}, {"T15", "T21"}, 1), [])

    def test_all_done_is_empty(self):
        plan = Plan.parse(GAME)
        self.assertEqual(ready_set(plan, set(GAME_DEPS), set(), 4), [])

    def test_unknown_and_double_listed_ids(self):  # AC-RQ-3
        plan = Plan.parse(GAME)
        for done, running, needle in ((set(), {"T99"}, "T99"), ({"X1"}, set(), "X1"),
                                      ({"T01"}, {"T01"}, "T01")):
            with self.subTest(needle=needle), self.assertRaises(Invalid) as raised:
                ready_set(plan, done, running, 4)
            self.assertIn(needle, str(raised.exception))


class ReadyCommand(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def ready(self, data, *extra):
        return invoke(["ready", dump(self.dir / "plan.json", data), *extra])

    def test_registered_as_plugin(self):
        self.assertIn("ready", [module.NAME for module in iter_commands()])

    def test_game_shape_json(self):  # AC-RQ-1
        self.assertEqual(self.ready(GAME, "--done", "T01,T21", "--running", "T15", "--max-width", "4"),
                         (0, {"status": "PASS", "ready": ["T02", "T03", "T06"], "running": ["T15"],
                              "remaining": 5, "critical_path": 2, "max_width": 4}))

    def test_nothing_done_default_width(self):  # AC-RQ-3
        code, result = self.ready(CHAIN, "--done", "")
        self.assertEqual((code, result["ready"], result["running"], result["remaining"], result["max_width"]),
                         (0, ["A", "D"], [], 4, 4))

    def test_all_done(self):  # AC-RQ-3
        code, result = self.ready(CHAIN, "--done", "A,B,C,D")
        self.assertEqual((code, result["ready"], result["remaining"]), (0, [], 0))

    def test_running_fills_width(self):  # AC-RQ-3
        code, result = self.ready(GAME, "--done", "T01", "--running", "T02,T03", "--max-width", "2")
        self.assertEqual((code, result["ready"], result["running"]), (0, [], ["T02", "T03"]))

    def test_bad_ids_blocked_naming_the_id(self):  # AC-RQ-3
        for extra, needle in ((["--done", "T01,T99"], "T99"), (["--done", "T01", "--running", "T01"], "T01")):
            with self.subTest(needle=needle):
                code, result = self.ready(GAME, *extra)
                self.assertEqual((code, result["status"]), (1, "BLOCKED"))
                self.assertIn(needle, result["reason"])

    def test_invalid_plan_wins_over_unknown_id(self):  # AC-RQ-3
        cyclic = plan_of(("A", ("B",)), ("B", ("A",)))
        self.assertEqual(self.ready(cyclic, "--done", "NOPE"),
                         (1, {"status": "BLOCKED", "reason": "cyclic or unknown task dependency"}))

    def test_done_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(["ready", dump(self.dir / "plan.json", GAME)])
        self.assertEqual(raised.exception.code, 2)


class ValidatePlan(unittest.TestCase):
    def test_reports_critical_path(self):  # AC-RQ-4
        with tempfile.TemporaryDirectory() as directory:
            code, result = invoke(["validate-plan", dump(Path(directory) / "plan.json", CHAIN)])
        self.assertEqual((code, result), (0, {"status": "PASS", "tasks": 4, "cases": 1, "critical_path": 3}))


if __name__ == "__main__":
    unittest.main()
