"""render: Mermaid playbooks in docs/playbooks.md, generated from graphs/*.md.

No flag prints the document; `--write` writes it; `--check` is the drift gate:
BLOCKED (exit 1) when the file on disk differs from what the graphs render.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from . import Output

NAME = "render"
HELP = "Mermaid playbooks from graphs/*.md: print, --write docs/playbooks.md, or --check for drift"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, help="checkout holding graphs/ and docs/ (default: this plugin)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write docs/playbooks.md")
    mode.add_argument("--check", action="store_true", help="BLOCKED when docs/playbooks.md differs from the graphs")


def run(args: Namespace) -> dict[str, Any] | Output:
    from ..common import require
    from ..render import OUTPUT, PLUGIN_ROOT, render  # imports PyYAML through preflight

    root = PLUGIN_ROOT if args.root is None else args.root
    data, target = render(root).encode(), root / OUTPUT
    if args.check:
        require(target.is_file() and target.read_bytes() == data,
                f"{OUTPUT} differs from graphs/*.md; run graph-control render --write")
        return {"checked": str(OUTPUT)}
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"written": str(OUTPUT)}
    return Output(data.decode())
