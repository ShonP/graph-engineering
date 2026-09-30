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
PLANNER_NODES = {"goal", "plan", "report"}


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
        for path in [ENGINE, *GRAPHS.values()]:
            with self.subTest(path=path.name):
                self.assertNotIn(chr(0x2014), path.read_text())


class EngineDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = ENGINE.read_text()
        cls.steps = steps(cls.text)

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
