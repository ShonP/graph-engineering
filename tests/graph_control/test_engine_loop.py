"""Contract checks for the wave 4 engine loop: the no-code lanes, graphs/research.md,
in-run defect classes, the post-deploy signal re-check and the merge digest.

The engine is prose, so these tests pin the load-bearing rules by the tokens a
reader (and a grep) keys on, and parse graphs/research.md with the same reader
preflight uses. Case ids are the wave 4 acceptance rows (AC-W4-EL-*). The
plugin is generic: nothing here may name one consumer's stack, app or vendor.
"""
import re
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.preflight import read_graph
from test_playbooks import ENGINE, ENGINE_LANES, ENGINE_PARTS, engine_text, node_block, steps
from test_router import lane_block

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "graphs" / "research.md"
CONSUMER_WORDS = ("pnpm", "xcodegen", "xcodebuild", "supabase", "sentry",
                  "ga4", "clarity", "doppler", "hormozi", "fable", "haiku")


def header(text):
    """The prose above the first node: the lane detail read only when the lane runs."""
    return text.split("## node: ", 1)[0]


def flat(text):
    """Wrapped prose as one line, so a token that spans a line break still matches."""
    return re.sub(r"\s+", " ", text)


def playbook_bullet(text, label):
    return flat(text.split(f"- **{label}**", 1)[1].split("\n- **", 1)[0])


def leaf_bullet(label):
    return playbook_bullet((ROOT / "agents" / "researcher.md").read_text(), label)


class Tokens(unittest.TestCase):
    def assert_tokens(self, body, tokens):
        for token in tokens:
            with self.subTest(token=token):
                self.assertIn(token, body)


class RouterLaneTests(Tokens):
    """AC-W4-EL-01: investigate, research and product lanes, the spike route, the budget."""

    @classmethod
    def setUpClass(cls):
        cls.text = ENGINE.read_text()
        cls.router = steps(cls.text)[1]

    def test_file_stays_within_budget(self):
        self.assertLessEqual(len(self.text.splitlines()), 250)

    def test_argument_hint_names_the_new_lanes_and_graph(self):
        hint = re.search(r"^argument-hint: (.*)$", self.text, flags=re.M).group(1)
        self.assertIn("--lane answer|direct|quick|full|investigate|research|product", hint)
        self.assertIn("--graph feature|bug|infra|quick|research", hint)

    def test_every_new_lane_has_a_bullet(self):
        for lane in ("investigate", "research", "product"):
            with self.subTest(lane=lane):
                self.assertTrue(lane_block(self.router, lane).strip(), f"no bullet for {lane}")

    def test_interim_research_rule_is_gone(self):
        self.assertNotIn("until the research playbook lands", self.text)

    def test_research_lane(self):
        research = lane_block(self.router, "research")
        self.assert_tokens(research, ("`graphs/research.md`", "exempt from `run.json` controls",
                                      "single lookup", "`answer`", "`quick`", "`standard`", "`deep`"))

    def test_spike_route(self):
        spike = lane_block(self.router, "spike")
        self.assert_tokens(spike, ("`graph-engineering:researcher-spike`", "no run dir"))

    def test_investigate_lane(self):
        lane = lane_block(self.router, "investigate") + lane_block(ENGINE_LANES.read_text(), "investigate")
        self.assert_tokens(lane, (
            "`researcher`", "`signals` mode", "fresh context", "`pulse.command`", "NEEDS_SETUP",
            "one-page digest", "aggregates", "pseudonymised ids", "only when the owner asks",
            "session_usage.py --medians", "asks the owner once", "already ranked",
            "`direct`", "`quick`", "`bug`", "run-it verification", "qa smoke test",
            "signal cleared in production", "fix all", "deferral"))

    def test_product_lane(self):
        lane = lane_block(self.router, "product")
        self.assert_tokens(lane, ("`graphs/research.md`", "product preset", "go / kill / clarify",
                                  "`intent: defined`", "`feature`"))

    def test_research_playbook_gates_at_report(self):
        self.assertIn("`research` writes no code and gates at `report`", self.router)


