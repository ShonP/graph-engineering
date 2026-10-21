import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hygiene_fixture import commit_at, make_repo, stage, write_profile
from helpers import dump, plan_data
from graph_control import cli
from graph_control.common import Invalid
from graph_control.plan import Plan

NEED = {"user": "example-user", "trigger": "weekly export takes 40 min by hand",
        "run": ["bash", "tools/newtool/run.sh"]}
MEASURE = {"command": ["bash", "tools/old/bench.sh"], "baseline": "p50 120 ms on acme-widget"}
PROFILE = "hygiene:\n  surfaces:\n    roots: [\"tools/*\"]\n  measure:\n    paths: [\"**/package.json\"]\n"
NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def plan(schema=2, **task):
    data = plan_data()
    data["schema_version"] = schema
    data["tasks"][0].update(task)
    return data


SHAPE = [
    ("need", plan(need=NEED), None),
    ("measure", plan(measure=MEASURE), None),
    ("both", plan(need=NEED, measure=MEASURE), None),
    ("neither", plan(), None),
    ("schema 1 without keys", plan(schema=1), None),
    ("need null", plan(need=None), "^task T1: need must not be null"),
    ("measure null", plan(measure=None), "^task T1: measure must not be null"),
    ("need not an object", plan(need="example-user"), "^task T1: need must be an object"),
    ("need empty user", plan(need={**NEED, "user": " "}), "^task T1: need.user must be nonempty text"),
    ("need empty trigger", plan(need={**NEED, "trigger": ""}), "^task T1: need.trigger must be nonempty text"),
    ("need user not text", plan(need={**NEED, "user": 3}), "^task T1: need.user must be nonempty text"),
    ("need empty run", plan(need={**NEED, "run": []}), "^task T1: need.run must be a nonempty argv"),
    ("need run blank arg", plan(need={**NEED, "run": ["bash", ""]}), "^task T1: need.run must be a nonempty argv"),
    ("need run string", plan(need={**NEED, "run": "bash run.sh"}), "^task T1: need.run must be a nonempty argv"),
    ("need run null", plan(need={**NEED, "run": None}), "^task T1: need.run must be a nonempty argv"),
    ("need unknown subkey", plan(need={**NEED, "owner": "example-user"}),
     r"^task T1: need has unknown fields \['owner'\]"),
    ("need missing subkey", plan(need={"user": "example-user", "run": ["bash"]}),
     r"^task T1: need is missing fields \['trigger'\]"),
    ("measure empty command", plan(measure={**MEASURE, "command": []}),
     "^task T1: measure.command must be a nonempty argv"),
    ("measure empty baseline", plan(measure={**MEASURE, "baseline": "  "}),
     "^task T1: measure.baseline must be nonempty text"),
    ("measure null baseline", plan(measure={**MEASURE, "baseline": None}),
     "^task T1: measure.baseline must be nonempty text"),
    ("measure unknown subkey", plan(measure={**MEASURE, "after": "p50 90 ms"}),
     r"^task T1: measure has unknown fields \['after'\]"),
    ("need in schema 1", plan(schema=1, need=NEED), "^task T1: need requires schema_version 2"),
    ("measure in schema 1", plan(schema=1, measure=MEASURE), "^task T1: measure requires schema_version 2"),
]


class Shape(unittest.TestCase):
    def test_verdict_table(self):
        for name, data, message in SHAPE:
            with self.subTest(name):
                if message is None:
                    Plan.parse(data)
                else:
                    with self.assertRaisesRegex(Invalid, message):
                        Plan.parse(data)

    def test_fields_parsed_onto_task(self):
        task = Plan.parse(plan(need=NEED, measure=MEASURE)).tasks[0]
        self.assertEqual((task.need.user, task.need.trigger, task.need.run), (NEED["user"], NEED["trigger"],
                                                                              ("bash", "tools/newtool/run.sh")))
        self.assertEqual((task.measure.command, task.measure.baseline), (("bash", "tools/old/bench.sh"),
                                                                         MEASURE["baseline"]))

    def test_absent_fields_default_to_none(self):
        task = Plan.parse(plan()).tasks[0]
        self.assertEqual((task.need, task.measure), (None, None))


def validate(directory, data, *flags):
    path = dump(Path(directory) / "plan.json", data)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["validate-plan", path, *flags])
    return code, json.loads(out.getvalue())


