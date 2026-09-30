"""guard-agent policy semantics, the command module and the public CLI.

Payloads are SYNTHETIC, shaped after the PreToolUse(Agent) stdin keys spike j
observed on CLI 2.1.285 and the hooks reference: common fields, tool_input with
description/prompt/subagent_type and optional model/run_in_background, and
agent_id/agent_type only when the call comes from inside a subagent.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import helpers  # noqa: F401 - puts scripts/ on sys.path
from graph_control.guard import decide

CLI = Path(__file__).resolve().parents[2] / "scripts" / "graph-control.py"
NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
POLICY = {"policy": {}}
PROFILE_YAML = ("policy:\n  never: [haiku, fable]\n  block_types: [general-purpose]\n"
                "localAgents:\n  review: my-reviewer\n")
BLOCKED = ("graph-engineering policy: subagent type general-purpose is blocked in this repo. "
           "Dispatch a roster agent (graph-engineering:implementer, implementer-simple, reviewer, "
           "researcher, qa, planner, ux-designer, retro), or add a line policy-override: <reason> to the prompt.")


def payload(nested=False, **tool_input):
    """Synthetic hook stdin; nested=True adds the fields a subagent's call carries."""
    data = {"session_id": "synthetic-session", "transcript_path": "/tmp/synthetic.jsonl", "cwd": "/tmp/project",
            "permission_mode": "default", "hook_event_name": "PreToolUse", "tool_name": "Agent",
            "tool_use_id": "toolu_synthetic",
            "tool_input": {"description": "Review task 3", "prompt": "Review the diff.", **tool_input}}
    if nested:
        data.update(agent_id="agent-synthetic-1", agent_type="graph-engineering:implementer")
    return data


def reason(decision):
    return decision.output["hookSpecificOutput"]["permissionDecisionReason"]


class NoPolicy(unittest.TestCase):
    def test_missing_profile_or_policy_is_none(self):
        for profile in (None, {}, {"routing": {}}, ["policy"], "policy: {}"):
            with self.subTest(profile=profile):
                decision = decide(payload(subagent_type="general-purpose", model="haiku"), profile)
                self.assertEqual((decision.kind, decision.output, decision.ledger_line), ("none", None, None))


