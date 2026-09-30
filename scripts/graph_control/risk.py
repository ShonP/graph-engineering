"""The profile's single risk table: which rows a change matches.

A `risk:` row is {id, paths: [globs], keywords: [strings]}. It matches when any
changed path matches any of its globs, or any keyword occurs literally and
case-sensitively in the added lines (the template's contract: keywords are
spelled the way the code spells them). A row with neither is a placeholder the
repo or the engine fills (`public-copy`, `outside-the-run`); it matches nothing
here. Globs use the dialect the profile template names: wcmatch
GLOBSTAR | BRACE | DOTGLOB against repo-relative paths. Pure: no I/O.

One row is built in and reserved: `agent-control`, the agent's own control
plane (CONTROL_PATHS plus the profile's `instructionPaths`). A diff there
rewrites the checks, hooks, permissions, gates and prompts later runs obey, so
it is never class `none`, and no profile can drop or redefine it.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .common import array, obj, require, strings, text, unique

CONTROL = "agent-control"
CONTROL_PATHS = ("**/.claude/**", "**/CLAUDE.md", "**/AGENTS.md", "**/.mcp.json", ".github/**")


@dataclass(frozen=True)
class Row:
    id: str
    paths: tuple[str, ...]
    keywords: tuple[str, ...]


def matcher(globs: Iterable[str]) -> Any:
    """One compiled wcmatch matcher for a glob list; an empty list matches nothing.

    wcmatch (the PEP 723 pin) is imported here, on first match, so the row
    constants and load_rows stay importable where only PyYAML is (doctor)."""
    from wcmatch import glob

    return glob.compile(list(globs), flags=glob.GLOBSTAR | glob.BRACE | glob.DOTGLOB)


def load_rows(profile: dict[str, Any]) -> tuple[Row, ...]:
    value = profile.get("risk")
    if value is None:
        return ()
    rows = []
    for item in array(value):
        row = obj(item, "id", "paths keywords")
        require(row["id"] != CONTROL, f"risk row id {CONTROL} is reserved: it is built in and always owner-gated")
        rows.append(Row(text(row["id"]), strings(row.get("paths", [])), strings(row.get("keywords", []))))
    unique(tuple(rows))
    return tuple(rows)


def control_row(instruction_paths: Iterable[str]) -> Row:
    """The built-in `agent-control` row: the control plane plus the repo's own instruction paths."""
    return Row(CONTROL, (*CONTROL_PATHS, *instruction_paths), ())


def classify(paths: Iterable[str], added_text: str, rows: Iterable[Row]) -> list[str]:
    """Sorted ids of the rows the change matches; an empty list when none does."""
    changed = list(paths)
    hits = set()
    for row in rows:
        match = matcher(row.paths).match
        if any(match(path) for path in changed) or any(k in added_text for k in row.keywords):
            hits.add(row.id)
    return sorted(hits)
