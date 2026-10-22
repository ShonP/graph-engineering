"""writable_companions: profile pairs that validate-plan --profile enforces on writable_paths."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import dump, plan_data
from graph_control import companions
from graph_control.common import Invalid
from graph_control.plan import Plan

CLI = Path(__file__).resolve().parents[2] / "scripts" / "graph-control.py"
PAIR = 'writable_companions:\n  - when: "apps/web/**"\n    also: "packages/i18n/**"\n'
SHAPE = "writable_companions must be a list of {when: <glob>, also: <glob>}"
BASELINE = '{"cases": 1, "critical_path": 1, "status": "PASS", "tasks": 1}\n'


def plan_with(paths):
    data = plan_data()
    data["tasks"][0]["writable_paths"] = paths
    return data


class Parse(unittest.TestCase):
    def test_absent_and_empty_are_no_pairs(self):
        self.assertEqual(companions.parse({}), ())
        self.assertEqual(companions.parse({"writable_companions": []}), ())

    def test_pairs_parse_in_order(self):
        value = [{"when": "apps/web/**", "also": "packages/i18n/**"}, {"when": "a/*", "also": "b/*"}]
        self.assertEqual(companions.parse({"writable_companions": value}),
                         (("apps/web/**", "packages/i18n/**"), ("a/*", "b/*")))

    def test_bad_shapes_name_the_shape(self):
        for value in ("apps/web/**", None, {"when": "a", "also": "b"}, ["a"], [{"when": "a"}],
                      [{"when": "a", "also": "b", "extra": "c"}], [{"when": "", "also": "b"}],
                      [{"when": "a", "also": 3}]):
            with self.subTest(value=value):
                with self.assertRaises(Invalid) as raised:
                    companions.parse({"writable_companions": value})
                self.assertEqual(str(raised.exception), SHAPE)


class Missing(unittest.TestCase):
    pairs = (("apps/web/**", "packages/i18n/**"),)

    def test_trigger_without_companion_names_the_glob_to_add(self):
        plan = Plan.parse(plan_with(["apps/web/src/a.ts"]))
        self.assertEqual(companions.missing_companions(plan, self.pairs),
                         ['task T1: writable_paths match "apps/web/**" but not its companion '
                          '"packages/i18n/**"; add "packages/i18n/**"'])

    def test_one_message_per_task_and_pair(self):
        plan = Plan.parse(plan_with(["apps/web/src/a.ts", "apps/web/src/b.ts"]))
        self.assertEqual(len(companions.missing_companions(plan, self.pairs)), 1)

    def test_companion_glob_or_matching_path_satisfies(self):
        for companion in ("packages/i18n/**", "packages/i18n/en.json"):
            with self.subTest(companion=companion):
                plan = Plan.parse(plan_with(["apps/web/src/a.ts", companion]))
                self.assertEqual(companions.missing_companions(plan, self.pairs), [])

    def test_unrelated_path_does_not_trigger(self):
        plan = Plan.parse(plan_with(["apps/api/src/a.ts"]))
        self.assertEqual(companions.missing_companions(plan, self.pairs), [])

    def test_no_pairs_is_silent(self):
        self.assertEqual(companions.missing_companions(Plan.parse(plan_with(["apps/web/a.ts"])), ()), [])


class ValidatePlanProfile(unittest.TestCase):
    def run_cli(self, paths, profile=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = [sys.executable, str(CLI), "validate-plan", dump(root / "plan.json", plan_with(paths))]
            if profile is not None:
                (root / "profile.yaml").write_text(profile)
                argv += ["--profile", str(root / "profile.yaml")]
            result = subprocess.run(argv, capture_output=True, text=True)
        return result.returncode, result.stdout

    def test_ac_s10_miss_blocks_then_passes_with_companion(self):
        code, out = self.run_cli(["apps/web/src/a.ts"], PAIR)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["status"], "BLOCKED")
        self.assertIn('add "packages/i18n/**"', json.loads(out)["reason"])
        for companion in ("packages/i18n/**", "packages/i18n/en.json"):
            with self.subTest(companion=companion):
                code, out = self.run_cli(["apps/web/src/a.ts", companion], PAIR)
                self.assertEqual((code, json.loads(out)["status"]), (0, "PASS"))

    def test_ac_s10_silent_without_key_or_flag(self):
        baseline = self.run_cli(["app/stage/**"])
        self.assertEqual(baseline, (0, BASELINE))
        for profile in ("gates:\n  plan: owner\n", "writable_companions: []\n"):
            with self.subTest(profile=profile):
                self.assertEqual(self.run_cli(["app/stage/**"], profile), baseline)

    def test_ac_s10_silent_string_value_blocks_naming_the_shape(self):
        code, out = self.run_cli(["app/stage/**"], 'writable_companions: "apps/web/**"\n')
        self.assertEqual((code, json.loads(out)), (1, {"status": "BLOCKED", "reason": SHAPE}))

    def test_messages_join_across_tasks(self):
        data = plan_with(["apps/web/a.ts"])
        data["tasks"].append({**data["tasks"][0], "id": "T2", "produces": [], "writable_paths": ["apps/web/b.ts"]})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "profile.yaml").write_text(PAIR)
            result = subprocess.run([sys.executable, str(CLI), "validate-plan", dump(root / "plan.json", data),
                                     "--profile", str(root / "profile.yaml")], capture_output=True, text=True)
        message = 'writable_paths match "apps/web/**" but not its companion "packages/i18n/**"; add "packages/i18n/**"'
        self.assertEqual((result.returncode, json.loads(result.stdout)["reason"]),
                         (1, f"task T1: {message}; task T2: {message}"))


if __name__ == "__main__":
    unittest.main()
