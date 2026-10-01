"""Plan.levels() and the `waves` command, over SYNTHETIC plans.

Task ids, paths and cases are invented shapes, not a real run's plan.
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
from graph_control.plan import Plan


def plan_of(*tasks):
    """A valid plan: one case owned by every task, one disjoint writable path per task."""
    data = plan_data()
    template = data["tasks"][0]
    data["tasks"] = [{**template, "id": key, "depends_on": list(needs), "produces": [],
                      "writable_paths": [f"app/{key.lower()}/**"]} for key, needs in tasks]
    return data


DIAMOND = plan_of(("A", ()), ("B", ("A",)), ("C", ("A",)), ("D", ("B", "C")))
FIVE = plan_of(*((str(n), ()) for n in range(1, 6)))


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


class Levels(unittest.TestCase):
    def test_diamond_levels(self):  # AC-W3-WV-01
        self.assertEqual(Plan.parse(DIAMOND).levels(), [["A"], ["B", "C"], ["D"]])

    def test_plan_order_within_a_level(self):
        data = plan_of(("Z", ()), ("C", ("Z",)), ("B", ("Z",)), ("Y", ()))
        self.assertEqual(Plan.parse(data).levels(), [["Z", "Y"], ["C", "B"]])

    def test_independent_tasks_share_one_level(self):
        self.assertEqual(Plan.parse(FIVE).levels(), [["1", "2", "3", "4", "5"]])


class WavesCommand(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def waves(self, data, *extra):
        return invoke(["waves", dump(self.dir / "plan.json", data), *extra])

    def test_registered_as_plugin(self):
        self.assertIn("waves", [module.NAME for module in iter_commands()])

    def test_diamond_default_width(self):  # AC-W3-WV-01
        self.assertEqual(self.waves(DIAMOND),
                         (0, {"status": "PASS", "waves": [["A"], ["B", "C"], ["D"]], "max_width": 4}))

    def test_wide_level_splits_in_plan_order(self):  # AC-W3-WV-02
        self.assertEqual(self.waves(FIVE, "--max-width", "2"),
                         (0, {"status": "PASS", "waves": [["1", "2"], ["3", "4"], ["5"]], "max_width": 2}))

    def test_split_keeps_levels_ordered(self):
        data = plan_of(("A", ()), ("B", ()), ("C", ()), ("D", ("A",)))
        self.assertEqual(self.waves(data, "--max-width", "2")[1]["waves"], [["A", "B"], ["C"], ["D"]])

    def test_invalid_plan_blocked_with_validate_message(self):  # AC-W3-WV-04
        cases = {"cyclic or unknown task dependency": plan_of(("A", ("B",)), ("B", ("A",))),
                 "unordered writable paths overlap: A:app/a/**, B:app/a/x.py":
                     {**DIAMOND, "tasks": [DIAMOND["tasks"][0],
                                           {**DIAMOND["tasks"][1], "depends_on": [],
                                            "writable_paths": ["app/a/x.py"]}]}}
        for message, data in cases.items():
            with self.subTest(message=message):
                self.assertEqual(self.waves(data), (1, {"status": "BLOCKED", "reason": message}))

    def test_missing_plan_blocked(self):
        code, result = invoke(["waves", str(self.dir / "absent.json")])
        self.assertEqual((code, result["status"]), (1, "BLOCKED"))

    def test_width_must_be_positive(self):
        for width in ("0", "-1", "two"):
            error = io.StringIO()
            with self.subTest(width=width), contextlib.redirect_stderr(error):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(["waves", dump(self.dir / "plan.json", FIVE), "--max-width", width])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("--max-width: expected a positive integer", error.getvalue())


if __name__ == "__main__":
    unittest.main()
