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
import shutil
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


def _variants(name: str, old: str, new: str) -> list[tuple[str, str]]:
    plain = (old, new)
    if name != "plan.json":
        return [plain]
    escaped = (json.dumps(old)[1:-1], json.dumps(new)[1:-1])
    return [plain] if escaped == plain else [escaped, plain]


def _hits(name: str, body: str, old: str, new: str) -> list[str]:
    needles = [needle for needle, _ in _variants(name, old, new)]
    return [f"{name}:{number}: {line.strip()[:LINE_LIMIT]}"
            for number, line in enumerate(body.splitlines(), 1) if any(needle in line for needle in needles)]


def _rewrite(name: str, body: str, old: str, new: str) -> str:
    for needle, replacement in _variants(name, old, new):
        body = body.replace(needle, replacement)
    return body


def _stage(path: Path, body: str) -> str:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copymode(path, temporary)
    except BaseException:
        os.unlink(temporary)
        raise
    return temporary


def _replace_all(run_dir: Path, rewritten: dict[str, str], originals: dict[str, str]) -> None:
    staged: dict[str, str] = {}
    replaced: list[str] = []
    try:
        for name, body in rewritten.items():
            staged[name] = _stage(run_dir / name, body)
        for name, temporary in staged.items():
            os.replace(temporary, run_dir / name)
            replaced.append(name)
    except BaseException:
        for name in replaced:
            os.replace(_stage(run_dir / name, originals[name]), run_dir / name)
        raise
    finally:
        for temporary in staged.values():
            if os.path.exists(temporary):
                os.unlink(temporary)


def _write(run_dir: Path, texts: dict[str, str], old: str, new: str) -> dict[str, Any]:
    from ..common import Invalid, require
    from ..state import locked

    candidates = {name: _rewrite(name, body, old, new) for name, body in texts.items()}
    rewritten = {name: body for name, body in candidates.items() if body != texts[name]}
    if "plan.json" in rewritten:
        try:
            json.loads(rewritten["plan.json"])
        except json.JSONDecodeError as error:
            raise Invalid(f"plan.json would no longer parse after the rewrite: {error}") from None
    left = [hit for name, body in rewritten.items() for hit in _hits(name, body, old, new)]
    require(not left, f"the rewrite would leave the old literal in place: {left}")
    _replace_all(run_dir, rewritten, texts)
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
    hits = [hit for name, body in texts.items() for hit in _hits(name, body, old, new)]
    if not hits:
        return {"hits": 0}
    return Output("\n".join([*hits, f"decision apply: {len(hits)} stale copies of the old literal"]) + "\n", 1)
