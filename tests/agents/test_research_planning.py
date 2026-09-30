"""Golden checks for wave 4: researcher signals and leaf rules, planner concept and
success signals, and the product-spec option sections.

Stdlib only, so it runs with plain `python3 -m unittest discover -s tests/agents`.
Each test names the acceptance row it guards (AC-W4-RP-*). The files are prompts,
so the checks are on the contract phrases and on the example shapes they carry.
"""

import json
import re
import subprocess
import unittest

from test_roster_policy import ROOT, split

RESEARCHER = ROOT / "agents" / "researcher.md"
PLANNER = ROOT / "agents" / "planner.md"
PRODUCT_SPEC = ROOT / "skills" / "process" / "product-spec" / "SKILL.md"

# Consumer and stack names the plugin core must never hard-code.
CONSUMER_WORDS = ("koach", "fitness", "supabase", "swiftui", "nestjs", "apps/")
CLAIM_KEYS = {"claim", "source", "pub_date", "rung", "confidence"}
SIGNAL_KEYS = {"goal", "source", "command", "success_condition", "window_days"}
SIGNAL_SOURCES = {"prometheus", "sentry", "sql-readonly", "command"}
SIGNAL_LINE = "`signal: already logged | instrumentation task`"


def section(body, heading):
    """From a `## heading` line to the next `## ` heading."""
    lines = body.split("\n")
    start = lines.index(heading)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def flat(text):
    return re.sub(r"\s+", " ", text)


def json_examples(text, first_key):
    """Every inline `{...}` object in backticks whose first key is `first_key`."""
    found = re.findall(r"`(\{\"" + first_key + r"\".*?\})`", text)
    return [json.loads(item) for item in found]


class GenericText(unittest.TestCase):
    def assert_generic(self, text, who):
        low = text.lower()
        for word in CONSUMER_WORDS:
            self.assertNotIn(word, low, f"{who}: names {word!r}")
        self.assertNotIn(chr(0x2014), text, f"{who}: em dash")
        self.assertNotIn("fable", low, f"{who}: retired tier")


class ResearcherSignals(GenericText):  # AC-W4-RP-01
    def setUp(self):
        self.fm, self.body = split(RESEARCHER)
        (self.line,) = [ln for ln in self.body.split("\n") if ln.startswith("- **signals** - ")]
        self.text = flat(self.line)

    def test_description_names_the_mode_and_keeps_the_five(self):
        self.assertIn("five modes", self.fm["description"])
        self.assertIn("signals", self.fm["description"])

    def test_runs_pulse_command_verbatim(self):
        for needle in ("`pulse.command`", "exactly as written", "never write a query of your own",
                       "`BLOCKED`"):
            self.assertIn(needle, self.text)

    def test_aggregates_and_pseudonymised_ids_only(self):
        for needle in ("aggregates", "pseudonymised ids", "never a name, email"):
            self.assertIn(needle, self.text)

    def test_named_user_only_on_owner_request(self):
        self.assertRegex(self.text, r"named user only when .*owner asked")

    def test_one_page_digest(self):
        self.assertIn("one-page digest", self.text)
        self.assertIn("60 lines", self.text)
        self.assertIn("the coordinator ranks", self.text)

    def test_generic(self):
        self.assert_generic(self.line, "researcher signals")


class ResearcherLeaf(GenericText):  # AC-W4-RP-02
    def setUp(self):
        self.fm, self.body = split(RESEARCHER)
        self.leaf = section(self.body, "## Research leaf")
        self.text = flat(self.leaf)

    def test_brief_only_firewall(self):
        for needle in ("brief only", "firewall", "other leaves"):
            self.assertIn(needle, self.text.lower())

    def test_per_leaf_budget(self):
        for needle in ("tool budget", "WebSearch", "WebFetch", "`maxTurns`", "`PARTIAL`"):
            self.assertIn(needle, self.text)

    def test_claims_digest_every_five_items_with_five_keys(self):
        self.assertIn("`research/claims.jsonl`", self.text)
        self.assertIn("every 5 items", self.text)
        self.assertIn("append", self.text)
        (example,) = json_examples(self.leaf, "claim")
        self.assertEqual(set(example), CLAIM_KEYS)
        self.assertIn(example["rung"], range(1, 6))
        self.assertIn(example["confidence"], {"high", "medium", "low"})

    def test_report_has_evidence_against_and_unverified(self):
        for needle in ("`## Evidence against`", "`## Unverified`", "spike"):
            self.assertIn(needle, self.text)

    def test_evidence_against_reaches_the_report_section(self):
        report = flat(section(self.body, "## Report"))
        self.assertIn("Evidence against", report)

    def test_modes_are_kept(self):
        for mode in ("ux", "tech", "competitor", "impact", "spike", "signals"):
            self.assertRegex(self.body, rf"(?m)^- \*\*{mode}\*\* - ")

    def test_generic(self):
        self.assert_generic(self.leaf, "researcher leaf")


