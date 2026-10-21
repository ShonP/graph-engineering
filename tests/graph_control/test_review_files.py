import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

import helpers

from graph_control import cli
from graph_control.common import Invalid
from graph_control.review_files import review_files

PER_RUN = {"review": {"cadence": "per-run"}}


def two_task_plan():
    plan = helpers.plan_data()
    second = copy.deepcopy(plan["tasks"][0])
    second.update(id="T2", writable_paths=["app/other/**"], produces=[{"id": "other", "fields": ["status"]}])
    plan["tasks"].append(second)
    return plan


class ReviewFiles(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.run_dir = Path(temp.name)

    def touch(self, *names):
        for name in names:
            (self.run_dir / name).write_text("{}")

    def test_per_task_reads_each_task_file_and_names_the_missing_one(self):
        self.touch("findings.T1.json", "findings.T1.r1.json")
        result = review_files(self.run_dir, {}, two_task_plan())
        self.assertEqual(result["cadence"], "per-task")
        self.assertEqual(result["legs"], ["T1", "T2"])
        self.assertEqual(result["latest"], [str(self.run_dir / "findings.T1.json"),
                                            str(self.run_dir / "findings.T2.json")])
        self.assertEqual(result["rounds"], [str(self.run_dir / "findings.T1.r1.json")])
        self.assertEqual(result["missing"], [str(self.run_dir / "findings.T2.json")])

    def test_per_run_reads_only_the_run_level_file_so_absent_task_files_never_block(self):
        self.touch("findings.run.json", "findings.run.r1.json")
        result = review_files(self.run_dir, PER_RUN, two_task_plan())
        self.assertEqual(result["legs"], ["run"])
        self.assertEqual(result["latest"], [str(self.run_dir / "findings.run.json")])
        self.assertEqual(result["rounds"], [str(self.run_dir / "findings.run.r1.json")])
        self.assertEqual(result["missing"], [])

    def test_per_run_without_its_review_file_is_missing_not_zero(self):
        result = review_files(self.run_dir, PER_RUN, two_task_plan())
        self.assertEqual(result["missing"], [str(self.run_dir / "findings.run.json")])

    def test_unknown_cadence_is_invalid(self):
        with self.assertRaises(Invalid):
            review_files(self.run_dir, {"review": {"cadence": "per_run"}}, two_task_plan())

    def test_cli_reads_the_profile_and_the_run_plan(self):
        (self.run_dir / "plan.json").write_text(json.dumps(two_task_plan()))
        profile = self.run_dir / "profile.yaml"
        profile.write_text("review:\n  cadence: per-run\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["review-files", str(self.run_dir), "--profile", str(profile)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["latest"], [str(self.run_dir / "findings.run.json")])


if __name__ == "__main__":
    unittest.main()
