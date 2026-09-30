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


SIGNAL = {"goal": "checkout errors stay rare", "source": "prometheus",
          "command": ["promtool", "query", "instant", "http://prometheus:9090", "sum(rate(errors[1d]))"],
          "success_condition": "value <= 0.01", "window_days": 7}


def v2(**extra):
    """A SYNTHETIC schema v2 plan: the v1 fixture plus the given top-level keys."""
    return {**plan_data(), "schema_version": 2, **extra}


class SuccessSignalTests(unittest.TestCase):
    def test_v1_parses_without_signals(self):  # AC-W4-SS-01
        plan = Plan.parse(plan_data())
        self.assertEqual((plan.success_signals, plan.success_signals_reason), ((), None))

    def test_v1_rejects_signal_keys(self):  # AC-W4-SS-01
        for extra in ({"success_signals": [SIGNAL]}, {"success_signals": []},
                      {"success_signals_reason": "internal refactor"}):
            with self.subTest(extra=extra), self.assertRaisesRegex(Invalid, "schema_version 2"):
                Plan.parse({**plan_data(), **extra})

    def test_v2_without_signals_parses(self):
        self.assertEqual(Plan.parse(v2()).success_signals, ())

    def test_v2_valid_signals_parse(self):  # AC-W4-SS-02
        second = {**SIGNAL, "source": "sql-readonly", "command": ["psql", "-c", "select count(*) from orders"],
                  "success_condition": "value >= baseline * 1.1 + 5", "window_days": 90}
        plan = Plan.parse(v2(success_signals=[SIGNAL, second]))
        self.assertEqual([(s.source, s.window_days) for s in plan.success_signals],
                         [("prometheus", 7), ("sql-readonly", 90)])
        self.assertEqual(plan.success_signals[1].command, ("psql", "-c", "select count(*) from orders"))

    def test_empty_signals_need_a_reason(self):  # AC-W4-SS-02
        with self.assertRaisesRegex(Invalid, "success_signals_reason"):
            Plan.parse(v2(success_signals=[]))
        with self.assertRaises(Invalid):
            Plan.parse(v2(success_signals=[], success_signals_reason=" "))
        plan = Plan.parse(v2(success_signals=[], success_signals_reason="internal refactor, no user signal"))
        self.assertEqual(plan.success_signals_reason, "internal refactor, no user signal")

    def test_reason_only_explains_an_empty_list(self):
        for extra in ({"success_signals_reason": "why"},
                      {"success_signals": [SIGNAL], "success_signals_reason": "why"}):
            with self.subTest(extra=extra), self.assertRaisesRegex(Invalid, "success_signals_reason"):
                Plan.parse(v2(**extra))

    def test_bad_signal_fields_rejected(self):  # AC-W4-SS-02
        for change in ({"source": "datadog"}, {"success_condition": "value < foo"}, {"window_days": 0},
                       {"window_days": 91}, {"window_days": True}, {"window_days": 7.0}, {"goal": ""},
                       {"command": []}, {"command": "promtool query"}, {"command": ["promtool", 1]},
                       {"command": ["promtool", ""]}):
            with self.subTest(change=change), self.assertRaises(Invalid):
                Plan.parse(v2(success_signals=[{**SIGNAL, **change}]))

    def test_signal_fields_are_exact(self):
        missing = {key: value for key, value in SIGNAL.items() if key != "window_days"}
        for signal in (missing, {**SIGNAL, "query": "rows"}):
            with self.subTest(signal=signal), self.assertRaisesRegex(Invalid, "fields"):
                Plan.parse(v2(success_signals=[signal]))

    def test_argv_may_repeat_a_flag(self):
        command = ["curl", "-H", "a: 1", "-H", "b: 2", "https://sentry.example.invalid/api"]
        Plan.parse(v2(success_signals=[{**SIGNAL, "source": "sentry", "command": command}]))

    def test_condition_grammar(self):  # AC-W4-SS-03
        accepted = ["value <= 0.01", "value >= baseline * 1.1 + 5", "value < 3", "value > -1",
                    "value == 0", "value >= baseline * 0.95", "value < baseline * 2 + -0.5"]
        rejected = ["value < foo", "x > 1", "value != 1", "value => 1", "value <= 0.01 ", " value <= 1",
                    "value<=1", "value >= baseline", "value >= 1.1 * baseline", "value >= baseline * 1.1 - 5",
                    "value > 1e3", "value > .5", "value > 1 and value < 2", "", "VALUE > 1"]
        for condition in accepted:
            with self.subTest(accepted=condition):
                Plan.parse(v2(success_signals=[{**SIGNAL, "success_condition": condition}]))
        for condition in rejected:
            with self.subTest(rejected=condition), self.assertRaises(Invalid):
                Plan.parse(v2(success_signals=[{**SIGNAL, "success_condition": condition}]))

    def test_unknown_plan_versions_rejected(self):
        for value in (0, 3, "2", True, 2.0):
            with self.subTest(value=value), self.assertRaisesRegex(Invalid, "schema_version must be 1 or 2"):
                Plan.parse({**plan_data(), "schema_version": value})

    def test_v2_keeps_plan_validation(self):
        data = v2(success_signals=[SIGNAL])
        data["tasks"][0]["depends_on"] = ["T1"]
        with self.assertRaisesRegex(Invalid, "cyclic or unknown"):
            Plan.parse(data)


if __name__ == "__main__":
    unittest.main()
