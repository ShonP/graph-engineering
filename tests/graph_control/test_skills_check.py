"""skills-check: a dispatch's REQUIRED skills against the child's `skills_loaded:` line.

Skill names here are SYNTHETIC or plugin names. A qualified name is proven only by
the identical qualified name; there is no host built-in list. The transcripts
under fixtures/transcripts are SYNTHETIC (see its README) and are read from a
temp CLAUDE_CONFIG_DIR copy, never the real config dir.
"""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli, skills
from graph_control.common import Invalid
from graph_control.skills import missing, names, unobserved
from graph_control.transcript import observed_skills, subagent_transcript

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "transcripts"
SUBAGENTS = Path("projects/-synthetic-repo/synthetic-session/subagents")
CLAIMED = "graph-engineering:prior-art,graph-engineering:definition-of-done,graph-engineering:bruno"


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


class Names(unittest.TestCase):
    def test_comma_separated_trimmed_and_deduplicated_in_order(self):
        self.assertEqual(names(" graph-engineering:bruno, prior-art ,,bruno-x, prior-art"),
                         ("graph-engineering:bruno", "prior-art", "bruno-x"))

    def test_empty_value_is_no_names(self):
        for value in ("", " ", ", ,", "skills_loaded:"):
            with self.subTest(value=value):
                self.assertEqual(names(value), ())

    def test_the_whole_return_line_is_accepted(self):
        self.assertEqual(names("skills_loaded: graph-engineering:bruno, superpowers:test-driven-development"),
                         ("graph-engineering:bruno", "superpowers:test-driven-development"))

    def test_backticks_annotations_and_case_are_tolerated(self):
        line = ("`skills_loaded: `Graph-Engineering:Bruno` (preloaded),  `superpowers:test-driven-development`"
                " (invoked, twice) , graph-engineering:prior-art`")
        self.assertEqual(names(line), ("graph-engineering:bruno", "superpowers:test-driven-development",
                                       "graph-engineering:prior-art"))

    def test_malformed_names_are_invalid(self):
        for value in ("two words", "graph-engineering:", ":", "a;b", "-rf", "a:b:c", "graph.engineering:x", "_x"):
            with self.subTest(value=value), self.assertRaises(Invalid):
                names(value)


class Missing(unittest.TestCase):
    def test_all_required_loaded_is_nothing_missing(self):
        self.assertEqual(missing(("graph-engineering:bruno", "superpowers:test-driven-development"),
                                 ("superpowers:test-driven-development", "graph-engineering:bruno")), [])

    def test_a_required_skill_absent_from_the_line_is_missing(self):
        # The measured failure: `bruno` REQUIRED, loaded 1 of 3 times.
        self.assertEqual(missing(("graph-engineering:bruno", "graph-engineering:prior-art"),
                                 ("graph-engineering:prior-art",)), ["graph-engineering:bruno"])

    def test_a_qualified_name_is_proven_only_by_the_identical_qualified_name(self):
        required = ("graph-engineering:security-review",)
        self.assertEqual(missing(required, ("security-review",)), list(required))
        self.assertEqual(missing(required, ("other-plugin:security-review",)), list(required))
        self.assertEqual(missing(required, ("graph-engineering:security-review",)), [])

    def test_a_bare_loaded_name_proves_only_a_bare_required_name(self):
        self.assertEqual(missing(("house-style",), ("house-style",)), [])
        self.assertEqual(missing(("house-style",), ("graph-engineering:house-style",)), ["house-style"])

    def test_no_static_host_snapshot(self):
        self.assertFalse(hasattr(skills, "HOST_BUILTINS"))

    def test_nothing_required_is_nothing_missing(self):
        self.assertEqual(missing((), ()), [])

    def test_no_skills_loaded_line_misses_every_required_skill_in_order(self):
        self.assertEqual(missing(("b:two", "a:one"), ()), ["b:two", "a:one"])


class Command(unittest.TestCase):
    def test_pass_exits_0_when_every_required_skill_loaded(self):
        code, out = invoke(["skills-check", "--required", "graph-engineering:bruno",
                            "--loaded", "graph-engineering:bruno (preloaded), graph-engineering:prior-art"])
        self.assertEqual((code, out), (0, {"status": "PASS", "required": 1, "missing": []}))

    def test_missing_skills_exit_1_naming_them(self):
        code, out = invoke(["skills-check", "--required", "graph-engineering:bruno,graph-engineering:security-review",
                            "--loaded", "security-review"])
        self.assertEqual((code, out), (1, {"status": "SKILLS_MISSING",
                                           "missing": ["graph-engineering:bruno", "graph-engineering:security-review"]}))

    def test_malformed_input_is_blocked_with_exit_2_naming_the_line_format(self):
        for flag in ("--loaded", "--required"):
            argv = {"--required": "graph-engineering:bruno", "--loaded": "graph-engineering:bruno", flag: "not a name"}
            with self.subTest(flag=flag):
                code, out = invoke(["skills-check", *(item for pair in argv.items() for item in pair)])
                self.assertEqual((code, out["status"]), (2, "BLOCKED"))
                self.assertIn("'not a name'", out["reason"])
                self.assertIn("skills_loaded: <plugin>:<skill>", out["reason"])


class Unobserved(unittest.TestCase):
    def test_claimed_names_the_transcript_lacks_in_claim_order(self):
        self.assertEqual(unobserved(("b:two", "a:one", "c:three"), frozenset({"a:one"})), ["b:two", "c:three"])

    def test_everything_observed_is_nothing_unobserved(self):
        self.assertEqual(unobserved(("a:one",), {"a:one", "b:two"}), [])


