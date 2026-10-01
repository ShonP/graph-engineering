"""Contract checks for the intake router, the quick playbook and the gate text.

The engine is prose, so these tests pin the load-bearing rules by the tokens a
reader (and a grep) keys on, and parse graphs/quick.md with the same reader
preflight uses. Case ids are the wave 2 router acceptance rows (AC-W2-RT-*).
"""
import re
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.preflight import read_graph
from test_playbooks import ENGINE, ENGINE_LANES, engine_text, steps

ROOT = Path(__file__).resolve().parents[2]
QUICK = ROOT / "graphs" / "quick.md"


def lane_block(step, lane):
    """The bullet that defines one lane in step 1: `- **<lane>** ...` to the next bullet."""
    match = re.search(rf"^\s*- \*\*{lane}\*\*(.*?)(?=^\s*- \*\*|^\s*\*\*|\Z)", step, flags=re.M | re.S)
    return match.group(1) if match else ""


class RouterTests(unittest.TestCase):
    """AC-W2-RT-01: the lanes, the risk floor, the argument hint, the file budget."""

    @classmethod
    def setUpClass(cls):
        cls.text = ENGINE.read_text()
        cls.steps = steps(cls.text)
        cls.router = cls.steps[1]
        cls.lanes = ENGINE_LANES.read_text()

    def lane(self, name):
        """A lane's router bullet plus its detail in docs/engine/lanes.md, when it has any."""
        return lane_block(self.router, name) + lane_block(self.lanes, name)

    def test_file_stays_within_budget(self):
        self.assertLessEqual(len(self.text.splitlines()), 250)

    def test_control_plane_row_always_applies(self):
        for token in ("`agent-control`", "`.claude/**`", "`CLAUDE.md`", "`instructionPaths`"):
            self.assertIn(token, self.router)

    def test_false_gate_claim_is_gone(self):
        self.assertNotIn("wrong pick costs one gate", self.text)

    def test_argument_hint_names_lanes(self):
        hint = re.search(r"^argument-hint: (.*)$", self.text, flags=re.M).group(1)
        self.assertIn("--lane answer|direct|quick|full", hint)
        self.assertIn("--graph", hint)

    def test_every_lane_is_defined(self):
        for lane in ("answer", "direct", "quick", "full", "spike"):
            with self.subTest(lane=lane):
                self.assertTrue(lane_block(self.router, lane).strip(), f"no bullet for {lane}")

    def test_size_and_risk_pick_the_lane(self):
        self.assertIn("size and risk", self.router)
        self.assertIn("only picks the graph", self.router)

    def test_answer_lane_looks_up_current_state(self):
        answer = lane_block(self.router, "answer")
        for token in ("no run dir", "WebFetch", "researcher", "never memory"):
            self.assertIn(token, answer)

    def test_direct_lane(self):
        direct = self.lane("direct")
        for token in ("at most 2 files", "no `run.json`", "exactly one `implementer-simple`",
                      "non-code text", "`ESCALATE`", "past 2 files", "risk row",
                      "ux-evidence", "Bruno", "reads the diff", "`.graph/ledger.md`"):
            self.assertIn(token, direct)
        self.assertIn("- <UTC> direct: <goal> | files | <test command>: exit=<n> | "
                      "evidence: <path> | reviewer: none|<risk row>", direct)

    def test_direct_lane_lands_alone_only_on_a_class_none_diff(self):
        """An owner's --lane direct over a risk row never skips the owner merge (owner_classes invariant)."""
        direct = self.lane("direct")
        for token in ("graph-control depth --root <worktree> --base <base> --profile <profile>",
                      "`risk_rows: []`", "`gates.auto_classes` holds `none`", "any matched row",
                      "waits for the owner", "`gates.owner_classes`", "`agent-control`",
                      "<plugin-root>/docs/engine/land.md"):
            self.assertIn(token, direct)
        self.assertNotIn("only when `gates.auto_classes` holds `none` and the verification is green", direct)

    def test_quick_and_full_lanes_name_their_graphs(self):
        quick = lane_block(self.router, "quick")
        self.assertIn("at most 5 files", quick)
        self.assertIn("`graphs/quick.md`", quick)
        full = lane_block(self.router, "full")
        for graph in ("`graphs/feature.md`", "`bug.md`", "`infra.md`"):
            self.assertIn(graph, full)

    def test_triage_keeps_the_playbook_definitions(self):
        for name in ("bug", "infra", "feature"):
            self.assertRegex(self.router, rf"- \*\*{name}\*\* - ")

    def test_spike_and_research_have_no_run_dir(self):
        spike = lane_block(self.router, "spike")
        self.assertIn("`spike` mode", spike)
        self.assertIn("`graph-engineering:researcher-spike`", spike)
        self.assertNotIn("one `researcher` dispatch", spike)
        for part in ("profile path", "REQUIRED skills", "rule packs", "project invariants"):
            self.assertIn(part, spike)
        self.assertIn("`<docsPath>/research/<UTC date>-spike-<slug>.md`", spike)
        self.assertIn("`<docsPath>/research/<UTC date>-<slug>.md`", lane_block(self.router, "research"))
        self.assertNotIn(".graph/research/<slug>.md", self.router)
        self.assertIn("exempt from `run.json` controls", self.router)

    def test_risk_rows_force_quick(self):
        for token in ("`risk:`", "keyword", "path glob", "at least `quick`"):
            self.assertIn(token, self.router)

    def test_multi_goal_split_and_no_silent_deferral(self):
        self.assertIn("parallel runs", self.router)
        self.assertIn("nothing is deferred silently", self.router.lower())

    def test_run_it_verification_replaces_the_gate_claim(self):
        self.assertIn("run-it verification", self.router)


