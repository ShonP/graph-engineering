"""Compile and test-run lanes, and elastic slots, as the docs teach them (AC-LN-SPLIT-01..04).

A test run against an already built product never queues behind a compile: it
takes the test-run lane (`xctest`), compiles take the build lane (`xcodebuild`),
and an undeclared test-run lane gets the build lane's slot count. Every surface
that tells an agent to wrap a command says so. Generic: no consumer names.
"""
import re
import unittest

import yaml

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from test_profile_parallel import COMMAND, LANES_DOC, paragraph
from test_profile_template import ROOT
from test_profile_v2 import comment_before

TEST_LANE = "`xctest`"
BUILD_LANE = "`xcodebuild`"
RUN_WORD = "test-without-building"
FALLBACK = "build lane's slot count"
ELASTIC_FLAGS = ("--elastic", "--max-load", "--min-free-gb")
ELASTIC_KEYS = ("slots", "elastic", "max_load", "min_free_gb")
WRAPPING_SURFACES = (
    "agents/qa.md", "agents/qa-lead.md", "agents/implementer.md",
    "skills/process/qa-verification/SKILL.md", "skills/process/ux-evidence/SKILL.md", "README.md",
)
ENGINE_RUN = "docs/engine/run.md"


def flat(path):
    return re.sub(r"\s+", " ", (ROOT / path).read_text())


class LanesDoc(unittest.TestCase):
    def setUp(self):
        self.doc = flat(LANES_DOC.relative_to(ROOT))

    def test_states_the_compile_and_test_run_split_ac_ln_split_01(self):
        # The engine docs stay generic (test_engine_loop bans stack words); the Xcode
        # names live in /graph-init, the template and the agent prompts.
        for needle in ("build lane", "test-run lane", "already built product", "never compiles",
                       FALLBACK, "`/graph-init`", "simulator lease"):
            self.assertIn(needle, self.doc, needle)

    def test_states_elastic_slots_and_their_profile_keys_ac_ln_split_02(self):
        for needle in (*ELASTIC_FLAGS, *(f"`{key}`" for key in ELASTIC_KEYS), "per core",
                       "unreadable", "declared slots", "scripts/lane_host.py"):
            self.assertIn(needle, self.doc, needle)


class Profile(unittest.TestCase):
    def test_template_comment_names_the_test_lane_and_the_mapping_form_ac_ln_split_03(self):
        comment = comment_before("lanes:")
        self.assertIn("xctest", comment)
        self.assertIn(RUN_WORD, comment)
        mapping = re.search(r"#\s+mapping form: (\{.*\})", comment)
        self.assertIsNotNone(mapping, "commented mapping-form example missing")
        entry = yaml.safe_load(mapping.group(1))["xcodebuild"]
        self.assertEqual(set(entry), set(ELASTIC_KEYS))

    def test_graph_init_proposes_the_test_lane_beside_the_build_lane_ac_ln_split_03(self):
        section = paragraph("**Lanes.**")
        for needle in (TEST_LANE, RUN_WORD, FALLBACK, "--elastic"):
            self.assertIn(needle, section, needle)
        self.assertTrue(COMMAND.is_file())


class Surfaces(unittest.TestCase):
    def test_every_wrapping_surface_routes_test_runs_to_the_test_lane_ac_ln_split_04(self):
        for path in WRAPPING_SURFACES:
            with self.subTest(path=path):
                body = flat(path)
                for needle in (TEST_LANE, RUN_WORD, BUILD_LANE):
                    self.assertIn(needle, body, needle)

    def test_engine_brief_rule_names_both_lanes_generically_ac_ln_split_04(self):
        body = flat(ENGINE_RUN)
        for needle in ("test-run lane", "build lane", "already built product", "docs/engine/lanes.md"):
            self.assertIn(needle, body, needle)


if __name__ == "__main__":
    unittest.main()