class Deny(unittest.TestCase):
    def test_general_purpose_names_the_roster_and_the_override_line(self):
        decision = decide(payload(subagent_type="general-purpose"), POLICY)
        self.assertEqual(decision.kind, "deny")
        self.assertEqual(decision.output, {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": BLOCKED}})

    def test_omitted_type_is_the_hosts_general_purpose_fallback(self):
        self.assertEqual(reason(decide(payload(), POLICY)), BLOCKED)

    def test_never_models_are_denied_with_the_tier_hint(self):
        for model in ("haiku", "fable"):
            with self.subTest(model=model):
                decision = decide(payload(subagent_type="graph-engineering:reviewer", model=model), POLICY)
                self.assertEqual(decision.kind, "deny")
                self.assertEqual(reason(decision), f"graph-engineering policy: model {model} is not allowed "
                                                   "here (policy.never). Omit model or use opus.")

    def test_never_applies_to_untiered_types_too(self):
        decision = decide(payload(subagent_type="Explore", model="haiku"), POLICY)
        self.assertEqual(reason(decision), "graph-engineering policy: model haiku is not allowed here "
                                           "(policy.never). Omit model.")

    def test_profile_lists_replace_the_defaults(self):
        profile = {"policy": {"never": ["opus"], "block_types": ["Explore"]}}
        self.assertEqual(decide(payload(subagent_type="general-purpose"), profile).kind, "none")
        self.assertEqual(decide(payload(subagent_type="Explore"), profile).kind, "deny")
        self.assertEqual(decide(payload(subagent_type="other:x", model="fable"), profile).kind, "none")


class Rewrite(unittest.TestCase):
    def assert_rewritten(self, decision, tool_input, tier):
        self.assertEqual(decision.kind, "rewrite")
        output = decision.output["hookSpecificOutput"]
        self.assertEqual((output["hookEventName"], output["permissionDecision"]), ("PreToolUse", "allow"))
        self.assertEqual(output["updatedInput"], {**tool_input, "model": tier})

    def test_reviewer_without_model_keeps_every_other_field(self):
        data = payload(subagent_type="graph-engineering:reviewer", run_in_background=True)
        original = dict(data["tool_input"])
        self.assert_rewritten(decide(data, POLICY), original, "opus")
        self.assertEqual(data["tool_input"], original, "the payload must not be mutated")

    def test_implementer_simple_asking_for_opus_goes_to_sonnet(self):
        data = payload(subagent_type="graph-engineering:implementer-simple", model="opus")
        self.assert_rewritten(decide(data, POLICY), data["tool_input"], "sonnet")

    def test_matching_tier_and_foreign_types_are_none(self):
        for subagent_type, model in (("graph-engineering:reviewer", "opus"), ("qa", "sonnet"),
                                     ("Explore", None), ("Explore", "sonnet"), ("other-plugin:x", None),
                                     ("other-plugin:reviewer", "sonnet")):
            with self.subTest(subagent_type=subagent_type, model=model):
                extra = {"model": model} if model else {}
                self.assertEqual(decide(payload(subagent_type=subagent_type, **extra), POLICY).kind, "none")

    def test_local_agents_take_their_legs_tier_in_both_shapes(self):
        profile = {"policy": {}, "localAgents": {"review": "my-reviewer", "qa": "forge:forge-qa",
                                                 "implement": {"web": "web-impl", "ios": "ios-impl"},
                                                 "visual": "visual-reviewer"}}
        for subagent_type, tier in (("my-reviewer", "opus"), ("forge:forge-qa", "sonnet"), ("ios-impl", "opus")):
            with self.subTest(subagent_type=subagent_type):
                data = payload(subagent_type=subagent_type)
                self.assert_rewritten(decide(data, profile), data["tool_input"], tier)
        self.assertEqual(decide(payload(subagent_type="visual-reviewer"), profile).kind, "none")

    def test_profile_roles_override_a_default_tier(self):
        data = payload(subagent_type="graph-engineering:qa")
        self.assert_rewritten(decide(data, {"policy": {"roles": {"qa": "opus"}}}), data["tool_input"], "opus")


class Override(unittest.TestCase):
    PROMPT = "Explore the repo.\npolicy-override: owner approved a one-off spike\nThanks."

    def test_main_thread_override_is_logged_and_not_enforced(self):
        decision = decide(payload(subagent_type="general-purpose", prompt=self.PROMPT), POLICY, now=NOW)
        self.assertEqual((decision.kind, decision.output), ("override", None))
        self.assertEqual(decision.ledger_line, "- 2026-09-30T12:00:00+00:00 policy-override: type=general-purpose "
                                               "model=default agent=main reason=owner approved a one-off spike")

    def test_nested_override_names_the_calling_agent_and_model(self):
        data = payload(nested=True, subagent_type="graph-engineering:reviewer", model="haiku", prompt=self.PROMPT)
        self.assertEqual(decide(data, POLICY, now=NOW).ledger_line,
                         "- 2026-09-30T12:00:00+00:00 policy-override: type=graph-engineering:reviewer model=haiku "
                         "agent=agent-synthetic-1 reason=owner approved a one-off spike")

    def test_ledger_fields_cannot_inject_lines(self):
        data = payload(nested=True, subagent_type="x\n- forged", prompt="policy-override: why\r- forged too")
        line = decide(data, POLICY, now=NOW).ledger_line
        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)


class CommandLine(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.profile = self.root / "graph-profile.yaml"
        self.profile.write_text(PROFILE_YAML)

    def guard(self, data):
        stdin = data if isinstance(data, str) else json.dumps(data)
        return subprocess.run([sys.executable, str(CLI), "guard-agent", "--profile", str(self.profile),
                               "--root", str(self.root)], input=stdin, capture_output=True, text=True)

    def test_prints_the_hook_json_and_exits_zero(self):
        data = payload(subagent_type="my-reviewer")
        result = self.guard(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"],
                         {**data["tool_input"], "model": "opus"})

    def test_override_appends_exactly_one_ledger_line(self):
        result = self.guard(payload(subagent_type="general-purpose", prompt="go\npolicy-override: spike"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        ledger = (self.root / ".graph" / "ledger.md").read_text()
        self.assertRegex(ledger, r"\A- \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00 policy-override: "
                                 r"type=general-purpose model=default agent=main reason=spike\n\Z")

    def test_load_errors_fail_open(self):
        blocked = json.dumps(payload(subagent_type="general-purpose"))
        cases = {"duplicate profile key": ("policy: {}\npolicy: {}\n", blocked),
                 "stdin is not JSON": (PROFILE_YAML, "not json")}
        for label, (profile, stdin) in cases.items():
            with self.subTest(label):
                self.profile.write_text(profile)
                result = self.guard(stdin)
                self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        self.profile.unlink()
        self.assertEqual(self.guard(payload(subagent_type="general-purpose")).stdout, "")
        self.assertFalse((self.root / ".graph").exists())


if __name__ == "__main__":
    unittest.main()
