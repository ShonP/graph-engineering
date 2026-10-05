#!/usr/bin/env python3
"""Registration contract for hooks/hooks.json and the matching hooks/README.md.

Stdlib only. Run from any directory:

    python3 hooks/tests/test_hooks_registration.py

Covers AC-W1-REG-01 to AC-W1-REG-04: every registration the 0.15 contract
names, the `if` and statusMessage rules, and the README facts a consumer needs
(breaking change, version floors, opt-in file).
"""

import json
import re
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
ROOT = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/"


def load():
    return json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))["hooks"]


def handler(name, **extra):
    base = {"type": "command", "command": ROOT + name, "args": []}
    base.update(extra)
    return base


class RegistrationContract(unittest.TestCase):
    def test_events_are_exactly_the_contract(self):
        self.assertEqual(
            sorted(load()), ["PostToolUse", "PreToolUse", "SessionStart", "Stop"]
        )

    def test_posttooluse_lint_is_async(self):
        self.assertEqual(
            load()["PostToolUse"],
            [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        handler("lint-touched-file.sh", timeout=130, **{"async": True})
                    ],
                }
            ],
        )

    def test_pretooluse_guards(self):
        groups = load()["PreToolUse"]
        self.assertEqual([g["matcher"] for g in groups], ["Bash", "Agent|Task"])
        ifs = ["Bash(git *)", "Bash(rm *)", "Bash(docker *)"]
        # The sleep-loop guard has no `if`: a permission rule matches a command
        # prefix and would miss `cd x && until ...`.
        self.assertEqual(
            groups[0]["hooks"],
            [handler("guard-destructive.sh", timeout=10, **{"if": i}) for i in ifs]
            + [handler("guard-poll-loop.sh", timeout=5)],
        )
        self.assertEqual(
            groups[1]["hooks"], [handler("guard-agent.sh", timeout=15)]
        )

    def test_description_names_the_sleep_loop_guard(self):
        description = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))["description"]
        self.assertIn("sleep-loop", description)

    def test_stop_rewakes_and_has_no_matcher(self):
        self.assertEqual(
            load()["Stop"],
            [{"hooks": [handler("test-before-stop.sh", timeout=620, asyncRewake=True)]}],
        )

    def test_sessionstart_matcher_is_an_exact_list(self):
        self.assertEqual(
            load()["SessionStart"],
            [
                {
                    "matcher": "startup|clear|compact",
                    "hooks": [handler("print-handoff.sh", timeout=15)],
                },
                {
                    "matcher": "startup",
                    "hooks": [handler("doctor-on-start.sh", timeout=5)],
                },
            ],
        )

    def test_if_only_on_tool_events_one_rule_each(self):
        for event, groups in load().items():
            for group in groups:
                for h in group["hooks"]:
                    if event in ("Stop", "SessionStart"):
                        self.assertNotIn("if", h, event)
                    if "if" in h:
                        # one permission rule: no list, pipe or brace syntax
                        self.assertRegex(h["if"], r"^Bash\([^|{},]+\)$")

    def test_no_status_message_on_background_entries(self):
        for groups in load().values():
            for group in groups:
                for h in group["hooks"]:
                    if h.get("async") or h.get("asyncRewake"):
                        self.assertNotIn("statusMessage", h)

    def test_command_shape_is_plugin_root_relative(self):
        # Only the command shape is asserted here; each script's behaviour is
        # covered by its own test module.
        for groups in load().values():
            for group in groups:
                for h in group["hooks"]:
                    self.assertRegex(h["command"], r"^\$\{CLAUDE_PLUGIN_ROOT\}/hooks/scripts/[a-z-]+\.sh$")


class ReadmeContract(unittest.TestCase):
    longMessage = False  # a miss names the needle, not the whole README

    @classmethod
    def setUpClass(cls):
        cls.text = (HOOKS_DIR / "README.md").read_text(encoding="utf-8")

    def test_removed_autodetect_is_mentioned_only_in_the_removal_note(self):
        hits = [
            line
            for line in self.text.splitlines()
            if re.search(r"autodetect|Taskfile|uv run test", line, re.I)
        ]
        self.assertTrue(hits, "the removal note must exist")
        for line in hits:
            self.assertRegex(line, r"(?i)removed in 0\.15", line)

    def test_states_breaking_change_floors_and_opt_in(self):
        for needle in (
            r"(?i)breaks 0\.14 autodetect",
            r"2\.1\.271",
            r"2\.1\.285",
            r"`if`[^\n]*2\.1\.85",
            r"2\.1\.89",
            r"background_tasks[^\n]*2\.1\.145",
            r"\.claude/graph-checks\.json",
            r"templates/graph-checks\.json",
            r"bash scripts/run-all-tests\.sh",
            r"policy-override: <reason>",
            r"\.graph/ledger\.md",
            r"stop_hook_active",
            r"asyncRewake",
            r"lint skipped",
        ):
            self.assertRegex(self.text, needle, "README lacks: " + needle)

    def test_documents_every_guard_rule(self):
        for needle in (
            r"git remote remove",
            r"--force-with-lease",
            r"docker volume rm",
            r"system prune -a",
            r"--volumes",
            r"\.git",
        ):
            self.assertRegex(self.text, needle, "README lacks: " + needle)

    def test_documents_timeout_bounds(self):
        self.assertRegex(self.text, r"600")
        self.assertRegex(self.text, r"120")
        self.assertRegex(self.text, r"\b60\b")

    def test_generic_and_dash_free(self):
        for name in ("README.md", "hooks.json"):
            body = (HOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn(chr(0x2014), body, name + " has an em dash")
            self.assertNotRegex(body, r"(?i)koach|fitness", name + " names a consumer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
