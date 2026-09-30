"""graph-control render: Mermaid playbooks generated from graphs/*.md, and the drift check.

The fixture graphs below are SYNTHETIC (invented node names and agents); the
drift test at the bottom runs against this repo's real graphs/ and docs/.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli
from graph_control.common import Invalid
from graph_control.render import OUTPUT, render

ROOT = Path(__file__).resolve().parents[2]

ALPHA = """# alpha

Prose between nodes is ignored, like `when: prose` in a sentence.

## node: intake
agent: engine
gate: no
next: research-ux, plan

## node: research-ux
agent: researcher
when: ui
gate: no
next: plan

## node: plan
agent: plan "lead"
gate: yes
next: END
"""

BETA = """## node: only
agent: qa
gate: no
next: END
"""

ALPHA_FLOWCHART = """```mermaid
flowchart LR
  intake["intake (engine)"]
  research-ux["research-ux (researcher)"]
  plan{{"plan (plan #quot;lead#quot;)"}}
  intake -->|"ui"| research-ux
  intake --> plan
  research-ux --> plan
```"""


def write_graphs(root: Path, graphs: dict[str, str]) -> None:
    (root / "graphs").mkdir(parents=True, exist_ok=True)
    for name, text in graphs.items():
        (root / "graphs" / name).write_text(text)


def invoke(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["render", *argv])
    return code, out.getvalue()


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_graphs(self.root, {"beta.md": BETA, "alpha.md": ALPHA})

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_flowchart_per_graph_sorted_by_file_name(self):
        text = render(self.root)
        self.assertEqual(text.count("flowchart LR"), 2)
        self.assertLess(text.index("## [alpha](../graphs/alpha.md)"), text.index("## [beta](../graphs/beta.md)"))
        self.assertTrue(text.startswith("# Playbooks\n"))
        self.assertTrue(text.endswith("```\n"))

    def test_flowchart_is_exact(self):
        self.assertIn(ALPHA_FLOWCHART, render(self.root))

    def test_gate_is_hexagon_and_when_labels_only_edges_into_conditional_node(self):
        text = render(self.root)
        self.assertIn('plan{{"plan', text)
        self.assertIn('intake["intake', text)
        self.assertEqual(text.count('-->|"ui"|'), 1)
        self.assertNotIn("END", text.split("```mermaid", 1)[1])

    def test_two_runs_are_byte_equal(self):
        self.assertEqual(render(self.root).encode(), render(self.root).encode())

    def test_graph_rules_are_preflights(self):
        write_graphs(self.root, {"gamma.md": "## node: a\nagent: qa\ngate: maybe\nnext: END\n"})
        with self.assertRaisesRegex(Invalid, "invalid gate"):
            render(self.root)

    def test_duplicate_when_is_rejected(self):
        write_graphs(self.root, {"gamma.md": "## node: a\nagent: qa\nwhen: ui\nwhen: api\ngate: no\nnext: END\n"})
        with self.assertRaisesRegex(Invalid, "duplicate graph field: when"):
            render(self.root)

    def test_node_names_mermaid_cannot_parse_are_rejected(self):
        for name in ("end", "style", "class-review", "graph-a", "fix--loop"):
            with self.subTest(name=name):
                write_graphs(self.root, {"gamma.md": f"## node: {name}\nagent: qa\ngate: no\nnext: END\n"})
                with self.assertRaisesRegex(Invalid, "Mermaid node id"):
                    render(self.root)

    def test_no_graphs_is_blocked(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesRegex(Invalid, "no graphs"):
                render(Path(empty))


class RenderCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_graphs(self.root, {"alpha.md": ALPHA})

    def tearDown(self):
        self.tmp.cleanup()

    def test_check_blocks_until_write_then_passes(self):
        code, out = invoke("--root", str(self.root), "--check")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["status"], "BLOCKED")
        self.assertEqual(invoke("--root", str(self.root), "--write")[0], 0)
        self.assertEqual((self.root / OUTPUT).read_bytes(), render(self.root).encode())
        code, out = invoke("--root", str(self.root), "--check")
        self.assertEqual((code, json.loads(out)["status"]), (0, "PASS"))

    def test_check_blocks_on_drift(self):
        invoke("--root", str(self.root), "--write")
        write_graphs(self.root, {"alpha.md": ALPHA.replace("agent: engine", "agent: planner")})
        code, out = invoke("--root", str(self.root), "--check")
        self.assertEqual(code, 1)
        self.assertIn("render --write", json.loads(out)["reason"])

    def test_no_flag_prints_the_document(self):
        code, out = invoke("--root", str(self.root))
        self.assertEqual((code, out), (0, render(self.root)))
        self.assertFalse((self.root / OUTPUT).exists())

    def test_write_and_check_are_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            invoke("--root", str(self.root), "--write", "--check")


class RepoDriftTests(unittest.TestCase):
    def test_docs_playbooks_matches_graphs(self):
        code, out = invoke("--check")
        self.assertEqual(code, 0, out)

    def test_no_committed_playbook_image(self):
        self.assertEqual(list((ROOT / "docs" / "img").glob("playbook.*")), [])


if __name__ == "__main__":
    unittest.main()