class GateTests(unittest.TestCase):
    """AC-W2-RT-03 and AC-W2-RT-04: auto-merge by class, decision cards."""

    @classmethod
    def setUpClass(cls):
        cls.step = steps(engine_text())[5]

    def test_control_plane_always_waits_for_the_owner(self):
        for token in ("`agent-control`", "even under `--auto-merge`"):
            self.assertIn(token, self.step)

    def test_plan_gate_always_stops(self):
        self.assertIn("`gates.plan` and `gates.merge` take only `owner`", self.step)

    def test_decision_card_format(self):
        self.assertIn(".graph/<run>/decisions.md", self.step)
        self.assertIn("- [ ] D<n> <what> | why owner: <..> | default: <..> | cost of waiting: <..> | "
                      "reversible: yes|no | meanwhile: <..> | redo if other: <..>", self.step)
        self.assertIn("(default applied)", self.step)
        self.assertIn("park only that leg", self.step)

    def test_owner_context_is_lazy(self):
        self.assertIn("ownerAccess: <path>", self.step)
        self.assertIn("lazily", self.step)

    def test_ask_first_list(self):
        for token in ("spend", "public posting", "deletion", "production writes", "destructive",
                      "credentials", "first publish", "real people"):
            self.assertIn(token, self.step)

    def test_auto_merge_predicate(self):
        for token in ("`gates.owner_classes`", "`gates.auto_classes`", "`none`",
                      "graph-control depth --root <run worktree> --base <run base> --profile <profile>"
                      " --plan <run>/plan.json", "`outside-the-run`",
                      "risk_rows",
                      "graph-control findings <run>/findings.json <run>/qa-findings.json --counts",
                      "blocking 0 and important 0", "absent file is BLOCKED",
                      "full PASS", "verify", "`[]`", "`--auto-merge`"):
            self.assertIn(token, self.step)

    def test_push_notifications_only_on_transitions(self):
        for token in ("NEEDS YOU", "first 429", "already happens"):
            self.assertIn(token, self.step)


class IntegrationAndReplyTests(unittest.TestCase):
    """AC-W2-RT-04 (integration) and the step 10 reply contract."""

    @classmethod
    def setUpClass(cls):
        cls.steps = steps(engine_text())

    def test_integration_modes(self):
        step = self.steps[9]
        for token in ("`integration: pr | push-main`", "rebase on origin/<default>",
                      "HEAD:<default>", "gh run watch <id> --exit-status", "run_in_background",
                      "decision card", "never an automatic revert", "green before merge"):
            self.assertIn(token, step)

    def test_reply_contract(self):
        step = self.steps[10]
        for token in ("at most 5 lines", "plain words", "owner's choices", "one recommended action",
                      "what I did", "what I need from you", "SHAs", ".graph/<run>/run-report.md",
                      "durable repo path"):
            self.assertIn(token, step)


class QuickGraphTests(unittest.TestCase):
    """AC-W2-RT-02: graphs/quick.md parses and carries the four capability nodes."""

    @classmethod
    def setUpClass(cls):
        cls.text = QUICK.read_text()
        cls.nodes = read_graph(QUICK)

    def test_capability_nodes_and_roles(self):
        roles = {"plan": "planner", "implement": "implementer", "review": "reviewer", "qa": "qa"}
        for node, agent in roles.items():
            with self.subTest(node=node):
                self.assertEqual(self.nodes[node]["agent"], agent)

    def test_flow(self):
        n = self.nodes
        self.assertEqual(n["intake"]["agent"], "engine")
        self.assertEqual({x.strip() for x in n["intake"]["next"].split(",")}, {"impact", "design"})
        self.assertEqual(n["impact"]["agent"], "researcher")
        self.assertEqual(n["design"]["agent"], "ux-designer")
        self.assertEqual(n["plan"]["gate"], "yes")
        self.assertEqual({x.strip() for x in n["implement"]["next"].split(",")}, {"review", "qa"})
        self.assertEqual(n["merge"]["agent"], "engine")
        self.assertEqual(n["merge"]["gate"], "yes")
        self.assertEqual(n["post-deploy"]["agent"], "qa")
        self.assertEqual(n["retro"]["agent"], "retro")
        self.assertEqual(n["retro"]["next"], "END")

    def test_only_plan_gates_before_code(self):
        gated = {name for name, fields in self.nodes.items() if fields["gate"] == "yes"}
        self.assertEqual(gated, {"plan", "merge"})

    def test_text_fields(self):
        self.assertIn("mode: impact", self.text)
        self.assertIn("when: ui", self.text)
        self.assertIn("skills: [post-deploy-verification]", self.text)
        self.assertIn("`ui: yes|no - <reason>`", self.text)
        self.assertNotIn(chr(0x2014), self.text)


if __name__ == "__main__":
    unittest.main()
