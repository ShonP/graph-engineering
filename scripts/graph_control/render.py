"""Mermaid playbooks: one `flowchart LR` per graphs/*.md, rendered deterministically.

Graphs are read by preflight.read_graph, so render accepts exactly what the
engine accepts; `when:` is read here with the same one-per-node rule. A gate
node is a hexagon; an edge into a conditional node carries its `when:` label.
`END` is the absence of an outgoing edge, so it draws nothing.
"""

import re
from pathlib import Path

from .common import require
from .preflight import read_graph

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("docs/playbooks.md")
HEADER = """# Playbooks

Generated from `graphs/*.md` by `graph-control render --write`; `render --check` fails when this file drifts, so edit the graphs, not this file. A hexagon is a gate node (`gate: yes`); an edge label is the `when:` condition of the node it enters.
"""
# Lowercase ids Mermaid 11.17.2 fails to parse, alone or before a hyphen (spiked 2026-10-01).
MERMAID_KEYWORDS = frozenset({"call", "class", "click", "end", "flowchart", "graph", "href",
                              "interpolate", "style", "subgraph"})


def read_conditions(path: Path) -> dict[str, str]:
    """`when:` per node, under the `## node:` headings read_graph uses."""
    conditions: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text().splitlines():
        heading = re.fullmatch(r"## node: ([a-z][a-z0-9_-]*)", line.strip())
        if heading:
            current = heading.group(1)
            continue
        field = re.fullmatch(r"when:\s*(.+)", line.strip())
        if current is not None and field:
            require(current not in conditions, "duplicate graph field: when")
            conditions[current] = field.group(1)
    return conditions


def node_id(name: str) -> str:
    require("--" not in name and name.split("-")[0] not in MERMAID_KEYWORDS,
            f"{name}: not usable as a Mermaid node id; rename the node")
    return name


def quoted(text: str) -> str:
    return '"' + text.replace('"', "#quot;") + '"'


def flowchart(path: Path) -> str:
    nodes, conditions = read_graph(path), read_conditions(path)
    lines = ["```mermaid", "flowchart LR"]
    for name, fields in nodes.items():
        label = quoted(f"{name} ({fields['agent']})")
        lines.append(f"  {node_id(name)}{{{{{label}}}}}" if fields["gate"] == "yes" else f"  {node_id(name)}[{label}]")
    for name, fields in nodes.items():
        for target in (item.strip() for item in fields["next"].split(",")):
            if target == "END":
                continue
            arrow = f"-->|{quoted(conditions[target])}|" if target in conditions else "-->"
            lines.append(f"  {name} {arrow} {target}")
    return "\n".join([*lines, "```"])


def render(root: Path) -> str:
    """The whole docs/playbooks.md: the header, then one section per graph sorted by file name."""
    paths = sorted((root / "graphs").glob("*.md"), key=lambda path: path.name)
    require(bool(paths), f"no graphs/*.md under {root}")
    sections = [f"## [{path.stem}](../graphs/{path.name})\n\n{flowchart(path)}\n" for path in paths]
    return "\n".join([HEADER, *sections])