class Enforce(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_repo(Path(self.tmp.name))
        stage(self.root, "tools/old/a.sh", "true\n")
        commit_at(self.root, "seed", 1, NOW)
        self.profile = write_profile(Path(self.tmp.name), PROFILE)
        self.flags = ("--profile", str(self.profile), "--root", str(self.root))

    def check(self, paths, **task):
        return validate(self.tmp.name, plan(writable_paths=paths, **task), *self.flags)

    def test_new_surface_without_need_is_blocked(self):
        self.assertEqual(self.check(["tools/newtool/**"]),
                         (1, {"status": "BLOCKED", "reason": "task T1: creates new surface tools/newtool without need"}))

    def test_new_surface_with_need_passes(self):
        code, out = self.check(["tools/newtool/**"], need=NEED)
        self.assertEqual((code, out["status"]), (0, "PASS"))

    def test_new_surface_from_a_file_path_is_blocked(self):
        code, out = self.check(["tools/newtool/run.sh"])
        self.assertEqual((code, out["reason"]), (1, "task T1: creates new surface tools/newtool without need"))

    def test_existing_surface_passes(self):
        for path in ("tools/old/**", "tools/old/b.sh", "tools/**", "tools/new.sh", "web/app/**"):
            with self.subTest(path):
                self.assertEqual(self.check([path])[0], 0)

    def test_untracked_files_do_not_make_a_surface_exist(self):
        (self.root / "tools" / "newtool").mkdir()
        (self.root / "tools" / "newtool" / "draft.sh").write_text("true\n")
        self.assertEqual(self.check(["tools/newtool/**"])[0], 1)

    def test_measure_path_without_measure_is_blocked(self):
        self.assertEqual(self.check(["web/package.json"]),
                         (1, {"status": "BLOCKED", "reason": "task T1: changes web/package.json without measure"}))

    def test_measure_path_with_measure_passes(self):
        self.assertEqual(self.check(["web/package.json"], measure=MEASURE)[0], 0)

    def test_surface_and_measure_path_need_both(self):
        paths = ["tools/newtool/**", "tools/newtool/package.json"]
        self.assertEqual(self.check(paths)[1]["reason"],
                         "task T1: creates new surface tools/newtool without need; "
                         "task T1: changes tools/newtool/package.json without measure")
        self.assertEqual(self.check(paths, need=NEED)[1]["reason"],
                         "task T1: changes tools/newtool/package.json without measure")
        self.assertEqual(self.check(paths, measure=MEASURE)[1]["reason"],
                         "task T1: creates new surface tools/newtool without need")
        self.assertEqual(self.check(paths, need=NEED, measure=MEASURE)[0], 0)

    def test_without_flags_only_the_shape_is_checked(self):
        data = plan(writable_paths=["tools/newtool/**", "web/package.json"])
        self.assertEqual(validate(self.tmp.name, data),
                         (0, {"cases": 1, "critical_path": 1, "status": "PASS", "tasks": 1}))

    def test_flags_go_together(self):
        for flags in (("--profile", str(self.profile)), ("--root", str(self.root))):
            with self.subTest(flags[0]):
                code, out = validate(self.tmp.name, plan(), *flags)
                self.assertEqual((code, out["status"]), (1, "BLOCKED"))
                self.assertIn("--profile and --root", out["reason"])

    def test_root_that_is_not_a_git_repo_is_blocked(self):
        other = Path(self.tmp.name) / "plain"
        other.mkdir()
        code, out = validate(self.tmp.name, plan(), "--profile", str(self.profile), "--root", str(other))
        self.assertEqual((code, out["reason"]), (1, f"not a git repository with a HEAD commit: {other}"))

    def test_invalid_profile_is_blocked(self):
        self.profile.write_text("hygiene:\n  measure:\n    pathz: []\n", encoding="utf-8")
        code, out = self.check(["web/package.json"])
        self.assertEqual((code, out["reason"]), (1, "unknown profile key hygiene.measure.pathz"))

    def test_unreadable_profile_yaml_is_blocked(self):
        self.profile.write_text("hygiene: [\n", encoding="utf-8")
        code, out = self.check(["web/package.json"])
        self.assertEqual(code, 1)
        self.assertTrue(out["reason"].startswith(f"profile {self.profile} cannot be read"), out["reason"])

    def test_empty_profile_enforces_nothing(self):
        self.profile.write_text("", encoding="utf-8")
        self.assertEqual(self.check(["tools/newtool/**", "web/package.json"])[0], 0)


if __name__ == "__main__":
    unittest.main()