class ResearchGraphTests(Tokens):
    """AC-W4-EL-02: graphs/research.md parses and carries presets, firewall and the report rules."""

    @classmethod
    def setUpClass(cls):
        cls.text = RESEARCH.read_text()
        cls.table = header(cls.text)
        cls.head = flat(cls.table)
        cls.nodes = read_graph(RESEARCH)

    def test_nodes_and_agents(self):
        self.assertEqual(list(self.nodes), ["brief", "research", "verify", "report"])
        agents = {name: fields["agent"] for name, fields in self.nodes.items()}
        self.assertEqual(agents, {"brief": "engine", "research": "researcher",
                                  "verify": "researcher", "report": "engine"})

    def test_flow_and_gate(self):
        n = self.nodes
        self.assertEqual(n["brief"]["next"], "research")
        self.assertEqual(n["research"]["next"], "verify")
        self.assertEqual(n["verify"]["next"], "report")
        self.assertEqual(n["report"]["next"], "END")
        gated = {name for name, fields in n.items() if fields["gate"] == "yes"}
        self.assertEqual(gated, {"report"})

    def test_verify_is_the_deep_refuter(self):
        block = node_block(self.text, "verify")
        self.assert_tokens(block, ("when: deep", "one refuter", "cap 1"))
        self.assertIn("`deep: yes|no - <reason>`", node_block(self.text, "brief"))

    def test_brief_is_written_by_the_engine_without_dispatch(self):
        block = node_block(self.text, "brief")
        self.assert_tokens(block, ("decision", "dimensions", "output format", "budget",
                                   "preferences probe", "no dispatch"))

    def test_presets(self):
        for preset, leaves in (("quick", 1), ("standard", 3), ("deep", 6)):
            with self.subTest(preset=preset):
                self.assertRegex(self.table, rf"(?m)^\| `{preset}` \| {leaves} \|")

    def test_fan_out_budget_and_firewall(self):
        self.assert_tokens(self.head, ("depth 1", "ONE message", "10-20", "`maxTurns`",
                                       "Firewall", "brief only", "No `run.json`"))

    def test_claims_digest_to_disk(self):
        self.assertIn(".graph/<run>/research/claims.jsonl", flat(self.text))
        leaf = leaf_bullet("Claims to disk.")
        self.assert_tokens(leaf, ("every 5", "`>>`"))
        self.assertRegex(leaf, r'\{"claim": .*"source": .*"pub_date": .*"rung": .*"confidence": [^}]*\}')

    def test_claims_contract_lives_only_in_the_researcher_leaf(self):
        leaf = leaf_bullet("Claims to disk.")
        for token in ("`confidence` is high, medium or low", "every 5 items (sources read)"):
            with self.subTest(token=token):
                self.assertIn(token, leaf)
        self.assertNotRegex(leaf, r"0\.0|1\.0")
        for token in ("pub_date", "confidence", "every 5", "`>>`"):
            with self.subTest(absent=token):
                self.assertNotIn(token, self.head)

    def test_leaf_side_points_at_the_researcher(self):
        for label in ("Budget.", "Firewall.", "Claims to disk."):
            with self.subTest(label=label):
                self.assertIn("`agents/researcher.md`", playbook_bullet(self.table, label))
        for leaf_rule in ("reports `PARTIAL`", "anchor"):
            with self.subTest(absent=leaf_rule):
                self.assertNotIn(leaf_rule, self.head)

    def test_fetch_blocklist(self):
        self.assert_tokens(self.head, ("login-walled", "WebFetch", "linkedin.com", "x.com"))

    def test_report_has_evidence_against_and_unverified_list(self):
        block = node_block(self.text, "report")
        self.assert_tokens(block, ("## Evidence against", "## Unverified", "the spike that settles",
                                   "<docsPath>/research/<UTC date>-<slug>.md",
                                   "<docsPath>/research/<UTC date>-<slug>-concept.md"))
        self.assertNotIn(".graph/research/", block)
        self.assertNotIn(".graph/<run>/concept.md", self.text)

    def test_single_lookup_stays_in_answer(self):
        self.assertIn("single lookup stays in the `answer` lane", self.head)