class ConfigDir(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = Path(temp.name) / "config"
        shutil.copytree(FIXTURES, self.config)
        self.subagents = self.config / SUBAGENTS
        patch = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)})
        patch.start()
        self.addCleanup(patch.stop)

    def check(self, required, loaded, agent_id=None):
        argv = ["skills-check", "--required", required, "--loaded", loaded]
        return invoke(argv + (["--agent-id", agent_id] if agent_id is not None else []))


class ObservedSkills(ConfigDir):
    def test_invoked_and_preloaded_skills_are_observed_and_assistant_text_is_not(self):
        self.assertEqual(observed_skills(self.subagents / "agent-aobserved.jsonl"),
                         {"graph-engineering:prior-art", "graph-engineering:definition-of-done",
                          "graph-engineering:impact-map"})

    def test_edges_errored_call_local_read_malformed_line_and_case(self):
        self.assertEqual(observed_skills(self.subagents / "agent-aedges.jsonl"),
                         {"local-baseline", "superpowers:test-driven-development"})

    def test_an_empty_transcript_observes_nothing(self):
        self.assertEqual(observed_skills(self.subagents / "agent-aempty.jsonl"), frozenset())


class Locate(ConfigDir):
    def test_finds_the_transcript_under_any_project(self):
        self.assertEqual(subagent_transcript("aobserved"), self.subagents / "agent-aobserved.jsonl")

    def test_unknown_id_is_none(self):
        self.assertIsNone(subagent_transcript("aunknown"))

    def test_two_matches_take_the_first_in_path_order(self):
        later = self.config / "projects/zz-later-repo/other-session/subagents"
        later.mkdir(parents=True)
        (later / "agent-aobserved.jsonl").write_text("")
        self.assertEqual(subagent_transcript("aobserved"), self.subagents / "agent-aobserved.jsonl")

    def test_malformed_ids_are_invalid(self):
        for value in ("../x", "a/b", "", "a" * 65, "a.b", "*"):
            with self.subTest(value=value), self.assertRaises(Invalid):
                subagent_transcript(value)

    def test_a_decoy_outside_projects_is_never_read(self):
        (self.config / "agent-x.jsonl").write_text((self.subagents / "agent-aobserved.jsonl").read_text())
        decoy = self.config / "elsewhere/p/s/subagents"
        decoy.mkdir(parents=True)
        (decoy / "agent-x.jsonl").write_text("")
        self.assertIsNone(subagent_transcript("x"))

    def test_a_symlink_out_of_projects_is_never_followed(self):
        outside = self.config / "outside.jsonl"
        outside.write_text("")
        (self.subagents / "agent-alink.jsonl").symlink_to(outside)
        self.assertIsNone(subagent_transcript("alink"))


class CommandWithAgentId(ConfigDir):
    def test_a_claimed_but_unobserved_skill_is_missing(self):
        code, out = self.check(CLAIMED, CLAIMED, "aobserved")
        self.assertEqual((code, out), (1, {"status": "SKILLS_MISSING", "missing": ["graph-engineering:bruno"],
                                           "unobserved": ["graph-engineering:bruno"]}))

    def test_the_same_lists_without_the_flag_pass_as_before(self):
        self.assertEqual(self.check(CLAIMED, CLAIMED),
                         (0, {"status": "PASS", "required": 3, "missing": []}))

    def test_claimed_and_observed_passes_from_the_transcript(self):
        required = "graph-engineering:prior-art,graph-engineering:definition-of-done"
        self.assertEqual(self.check(required, "Graph-Engineering:Prior-Art, " + required, "aobserved"),
                         (0, {"status": "PASS", "required": 2, "missing": [], "observed": "transcript"}))

    def test_observed_but_not_claimed_is_still_missing_and_not_unobserved(self):
        code, out = self.check("graph-engineering:definition-of-done,graph-engineering:prior-art",
                               "graph-engineering:prior-art", "aobserved")
        self.assertEqual((code, out), (1, {"status": "SKILLS_MISSING",
                                           "missing": ["graph-engineering:definition-of-done"], "unobserved": []}))

    def test_an_errored_skill_call_does_not_prove_the_claim(self):
        code, out = self.check("graph-engineering:bruno,local-baseline", "graph-engineering:bruno, local-baseline",
                               "aedges")
        self.assertEqual((code, out["missing"], out["unobserved"]),
                         (1, ["graph-engineering:bruno"], ["graph-engineering:bruno"]))

    def test_no_transcript_falls_back_to_the_claim_marked_unavailable(self):
        self.assertEqual(self.check(CLAIMED, CLAIMED, "aunknown"),
                         (0, {"status": "PASS", "required": 3, "missing": [], "observed": "unavailable"}))
        self.assertEqual(self.check(CLAIMED, "graph-engineering:bruno", "aunknown"),
                         (1, {"status": "SKILLS_MISSING", "observed": "unavailable",
                              "missing": ["graph-engineering:prior-art", "graph-engineering:definition-of-done"]}))

    def test_a_malformed_agent_id_is_blocked_naming_the_id_rule(self):
        for value in ("../x", "a/b", ""):
            with self.subTest(value=value):
                code, out = self.check(CLAIMED, CLAIMED, value)
                self.assertEqual((code, out["status"]), (2, "BLOCKED"))
                self.assertIn("[A-Za-z0-9_-]{1,64}", out["reason"])
                self.assertIn(repr(value), out["reason"])


if __name__ == "__main__":
    unittest.main()
