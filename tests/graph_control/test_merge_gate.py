"""Merge-gate rule: the profile read from the run base decides when a green change merges without the owner.

Profiles are SYNTHETIC dicts built from the template's `gates` block.
"""

import importlib.util
import unittest

import helpers  # noqa: F401 - puts scripts/ on sys.path

if importlib.util.find_spec("wcmatch") is None:
    raise unittest.SkipTest("needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

from graph_control.merge_rule import FLOOR, Decision, Inputs, decide, mode  # noqa: E402

OWNER = ["destructive", "credentials-and-access", "spend", "outbound-messaging"]


def profile(merge_auto=None, auto_classes=()):
    gates = {"plan": "owner", "merge": "owner", "owner_classes": list(OWNER), "auto_classes": list(auto_classes),
             "quick": ""}
    if merge_auto is not None:
        gates["merge_auto"] = merge_auto
    return {"gates": gates}


def green(rows=("agent-control",), **overrides):
    values = {"risk_rows": tuple(rows), "changed_paths": ("src/app.py",), "blocking": 0, "important": 0,
              "qa_verdict": "PASS", "verify_ok": True}
    values.update(overrides)
    return Inputs(**values)


def failed(decision: Decision) -> list[str]:
    return [reason for reason in decision.reasons if reason.startswith("failed:")]


class MergeGateTest(unittest.TestCase):
    def assertShut(self, decision: Decision, needle: str) -> None:
        self.assertFalse(decision.open, decision.reasons)
        self.assertTrue(any(needle in reason for reason in failed(decision)), decision.reasons)

    def test_s1_agent_control_waits_when_merge_auto_off(self):
        for merge_auto in (None, "off"):
            with self.subTest(merge_auto=merge_auto):
                decision = decide(profile(merge_auto), green())
                self.assertEqual("off", decision.mode)
                self.assertShut(decision, "agent-control")

    def test_s1_off_opens_only_for_auto_classes(self):
        self.assertTrue(decide(profile("off", ["docs"]), green(["docs"])).open)
        self.assertShut(decide(profile("off", ["docs"]), green(["docs", "infra"])), "infra")
        self.assertShut(decide(profile("off", ["docs", "agent-control"]), green()), "agent-control")
        self.assertShut(decide(profile("off"), green(())), "none")

    def test_s2_when_green_opens_for_agent_control(self):
        decision = decide(profile("when-green"), green())
        self.assertTrue(decision.open, decision.reasons)
        self.assertEqual("when-green", decision.mode)
        self.assertEqual(5, len(decision.reasons))
        self.assertTrue(all(reason.startswith("held:") for reason in decision.reasons), decision.reasons)

    def test_s2_finding_shuts(self):
        self.assertShut(decide(profile("when-green"), green(important=1)), "findings")
        self.assertShut(decide(profile("when-green"), green(blocking=1)), "findings")

    def test_s2_qa_must_be_exactly_pass(self):
        self.assertTrue(decide(profile("when-green"), green(qa_verdict=" PASS\n")).open)
        for verdict in ("PASS (static-only)", "FAIL INCOMPLETE: AC-2", "INCOMPLETE: AC-1", "", "pass", None):
            with self.subTest(verdict=verdict):
                self.assertShut(decide(profile("when-green"), green(qa_verdict=verdict)), "qa")

    def test_s2_verify_shuts(self):
        self.assertShut(decide(profile("when-green"), green(verify_ok=False)), "verify")

    def test_s3_owner_classes_wait_in_every_mode(self):
        for row in OWNER:
            for merge_auto, auto_merge in (("when-green", False), ("off", True), ("off", False)):
                with self.subTest(row=row, merge_auto=merge_auto, auto_merge=auto_merge):
                    inputs = green([row], auto_merge=auto_merge)
                    self.assertShut(decide(profile(merge_auto, [row]), inputs), row)

    def test_s3_composed_owner_class_names_it(self):
        decision = decide(profile("when-green"), green(["agent-control", "spend"]))
        self.assertShut(decision, "spend")
        self.assertFalse(any("agent-control" in reason for reason in failed(decision)), decision.reasons)

    def test_floor_paths_always_wait(self):
        for path in (".claude/graph-profile.yaml", "svc/.claude/graph-checks.json", "scripts/graph_control/risk.py",
                     "scripts/graph-control.py"):
            for merge_auto, auto_merge in (("when-green", False), ("off", True)):
                with self.subTest(path=path, merge_auto=merge_auto, auto_merge=auto_merge):
                    inputs = green(changed_paths=("src/app.py", path), auto_merge=auto_merge)
                    decision = decide(profile(merge_auto), inputs)
                    self.assertShut(decision, f"gate-floor {path}")
                    self.assertTrue(decision.reasons[0].startswith("failed: gate-floor"), decision.reasons)

    def test_floor_ignores_neighbours(self):
        inputs = green(changed_paths=(".claude/settings.json", "scripts/graph_controller.py", "docs/graph-profile.yaml"))
        self.assertTrue(decide(profile("when-green"), inputs).open)

    def test_floor_is_hard_coded(self):
        self.assertIn("**/.claude/graph-profile.yaml", FLOOR)
        self.assertIn("**/.claude/graph-checks.json", FLOOR)

    def test_auto_merge_alias(self):
        decision = decide(profile("off"), green(["agent-control", "outside-the-run"], auto_merge=True))
        self.assertTrue(decision.open, decision.reasons)
        self.assertEqual("auto-merge", decision.mode)
        self.assertShut(decide(profile("off"), green(["agent-control", "outside-the-run", "spend"], auto_merge=True)),
                        "spend")
        self.assertTrue(decide(profile("off"), green((), auto_merge=True)).open)
        self.assertTrue(decide(profile("when-green"), green(())).open)

    def test_mode_is_fail_safe(self):
        self.assertEqual("auto-merge", mode(profile("off"), True))
        self.assertEqual("when-green", mode(profile("when-green"), False))
        for value in (None, "off", False, "When-Green", "when-green ", True, "on", ["when-green"]):
            with self.subTest(value=value):
                self.assertEqual("off", mode(profile(value), False))
        for broken in ({}, {"gates": None}, {"gates": "when-green"}):
            with self.subTest(profile=broken):
                self.assertEqual("off", mode(broken, False))

    def test_reasons_are_ordered_and_complete(self):
        inputs = green(["spend"], changed_paths=("scripts/graph-control.py",), blocking=2, qa_verdict="",
                       verify_ok=False)
        decision = decide(profile("when-green"), inputs)
        self.assertFalse(decision.open)
        self.assertEqual(5, len(decision.reasons))
        self.assertEqual(5, len(failed(decision)))
        for reason, needle in zip(decision.reasons, ("gate-floor", "spend", "findings", "qa", "verify")):
            self.assertIn(needle, reason)

    def test_owner_classes_read_defensively(self):
        broken = {"gates": {"merge_auto": "when-green", "owner_classes": None}}
        self.assertTrue(decide(broken, green()).open)
        self.assertShut(decide({"gates": {"merge_auto": "when-green", "owner_classes": "infra"}}, green(["infra"])),
                        "infra")

    def test_spend_destructive_credentials_wait_even_when_profile_drops_them(self):
        for gates in ({"merge_auto": "when-green", "owner_classes": []}, {"merge_auto": "when-green"}):
            for row in ("spend", "destructive", "credentials-and-access"):
                with self.subTest(gates=gates, row=row):
                    self.assertShut(decide({"gates": gates}, green(["agent-control", row])), row)
                    self.assertShut(decide({"gates": gates}, green([row], auto_merge=True)), row)


if __name__ == "__main__":
    unittest.main()