class PlannerConcept(GenericText):  # AC-W4-RP-03
    def setUp(self):
        self.fm, self.body = split(PLANNER)
        self.text = flat(self.body)

    def test_description_keeps_goal_and_plan_nodes(self):
        self.assertIn("goal and plan nodes", self.fm["description"])
        self.assertIn("product concept", self.fm["description"])

    def test_concept_md_for_the_product_preset(self):
        concept = flat(section(self.body, "## Product concept"))
        for needle in ("`concept.md`", "`product-spec`", "smallest thing", "buy / do nothing",
                       "riskiest assumption", "completeness checklist", SIGNAL_LINE, "go / kill / clarify"):
            self.assertIn(needle, concept)
        self.assertRegex(concept, r"2-3 options")

    def test_success_signals_shape(self):
        for needle in ("`success_signals`", "schema v2", "`success_signals_reason`", "aggregate",
                       "`value <= 0.01`", "`value >= baseline * 1.1 + 5`", "argv", "1-90"):
            self.assertIn(needle, self.text)
        (example,) = json_examples(self.body, "goal")
        self.assertEqual(set(example), SIGNAL_KEYS)
        self.assertIn(example["source"], SIGNAL_SOURCES)
        self.assertIsInstance(example["command"], list)
        self.assertTrue(1 <= example["window_days"] <= 90)
        for source in SIGNAL_SOURCES:
            self.assertIn(f"`{source}`", self.text)

    def test_empty_signals_need_a_reason(self):
        self.assertRegex(self.text, r"`\"success_signals\": \[\]`.*`success_signals_reason`")
        for kind in ("internal", "refactor", "infra"):
            self.assertIn(kind, self.text)

    def test_contract_task_first(self):
        self.assertIn("Contract task first", self.text)
        self.assertRegex(self.text, r"produces a shared contract precedes every task that consumes it")

    def test_brief_size_limits(self):
        for needle in ("`.graph/<run>/tasks/<id>.md`", "300 lines", "35%", "`graph-control validate-briefs`"):
            self.assertIn(needle, self.text)

    def test_quick_lane_one_exhibit(self):
        self.assertRegex(self.text, r"quick.{0,80}one exhibit")

    def test_generic(self):
        self.assert_generic(self.body, "planner")

    def test_stays_small(self):
        self.assertLess(len(PLANNER.read_text(encoding="utf-8").split("\n")), 250)


class ProductSpecSections(GenericText):  # AC-W4-RP-04
    def setUp(self):
        self.text = PRODUCT_SPEC.read_text(encoding="utf-8")
        self.sections = section(self.text, "## Sections")
        self.flat = flat(self.sections)

    def test_new_sections_sit_in_sections(self):
        for heading in ("**Options.**", "**Riskiest assumption.**", "**Completeness checklist.**",
                        "**Signal.**"):
            self.assertIn(heading, self.sections)

    def test_options_always_include_smallest_and_buy_or_nothing(self):
        for needle in ("2-3", "smallest thing", "buy / do nothing"):
            self.assertIn(needle, self.flat)

    def test_riskiest_assumption_is_per_option(self):
        self.assertRegex(self.flat, r"\*\*Riskiest assumption\.\*\* One per option")
        self.assertIn("spike", self.flat)

    def test_checklist_rows_and_statuses(self):
        for needle in ("design system", "auth and session", "CI", "QA", "observability", "cost",
                       "skills per technology", "`covered`", "`gap`", "`n/a`"):
            self.assertIn(needle, self.flat)

    def test_signal_line(self):
        self.assertIn(SIGNAL_LINE, self.flat)

    def test_condition_is_observable(self):
        self.assertIn("`product-discovery: yes`", self.flat)

    def test_generic(self):
        self.assert_generic(self.text, "product-spec")

    def test_frontmatter_check_passes(self):
        done = subprocess.run(["bash", str(ROOT / "scripts" / "check-skill-frontmatter.sh"), str(ROOT)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
