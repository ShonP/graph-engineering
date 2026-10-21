"""Golden checks for the researcher-spike agent (wave 3, P10).

Stdlib only, so it runs with plain `python3 -m unittest discover -s tests/agents`.
Each test names the acceptance row it guards (AC-W3-SP-*). The agent is a plain
prompt file, so the checks are on its frontmatter and on the contract phrases
its body must carry.
"""

import re
import subprocess
import unittest
from pathlib import Path

from test_roster_policy import split

ROOT = Path(__file__).resolve().parents[2]
SPIKE = ROOT / "agents" / "researcher-spike.md"
RESEARCHER = ROOT / "agents" / "researcher.md"
CHECK = ROOT / "scripts" / "check-agent-frontmatter.sh"

# Stack and consumer names the plugin core must never hard-code.
CONSUMER_WORDS = ("supabase", "swiftui", "nestjs")


class ResearcherSpikeFrontmatter(unittest.TestCase):
    def setUp(self):
        self.fm, self.body = split(SPIKE)

    def test_frontmatter_fields(self):  # AC-W3-SP-01
        self.assertEqual(self.fm.get("name"), "researcher-spike")
        self.assertEqual(self.fm.get("model"), "sonnet")
        self.assertEqual(self.fm.get("maxTurns"), "25")
        self.assertEqual(self.fm.get("omitClaudeMd"), "true")
        self.assertEqual(
            self.fm.get("tools"),
            ["Read", "Grep", "Glob", "Bash", "Write", "WebSearch", "WebFetch", "Skill"],
        )

    def test_frontmatter_check_passes_on_the_repo(self):  # AC-W3-SP-01
        done = subprocess.run(
            ["bash", str(CHECK), str(ROOT)], capture_output=True, text=True, check=False
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class ResearcherSpikeBody(unittest.TestCase):
    def setUp(self):
        self.fm, self.body = split(SPIKE)

    def has(self, needle):
        self.assertIn(needle, self.body)

    def test_no_claude_md_contract(self):  # AC-W3-SP-02
        for needle in (
            "no CLAUDE.md",
            "managed policy",
            "MEMORY.md",
            "profile path",
            "REQUIRED skills",
            "rule packs",
            "project invariants",
            "NEEDS_CONTEXT",
        ):
            self.has(needle)

    def test_verdict_vocabulary(self):  # AC-W3-SP-02
        for needle in (
            "hypothesis",
            "smallest experiment",
            "VALIDATED",
            "PARTIAL",
            "INVALIDATED",
            "edge case",
            "observation",
            "inference",
            "prior-art",
        ):
            self.has(needle)

    def test_partial_is_reported_never_extended(self):  # AC-W3-SP-02
        self.has("PARTIAL is reported, never extended")
        self.has("lower turn budget")

    def test_never_bypasses_owner_guards(self):  # AC-W3-SP-02
        self.has("Never bypass a guard, permission rule or shell function")
        self.has("BLOCKED")
        self.has("recipe")

    def test_report_lands_on_a_durable_repo_path(self):
        self.has("`<docsPath>/research/<UTC date>-spike-<slug>.md`")
        self.assertNotIn("in the temp directory your environment names and return", self.body)

    def test_return_and_cleanup_contract(self):  # AC-W3-SP-02
        for needle in ("1,500 tokens", "report path", "Clean up temp files"):
            self.has(needle)

    def test_no_savings_claim(self):  # DoD: savings are unmeasured until canary R3
        pattern = re.compile(r"\bsav(e|es|ed|ing|ings)\b|cheaper|fewer tokens", re.I)
        text = "\n".join(str(v) for v in self.fm.values()) + self.body
        self.assertIsNone(pattern.search(text))

    def test_generic_not_overfit_to_one_consumer(self):
        text = (self.body + str(self.fm.get("description", ""))).lower()
        for word in CONSUMER_WORDS:
            self.assertNotIn(word, text)

    def test_no_em_dash_or_retired_tier(self):
        text = SPIKE.read_text(encoding="utf-8")
        self.assertNotIn(chr(0x2014), text)
        self.assertNotIn("fable", text.lower())

    def test_no_polling_advice(self):
        polling = re.compile(r"sleep\s+\d|while\b.*\bsleep|until\b.*;\s*do|\bpoll\b", re.I)
        self.assertIsNone(polling.search(self.body))


class ResearcherPointsToSpike(unittest.TestCase):
    def setUp(self):
        self.fm, self.body = split(RESEARCHER)

    def spike_line(self):
        (line,) = [ln for ln in self.body.split("\n") if ln.startswith("- **spike**")]
        return line

    def test_spike_mode_points_to_the_agent(self):  # AC-W3-SP-03
        self.assertIn("researcher-spike", self.spike_line())

    def test_mode_list_is_kept(self):  # AC-W3-SP-03
        for mode in ("ux", "tech", "competitor", "impact", "spike"):
            self.assertRegex(self.body, rf"(?m)^- \*\*{mode}\*\* - ")
        self.assertIn("five modes", self.fm["description"])

    def test_researcher_still_has_no_omit_flag(self):
        self.assertNotIn("omitClaudeMd", self.fm)


class DispatchersRouteToTheSpikeAgent(unittest.TestCase):  # AC-W3-SP-03
    """Every engine and skill that dispatches a spike names researcher-spike, not researcher."""

    SOURCES = ("commands", "graphs", "skills")

    def texts(self):
        for top in self.SOURCES:
            for path in sorted((ROOT / top).rglob("*.md")):
                yield path, re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))

    def test_no_dispatcher_sends_a_spike_to_researcher(self):
        stale = re.compile(r"`researcher`[^.]{0,30}\bspike\b")
        for path, text in self.texts():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(stale.search(text))

    def test_prior_art_dispatches_the_spike_agent_with_its_brief(self):
        text = dict(self.texts())[ROOT / "skills" / "process" / "prior-art" / "SKILL.md"]
        (sentence,) = [s for s in text.split(". ") if "researcher-spike" in s]
        self.assertIn("`graph-engineering:researcher-spike`", sentence)
        for part in ("profile path", "REQUIRED skills", "rule packs", "project invariants"):
            self.assertIn(part, text)


class SearchQuota(unittest.TestCase):
    """WebSearch draws on one account quota shared by every agent; an empty quota is said, not hidden."""

    def test_both_web_agents_budget_the_shared_search_quota(self):
        for path in (RESEARCHER, SPIKE):
            text = " ".join(path.read_text(encoding="utf-8").split())
            for needle in ("WebSearch quota", "shared", "WebFetch on a known primary URL", "not retried",
                           "`[INFERRED]`", "status line"):
                with self.subTest(agent=path.stem, needle=needle):
                    self.assertIn(needle, text)
            self.assertNotIn("first line of the report", text)

    def test_researcher_quota_rule_is_outside_the_fan_out_leaf_block(self):
        text = RESEARCHER.read_text(encoding="utf-8")
        leaf = text.index("## Research leaf")
        after_leaf = text.index("\n## ", leaf + 1)
        self.assertIn("WebSearch quota", text[:leaf] + text[after_leaf:])
        self.assertNotIn("WebSearch quota", text[leaf:after_leaf])


if __name__ == "__main__":
    unittest.main()
