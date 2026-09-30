"""Contract checks for the shipped playbooks and the engine's dispatch rules.

The engine is prose, so these tests pin the load-bearing rules by the tokens a
reader (and a grep) keys on, and parse every shipped graph with the same
reader preflight uses.
"""
import re
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.preflight import read_graph

ROOT = Path(__file__).resolve().parents[2]
GRAPHS = {name: ROOT / "graphs" / f"{name}.md" for name in ("feature", "bug", "infra")}
ENGINE = ROOT / "commands" / "graph-ship.md"
ENGINE_RUN = ROOT / "docs" / "engine" / "run.md"
ENGINE_LAND = ROOT / "docs" / "engine" / "land.md"
ENGINE_LANES = ROOT / "docs" / "engine" / "lanes.md"
ENGINE_PARTS = (ENGINE, ENGINE_RUN, ENGINE_LAND, ENGINE_LANES)
ENGINE_BYTES = 8000
PLANNER_NODES = {"goal", "plan", "report"}


def engine_text():
    """graph-ship.md plus the references it Reads only when a lane needs them: the whole engine."""
    return "\n".join(path.read_text() for path in ENGINE_PARTS)


def steps(text):
    """Split graph-ship.md into its numbered steps: {number: body}."""
    parts = re.split(r"^(\d+)\. \*\*", text, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def node_block(text, name):
    match = re.search(rf"^## node: {name}\n(.*?)(?=^## node: |\Z)", text, flags=re.M | re.S)
    return match.group(1)


class PlaybookTests(unittest.TestCase):
    def test_every_graph_parses(self):
        for name, path in GRAPHS.items():
            with self.subTest(graph=name):
                self.assertIn("merge", read_graph(path))

    def test_planner_owns_only_goal_plan_report(self):
        for name, path in GRAPHS.items():
            nodes = read_graph(path)
            planner = {node for node, fields in nodes.items() if fields["agent"] == "planner"}
            with self.subTest(graph=name):
                self.assertLessEqual(planner, PLANNER_NODES)
                self.assertEqual(nodes["merge"]["agent"], "engine")
                self.assertEqual(nodes["retro"]["agent"], "retro")

    def test_retro_node_does_not_route_the_preloaded_skill(self):
        for name, path in GRAPHS.items():
            with self.subTest(graph=name):
                self.assertNotIn("skills:", node_block(path.read_text(), "retro"))

    def test_no_em_dashes(self):
        for path in [*ENGINE_PARTS, *GRAPHS.values()]:
            with self.subTest(path=path.name):
                self.assertNotIn(chr(0x2014), path.read_text())


class EngineSplitTests(unittest.TestCase):
    """graph-ship.md loads on every /graph-ship; only the router lives there, the rest loads by lane."""

    def test_command_stays_within_its_byte_budget(self):
        self.assertLessEqual(len(ENGINE.read_bytes()), ENGINE_BYTES)

    def test_command_holds_only_the_router(self):
        self.assertEqual(sorted(steps(ENGINE.read_text())), [1])
        self.assertEqual(sorted(steps(ENGINE_RUN.read_text())), [2, 3, 4, 5, 6, 7, 8, 10])
        self.assertEqual(sorted(steps(ENGINE_LAND.read_text())), [9])
        self.assertEqual(steps(ENGINE_LANES.read_text()), {})

    def test_router_names_what_each_lane_reads(self):
        router = steps(ENGINE.read_text())[1]
        for token in ("<plugin-root>/docs/engine/run.md", "<plugin-root>/docs/engine/land.md",
                      "<plugin-root>/docs/engine/lanes.md", "once per run"):
            self.assertIn(token, router)

    def test_every_reference_says_where_it_belongs(self):
        for path in ENGINE_PARTS[1:]:
            with self.subTest(path=path.name):
                self.assertIn("/graph-ship", path.read_text().splitlines()[0])


class EngineDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = engine_text()
        cls.steps = steps(cls.text)

    def test_review_depth_picks_the_review_leg(self):
        step = self.steps[4]
        for token in ("graph-control depth --root <run worktree> --base <run base> --profile <profile>",
                      "`lint`", "no reviewer", "`single`", "`panel`", "review receipt", "`findings.json`",
                      "lint.argv", "agent-control"):
            self.assertIn(token, step)

    def test_policy_roles_is_the_single_model_source(self):
        step = self.steps[4]
        self.assertIn("`policy.roles`", step)
        self.assertIn("single source", step)
        self.assertIn("policy-override: <reason>", step)
        self.assertNotIn("role-tier mapping", self.text)
        self.assertIn("never substitute a cheaper reviewer", step.lower())

    def test_dispatch_shape(self):
        step = self.steps[4]
        self.assertIn("five parts", step)
        self.assertIn(".graph/<run>/tasks/<n>.md", step)
        self.assertIn("graph-engineering:<name>", step)
        self.assertIn("`<first 8 chars of run id>:<node>`", step)
        self.assertIn("Never paste history", step)

    def test_delegation_thresholds(self):
        step = self.steps[4]
        for token in ("~150k", "~100k", "~15 minutes", "~10+ tool calls", "scoped reviewer"):
            self.assertIn(token, step)

    def test_engine_nodes_are_not_dispatched(self):
        self.assertIn("`agent: engine`", self.steps[4])
        merge = self.steps[5]
        for token in ("git diff --stat", "## Follow-ups", "parked", "no planner dispatch"):
            self.assertIn(token, merge)

    def test_fix_rounds_are_fresh(self):
        step = self.steps[7]
        for token in ("FRESH dispatch", "needs_author_context: true", "Round 3",
                      "small task", "standard task", "fresh diagnosis",
                      "git diff <last reviewed head>..HEAD", "validate-attempts"):
            self.assertIn(token, step)

    def test_return_contract(self):
        step = self.steps[8]
        for token in ("1,500 tokens", "verdict line", "never relays"):
            self.assertIn(token, step)

    def test_retro_fast_path(self):
        step = self.steps[10]
        self.assertIn("No leaks: <n> review rounds, <m> qa rows verified", step)
        for token in ("zero blocking or important", "FAILED", "NEEDS_SETUP", "BLOCKED",
                      "post-deploy", "`retro` agent"):
            self.assertIn(token, step)


if __name__ == "__main__":
    unittest.main()
