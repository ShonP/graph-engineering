"""Golden checks for the implementer time-box, PARTIAL status and inner loop.

Stdlib only, like test_roster_policy.py. Guards AC-TB-1 and the `partial-status`
contract the engine parses (T11): the status word and its five field names.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents"
IMPLEMENTERS = ("implementer", "implementer-simple")
PARTIAL_FIELDS = (
    "green_commit", "done_cases", "remaining_cases", "remaining_scope", "elapsed_min",
)
PINNED = (
    "45 minutes",
    "date -u +%s",
    "Never commit red work",
    "focused tests",
    "full suite once at the end",
    "belongs to qa or the per-merge gate",
)


def body(name):
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1]


def section(text, heading):
    match = re.search(rf"(?ms)^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text)
    return match.group(1) if match else ""


class ImplementerBudget(unittest.TestCase):
    def test_time_box_and_inner_loop_wording(self):  # AC-TB-1
        for name in IMPLEMENTERS:
            text = body(name)
            for needle in PINNED:
                self.assertIn(needle, text, f"{name}: missing {needle!r}")

    def test_time_box_and_inner_loop_have_own_sections(self):  # AC-TB-1
        for name in IMPLEMENTERS:
            text = body(name)
            self.assertIn("45 minutes", section(text, "Time-box"), name)
            self.assertIn("focused tests", section(text, "Inner loop"), name)

    def test_integration_proof_names_device_and_cluster(self):  # AC-TB-1
        for name in IMPLEMENTERS:
            loop = section(body(name), "Inner loop")
            for kind in ("device", "cluster", "integration"):
                self.assertIn(kind, loop, f"{name}: inner loop lacks {kind!r}")

    def test_status_list_contains_partial(self):  # AC-TB-1
        for name in IMPLEMENTERS:
            statuses = re.findall(r"(?m)^- `([A-Z_]+)` - ", section(body(name), "Report"))
            self.assertIn("PARTIAL", statuses, name)

    def test_partial_block_names_every_field(self):  # AC-TB-1, contract partial-status
        for name in IMPLEMENTERS:
            report = section(body(name), "Report")
            for field in PARTIAL_FIELDS:
                self.assertIn(f"`{field}: ", report, f"{name}: missing field {field}")

    def test_nothing_green_reports_the_base_sha(self):  # contract partial-status
        # The engine keys "nothing green" on green_commit equal to the dispatch base SHA,
        # so `none` or a missing field would send a commitless task to review.
        for name in IMPLEMENTERS:
            report = section(body(name), "Report")
            self.assertIn("with nothing green, `green_commit` is the dispatch base SHA, never `none` or absent",
                          report, name)


if __name__ == "__main__":
    unittest.main()
