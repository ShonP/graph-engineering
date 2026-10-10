"""Golden checks for the qa time contract: no early lead return, shards, streaming
rows, checkpoints, device-only pre-classification, the coverage default, rerun
discipline, pid-only kills and one findings template.

Stdlib only; run by scripts/check-skill-scripts.sh. Each needle pins a rule a
retro traced to lost hours: a lead that returned "FAIL INCOMPLETE" while its
background leaves still ran, leaves that hit the turn cap with no report
written, rows driven for 30-45 min that a simulator can never observe, and a
`pkill -f` that killed sibling leaves' processes.
"""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]


def flat(path):
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


LEAD = flat(ROOT / "agents" / "qa-lead.md")
LEAF = flat(ROOT / "agents" / "qa.md")
SKILL = flat(SKILL_DIR / "SKILL.md")
RUN = flat(ROOT / "docs" / "engine" / "run.md")
PROFILE = (ROOT / "templates" / "graph-profile.yaml").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


class Case(unittest.TestCase):
    def has(self, text, *needles):
        for needle in needles:
            self.assertIn(needle, text)


class LeadWaitsOnMarkers(Case):
    def test_markers_gate_the_merge(self):
        self.has(LEAD, "`.graph/<run>/qa/r<N>/<lane>.done`", "graph-control.py qa-lanes",
                 "exit 75", "never on your own turn ending", "Never return while a lane is pending")

    def test_background_leaves_are_waited_on(self):
        self.has(LEAD, "run_in_background: true", "--wait 270")

    def test_the_wait_call_outlasts_its_block(self):
        # Review F4: under the default 120 s Bash timeout a 270 s wait is killed, not answered with exit 75.
        self.has(LEAD, "Bash timeout of 300000 ms")

    def test_rounds_are_unambiguous(self):
        # Review F1: a fix round's qa must never read round 1's markers or append to round 1's reports.
        self.has(LEAD, "`qa round: <N>`", "a fresh directory", "never reuse an earlier round's", "--round <N>")
        self.has(LEAF, '`"round"`', "never append to an earlier round's report")
        self.has(SKILL, "`.graph/<run>/qa/r<N>/`", "`--round`")
        self.has(RUN, "`qa round: <N>`")

    def test_an_empty_checkpoint_is_a_done_marker(self):
        # Review F3: a checkpoint with no remaining row is refused; the leaf writes `.done` instead.
        self.has(LEAF, "No row left: write `<lane>.done`, never a checkpoint")


class DeviceOnlyAtTheGate(Case):
    def test_device_only_blocked_is_not_a_setup_stop(self):
        # Review F5: a DEVICE-ONLY BLOCKED row reaches the merge gate as a device check, not NEEDS_SETUP.
        self.has(RUN, "A `DEVICE-ONLY` `BLOCKED` row is not a setup failure", "device-checklist.md",
                 "the merge gate's card lists those rows")

    def test_checkpointed_lane_gets_a_continuation(self):
        self.has(LEAD, "`<lane>.checkpoint.json`", "`remaining_rows`", "never re-runs a decided row")


class Shards(Case):
    def test_at_most_twenty_rows_per_leaf(self):
        self.has(LEAD, "at most 20 rows", "`<lane>-<k>`")
        self.has(SKILL, "at most 20 rows")


class PreClassification(Case):
    def test_lead_writes_device_checklist(self):
        self.has(LEAD, "`.graph/<run>/qa/device-checklist.md`", "DEVICE-ONLY", "never silently dropped")

    def test_skill_names_the_unobservable_classes(self):
        self.has(SKILL, "**Classify observability", "screen-reader announcement text", "focus order",
                 "OS settings panes", "real push delivery", "no local sink", "not running",
                 "`BLOCKED`", "DEVICE-ONLY", "device-checklist.md")


class Coverage(Case):
    def test_newest_runtime_by_default(self):
        self.has(SKILL, "newest runtime", "`qa.runtimes`")
        self.has(LEAD, "`qa.runtimes`")

    def test_profile_documents_the_key(self):
        self.assertRegex(PROFILE, r"(?m)^qa:\n  runtimes: \[\]")


class Leaf(Case):
    def test_turn_cap_raised(self):
        head = (ROOT / "agents" / "qa.md").read_text(encoding="utf-8").split("---")[1]
        self.assertIn("maxTurns: 400", head)

    def test_streams_rows_and_checkpoints(self):
        self.has(LEAF, "as soon as it is decided", "never batch", "85%", "`<lane>.checkpoint.json`",
                 "templates/lane.checkpoint.json", "PARTIAL")

    def test_writes_done_marker_last(self):
        self.has(LEAF, "`<lane>.done`", "templates/lane.done.json", "last act")

    def test_smoke_first_and_rerun_cap(self):
        self.has(LEAF, "one locale and one color scheme", "at most 2 fix-reruns")
        self.has(SKILL, "at most 2 fix-reruns")

    def test_kill_by_recorded_pid_only(self):
        self.has(LEAF, "recorded pid", "never `pkill -f`")
        self.has(SKILL, "recorded pid", "never `pkill -f`")

    def test_findings_template_is_the_schema(self):
        self.has(LEAF, "templates/qa-findings.json", "graph-control.py findings")
        self.has(LEAD, "templates/qa-findings.json")
        self.has(SKILL, "templates/qa-findings.json", "never `INCOMPLETE`")


class Hygiene(unittest.TestCase):
    def test_changelog_newest_section_names_it(self):
        # Unreleased plus the newest release: a release moves the entry from one to the other.
        sections = CHANGELOG.split("\n## [")[1:3]
        self.assertTrue(sections[0].startswith("Unreleased]"), "Unreleased must be the first section")
        newest = "".join(sections)
        self.assertIn("qa-lanes", newest)
        self.assertIn("device-checklist.md", newest)

    def test_no_em_dash_or_consumer_names(self):
        for path in (ROOT / "agents" / "qa-lead.md", ROOT / "agents" / "qa.md", SKILL_DIR / "SKILL.md",
                     *sorted((SKILL_DIR / "templates").glob("*.json"))):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(chr(0x2014), text, path.name)
            for word in ("koach", "fitness", "supabase", "voiceover"):
                self.assertNotIn(word, text.lower(), f"{path.name}: {word}")


if __name__ == "__main__":
    unittest.main()
