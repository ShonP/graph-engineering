import re
import unittest

from test_roster_policy import ROOT

RUN = ROOT / "docs" / "engine" / "run.md"
TEMPLATE = ROOT / "templates" / "graph-profile.yaml"


class ReviewCadence(unittest.TestCase):
    def test_template_ships_the_per_task_default(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^review:\n(?:  .*\n)*  cadence: per-task$")

    def test_engine_honors_both_cadences(self):
        text = re.sub(r"\s+", " ", RUN.read_text(encoding="utf-8"))
        self.assertIn("`review.cadence: per-task`, the default", text)
        self.assertRegex(text, r"With `per-run`, a task merges once its tests and the quick gate pass")
        self.assertIn("one review leg runs on the whole run diff", text)


if __name__ == "__main__":
    unittest.main()