class ClassesTests(Tokens):
    """AC-W4-EL-03: the in-run defect classes file, appended by the engine."""

    def test_classes_append_rule(self):
        step = steps(engine_text())[7]
        self.assert_tokens(step, (".graph/<run>/classes.md",
                                  "`- <class> | <finding id> | <task> round <n>`",
                                  "blocking or important", "`rule`", "no dispatch",
                                  "every later dispatch in the run", "graph-control findings", "--classes"))

    def test_ac_en_2_round_files_are_per_task(self):
        # Parallel tasks each run their own review rounds; run-global files would overwrite each other.
        step = steps(engine_text())[7]
        self.assert_tokens(step, (".graph/<run>/findings.<task>.json", "`findings.<task>.r<N>.json`",
                                  "that task's first review", "qa rows use `qa` as the task"))
        self.assertNotIn("| round <n>`", step.replace("<task> round <n>`", ""))

    def test_ac_en_2_gates_and_fast_path_count_every_task(self):
        all_steps = steps(engine_text())
        self.assertIn("every task's latest `findings.<task>.json`", all_steps[5])
        self.assertIn("`findings.<task>.r<N>.json`", all_steps[10])
        self.assertIn("an absent file is not zero", all_steps[10])

    def test_ac_en_2_remainder_and_round_ids(self):
        step = steps(engine_text())[4]
        self.assert_tokens(step, ("`<id>b`", "-r<N>"))


class SignalsAndDigestTests(Tokens):
    """AC-W4-EL-04: post-deploy success_signals re-check, the lazy measure, the merge digest."""

    @classmethod
    def setUpClass(cls):
        cls.steps = steps(engine_text())

    def test_post_deploy_rechecks_short_window_signals(self):
        self.assert_tokens(self.steps[9], (
            "`success_signals`", "plan.json", "short-window", ".graph/<run>/post-deploy/baseline.json",
            "`deployedAt`", "python3 <plugin-root>/scripts/measure_signals.py", "SessionStart",
            "next `/graph-ship`", "`not met`", "`.graph/ledger.md`", "suggested bug run"))

    def test_measure_is_triggered_lazily_at_intake(self):
        self.assertIn("scripts/measure_signals.py", self.steps[1])

    def test_merge_exhibit_has_the_digest(self):
        self.assertIn("graph-control digest --root <run worktree> --base <run base> "
                      "--plan <run>/plan.json --profile <profile>", self.steps[5])


class ProductPresetTests(Tokens):
    """AC-W4-EL-05: the slim product preset ends at an owner gate and hands off to feature."""

    @classmethod
    def setUpClass(cls):
        cls.text = RESEARCH.read_text()
        cls.head = flat(header(cls.text))

    def test_intake_and_constraints_probe(self):
        self.assert_tokens(self.head, ("intake.md", "constraints probe", "market", "language",
                                       "audience", "budget", "must-not", "tools already used elsewhere",
                                       "`intent: defined`", "straight to `feature`"))

    def test_fan_out_and_completeness_checklist(self):
        self.assert_tokens(self.head, (
            "`standard`", "reuse first", "completeness checklist", "design system", "auth and session",
            "DX/CI/runner", "QA", "observability", "cost", "skills per technology", "competitor",
            "user-facing surface", "5 leaves", "large"))

    def test_concept_spike_and_gate(self):
        self.assert_tokens(self.head, (
            "ONE `planner` dispatch", "-concept.md`", "`researcher-spike`", "riskiest assumption",
            "go / kill / clarify", "5-line summary", "`skipped (product run <id>)`"))


class GenericTests(unittest.TestCase):
    """AC-W4-EL-05: the plugin is generic; no consumer names, no em dashes."""

    def test_no_consumer_words(self):
        for path in (*ENGINE_PARTS, RESEARCH):
            lowered = path.read_text().lower()
            for word in CONSUMER_WORDS:
                if path in ENGINE_PARTS and word in ("fable", "haiku"):
                    continue  # step 4 names them to forbid them
                with self.subTest(path=path.name, word=word):
                    self.assertIsNone(re.search(rf"\b{word}\b", lowered))

    def test_no_em_dashes(self):
        for path in (*ENGINE_PARTS, RESEARCH):
            with self.subTest(path=path.name):
                self.assertNotIn(chr(0x2014), path.read_text())


if __name__ == "__main__":
    unittest.main()
