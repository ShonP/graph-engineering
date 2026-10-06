"""Every agent and skill that boots a simulator routes it through sim-session.sh.

The owner saw subagents leave simulators (and Simulator.app) running, eating
CPU and RAM. The guard is scripts/sim-session.sh plus the Stop/SubagentStop
reaper; this test keeps the prose that sends agents to the guard in place.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDES = (
    "agents/implementer.md",
    "agents/qa-lead.md",
    "skills/process/qa-verification/SKILL.md",
    "skills/process/ux-evidence/SKILL.md",
    "skills/ux/ux-journey/SKILL.md",
)


class SimulatorRule(unittest.TestCase):
    def test_every_simulator_guide_names_the_wrapper_and_forbids_the_gui(self):
        for rel in GUIDES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(rel):
                self.assertIn("scripts/sim-session.sh", text)
                self.assertIn("Never `open -a Simulator`", text)
                self.assertIn("Close what you open", text)

    def test_capture_targets_the_wrapped_device_not_whatever_is_booted(self):
        text = (ROOT / "skills/process/ux-evidence/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("simctl io booted", text)
        self.assertIn("$SIM_UDID", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
