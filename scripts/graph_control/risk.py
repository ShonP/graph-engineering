"""The profile's single risk table: which rows a change matches.

`risk:` is a list of rows {id, paths: [globs], keywords: [strings]}, the one
shape the profile template documents; any other shape is Invalid with SHAPE in
the message, which doctor reports verbatim. A row matches when any changed path
matches any of its globs, or any keyword occurs literally and case-insensitively
in the added lines, so `delete from` in lowercase SQL matches `DELETE FROM`. A
row with neither is a placeholder the repo or the engine fills (`public-copy`,
`outside-the-run`); it matches nothing here. Globs use the dialect the profile
template names: wcmatch GLOBSTAR | BRACE | DOTGLOB against repo-relative paths.
Pure: no I/O.

One row is built in and reserved: `agent-control`, the agent's own control
plane (CONTROL_PATHS plus the profile's `instructionPaths`). A diff there
rewrites the checks, hooks, permissions, gates and prompts later runs obey, so
it is never class `none`, and no profile can drop or redefine it.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .common import Invalid, obj, require, strings, text

CONTROL = "agent-control"
CONTROL_PATHS = ("**/.claude/**", "**/CLAUDE.md", "**/AGENTS.md", "**/.mcp.json", ".github/**")
SHAPE = "risk must be a list of rows, each {id, paths: [globs], keywords: [strings]}"


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


def parse_rows(value: Any) -> tuple[Row, ...]:
    """The `risk:` value as rows; None is no rows. Every shape error names SHAPE."""
    if value is None:
        return ()
    require(isinstance(value, list), f"{SHAPE}, not a mapping: write each key as a `- id: <key>` row"
            if isinstance(value, dict) else f"{SHAPE}, not {type(value).__name__}")
    rows = []
    for number, item in enumerate(value, 1):
        try:
            row = obj(item, "id", "paths keywords")
            rows.append(Row(text(row["id"]), strings(row.get("paths", [])), strings(row.get("keywords", []))))
        except Invalid as error:
            raise Invalid(f"{SHAPE}; row {number}: {error}") from error
    require(len({row.id for row in rows}) == len(rows), f"{SHAPE}; duplicate id")
    return tuple(rows)


def load_rows(profile: dict[str, Any]) -> tuple[Row, ...]:
    rows = parse_rows(profile.get("risk"))
    require(CONTROL not in {row.id for row in rows},
            f"risk row id {CONTROL} is reserved: it is built in and always owner-gated")
    return rows


def control_row(instruction_paths: Iterable[str]) -> Row:
    """The built-in `agent-control` row: the control plane plus the repo's own instruction paths."""
    return Row(CONTROL, (*CONTROL_PATHS, *instruction_paths), ())


def classify(paths: Iterable[str], added_text: str, rows: Iterable[Row]) -> list[str]:
    """Sorted ids of the rows the change matches; an empty list when none does."""
    changed = list(paths)
    added = added_text.casefold()
    hits = set()
    for row in rows:
        match = matcher(row.paths).match
        if any(match(path) for path in changed) or any(k.casefold() in added for k in row.keywords):
            hits.add(row.id)
    return sorted(hits)
