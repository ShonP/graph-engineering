"""decision apply: rewrite a changed decision literal in every run artifact that still carries it.

Scans `plan.json`, `plan.md`, `tasks/*.md` and `design/experience.md` under the
run directory for the old literal (plain, case-sensitive substring). Without
`--write` it lists each hit line and exits 1, or passes with `{"hits": 0}`.
With `--write` it computes every rewrite in memory, refuses a `plan.json` that
would no longer parse or any text that would still carry the old literal,
replaces each changed file atomically and appends one ledger line:
`- <UTC ISO ts> decision-apply "<old>" -> "<new>" <n> files`.
"""

import json
import os
import tempfile
from argparse import ArgumentParser, Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import Output

NAME = "decision"
HELP = "apply a changed decision literal to every run artifact that still carries the old one"
LINE_LIMIT = 160


def add_arguments(parser: ArgumentParser) -> None:
    actions = parser.add_subparsers(dest="action", required=True)
    apply = actions.add_parser("apply", help="list or rewrite stale copies of the old literal")
    apply.add_argument("run_dir", type=Path, help="the run directory, .graph/<run>")
    apply.add_argument("--old", required=True, help="the literal the decision replaced")
    apply.add_argument("--new", required=True, help="the literal the decision chose")
    apply.add_argument("--write", action="store_true", help="rewrite the artifacts and append a ledger line")


def _artifacts(run_dir: Path) -> list[Path]:
    named = [run_dir / "plan.json", run_dir / "plan.md", *sorted((run_dir / "tasks").glob("*.md")),
             run_dir / "design" / "experience.md"]
    return [path for path in named if path.is_file()]


def _hits(name: str, body: str, old: str) -> list[str]:
    return [f"{name}:{number}: {line.strip()[:LINE_LIMIT]}"
            for number, line in enumerate(body.splitlines(), 1) if old in line]


def _replace(path: Path, body: str) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write(run_dir: Path, texts: dict[str, str], old: str, new: str) -> dict[str, Any]:
    from ..common import Invalid, require
    from ..state import locked

    rewritten = {name: body.replace(old, new) for name, body in texts.items() if old in body}
    if "plan.json" in rewritten:
        try:
            json.loads(rewritten["plan.json"])
        except json.JSONDecodeError as error:
            raise Invalid(f"plan.json would no longer parse after the rewrite: {error}") from None
    left = [hit for name, body in rewritten.items() for hit in _hits(name, body, old)]
    require(not left, f"the rewrite would leave the old literal in place: {left}")
    for name, body in rewritten.items():
        _replace(run_dir / name, body)
    if rewritten:
        ledger = run_dir / "ledger.md"
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with locked(ledger), ledger.open("a", encoding="utf-8") as stream:
            stream.write(f'- {stamp} decision-apply "{old}" -> "{new}" {len(rewritten)} files\n')
    return {"rewritten": sorted(rewritten), "ledger_lines": 1 if rewritten else 0}


def run(args: Namespace) -> dict[str, Any] | Output:
    from ..common import require

    old, new = args.old, args.new
    require(old not in new, "--old is empty, equal to --new or inside it, so a rewrite could never clear it")
    require(args.run_dir.is_dir(), f"no run directory: {args.run_dir}")
    texts = {path.relative_to(args.run_dir).as_posix(): path.read_text(encoding="utf-8")
             for path in _artifacts(args.run_dir)}
    if args.write:
        return _write(args.run_dir, texts, old, new)
    hits = [hit for name, body in texts.items() for hit in _hits(name, body, old)]
    if not hits:
        return {"hits": 0}
    return Output("\n".join([*hits, f"decision apply: {len(hits)} stale copies of the old literal"]) + "\n", 1)
