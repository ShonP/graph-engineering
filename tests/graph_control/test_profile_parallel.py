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
TIERS = {"opus", "sonnet"}
NEW_ROLES = {"reviewer-lead": "opus", "qa-lead": "sonnet", "researcher-spike": "sonnet"}
LANES_EXAMPLE = {"xcodebuild": 1, "cluster": 1, "local_db": 1}
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


if __name__ == "__main__":
    unittest.main()
