"""Profile blocks for parallel work: `bootstrap`, `lanes`, the lead and spike roles,
and how /graph-init proposes the first two.

Generic by construction: every assertion holds for a Python API, a Go CLI, a TS
monorepo or an Xcode app, and names no consumer. Acceptance rows AC-W3-PP-*.
"""
import re
import unittest

import yaml

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from test_profile_template import ROOT, load_template
from test_profile_v2 import comment_before

COMMAND = ROOT / "commands" / "graph-init.md"
LANES_DOC = ROOT / "docs" / "engine" / "lanes.md"
TEMPLATE = ROOT / "templates" / "graph-profile.yaml"
HOST = ROOT / "scripts" / "graph_control" / "host.py"
SLOT_RULE = "independent instances"
NAMESPACE_RULE = "per-task namespace"
TIERS = {"opus", "sonnet"}
NEW_ROLES = {"reviewer-lead": "opus", "qa-lead": "sonnet", "researcher-spike": "sonnet"}
LANES_EXAMPLE = {"xcodebuild": 1, "xctest": 2, "cluster": 1, "local_db": 1}
# lockfile -> the command /graph-init proposes for `bootstrap`.
BOOTSTRAP = {
    "pnpm-lock.yaml": "pnpm install --frozen-lockfile --offline",
    "package-lock.json": "npm ci --offline",
    "yarn.lock": "yarn install --immutable",
    "uv.lock": "uv sync --frozen",
    "Gemfile.lock": "bundle install",
    "go.sum": "go mod download",
    "project.yml": "xcodegen generate",
}


def text():
    return COMMAND.read_text()


def paragraph(title):
    """From the line holding `title` to the next bold paragraph, numbered step or heading."""
    lines = text().split("\n")
    start = next(i for i, line in enumerate(lines) if title in line)
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^(\s*\*\*[A-Z]|\d+\. \*\*|#)", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def bootstrap_rows():
    """(found cell, command) for every table row of the bootstrap proposal."""
    rows = []
    for line in paragraph("**Bootstrap.**").split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and len(cells) >= 2 and cells[1].startswith("`"):
            rows.append((cells[0], cells[1].strip("`")))
    return rows


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_template()

    def test_bootstrap_and_lanes_ship_empty(self):  # AC-W3-PP-01
        self.assertEqual(self.profile["bootstrap"], [])
        self.assertEqual(self.profile["lanes"], {})

    def test_lanes_comment_names_the_wrapper_and_a_parsing_example(self):
        comment = comment_before("lanes:")
        self.assertIn("scripts/lane-run.sh <lane> --slots <n>", comment)
        self.assertIn("serialized", comment)
        example = re.search(r"#\s+lanes: (\{.*\})", comment)
        self.assertIsNotNone(example, "commented lanes example missing")
        self.assertEqual(yaml.safe_load(example.group(1)), LANES_EXAMPLE)

    def test_bootstrap_comment_says_it_runs_per_task_worktree(self):
        comment = comment_before("bootstrap:")
        for needle in ("worktree", "install", "generat"):
            self.assertIn(needle, comment, needle)

    def test_policy_roles_add_the_leads_and_the_spike(self):  # AC-W3-PP-02
        roles = self.profile["policy"]["roles"]
        self.assertEqual({k: roles.get(k) for k in NEW_ROLES}, NEW_ROLES)

    def test_every_tier_is_opus_or_sonnet(self):  # AC-W3-PP-02
        policy = self.profile["policy"]
        self.assertEqual(set(policy["roles"].values()) - TIERS, set())
        self.assertLessEqual({"haiku", "fable"}, set(policy["never"]))


class GraphInitTests(unittest.TestCase):
    def test_bootstrap_table_maps_each_lockfile(self):  # AC-W3-PP-03
        rows = bootstrap_rows()
        for lockfile, command in BOOTSTRAP.items():
            with self.subTest(lockfile=lockfile):
                self.assertIn(command, [cmd for found, cmd in rows if f"`{lockfile}`" in found])

    def test_yarn_classic_is_not_given_the_berry_flag(self):
        # Spiked 2026-10-01: Yarn 1.22.22 ignores --immutable and rewrites the lockfile.
        rows = bootstrap_rows()
        berry = [found for found, cmd in rows if cmd == "yarn install --immutable"]
        classic = [found for found, cmd in rows if cmd == "yarn install --frozen-lockfile"]
        self.assertTrue(berry and "__metadata:" in berry[0], berry)
        self.assertTrue(classic and "yarn lockfile v1" in classic[0], classic)

    def test_bootstrap_guesses_nothing_and_waits_for_approval(self):
        section = paragraph("**Bootstrap.**")
        self.assertIn("gap", section)
        self.assertIn("approv", section)

    def test_lanes_rules(self):  # AC-W3-PP-03
        section = paragraph("**Lanes.**")
        for needle in ("`xcodebuild`", ".xcodeproj", "project.yml", "`cluster`", "infra.cluster",
                       "`local_db`", "runtime.up", "${GRAPH_RUN_ID", "runtime.none",
                       "scripts/lane-run.sh", "approv"):
            self.assertIn(needle, section, needle)

    def test_upgrade_fills_the_new_blocks_by_detection(self):
        up = paragraph("**Upgrade")
        self.assertIn("`bootstrap`", up)
        self.assertIn("`lanes`", up)
        self.assertIn("`host`", up)

    def test_host_floor_is_proposed_from_the_stack(self):
        section = paragraph("**Host floor.**")
        for needle in ("host.min_free_gb", "host-check", "20", "runtime.none", "docker", "lanes", "approv"):
            self.assertIn(needle, section, needle)


class LaneSlotTests(unittest.TestCase):
    """AC-LN-1: slots count the instances a host can run; a per-task namespace beats a lane."""

    def test_lanes_doc_states_the_slot_and_namespace_rules(self):
        doc = LANES_DOC.read_text()
        for needle in (SLOT_RULE, NAMESPACE_RULE, "GRAPH_RUN_ID", "<run>-t<n>",
                       "cannot be multiplied", "per-merge gate"):
            self.assertIn(needle, doc, needle)

    def test_template_lanes_comment_carries_both_rules(self):
        comment = comment_before("lanes:")
        self.assertIn(SLOT_RULE, comment)
        self.assertIn(NAMESPACE_RULE, comment)

    def test_graph_init_proposes_slots_from_evidence_not_one_by_default(self):
        section = paragraph("**Lanes.**")
        self.assertNotIn("each with 1 slot", section)
        self.assertIn(SLOT_RULE, section)
        self.assertIn(NAMESPACE_RULE, section)

    def test_host_floor_is_held_per_dispatch(self):
        self.assertIn("before each implementer dispatch", paragraph("**Host floor.**"))
        self.assertIn("before each implementer dispatch", comment_before("host:"))

    def test_no_wave_or_cluster_turn_wording(self):
        for path in (LANES_DOC, COMMAND, TEMPLATE, HOST):
            with self.subTest(path=path.name):
                self.assertIsNone(re.search(r"implementation wave|cluster turn", path.read_text()))
        self.assertNotIn("wave", HOST.read_text().split('"""')[1])


if __name__ == "__main__":
    unittest.main()
