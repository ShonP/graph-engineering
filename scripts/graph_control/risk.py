"""The profile's single risk table: which rows a change matches.

A `risk:` row is {id, paths: [globs], keywords: [strings]}. It matches when any
changed path matches any of its globs, or any keyword occurs literally and
case-sensitively in the added lines (the template's contract: keywords are
spelled the way the code spells them). A row with neither is a placeholder the
repo or the engine fills (`public-copy`, `outside-the-run`); it matches nothing
here. Globs use the dialect the profile template names: wcmatch
GLOBSTAR | BRACE | DOTGLOB against repo-relative paths. Pure: no I/O.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from wcmatch import glob

from .common import array, obj, strings, text, unique

FLAGS = glob.GLOBSTAR | glob.BRACE | glob.DOTGLOB


@dataclass(frozen=True)
class Row:
    id: str
    paths: tuple[str, ...]
    keywords: tuple[str, ...]


def matcher(globs: Iterable[str]) -> glob.WcMatcher:
    """One compiled matcher for a glob list; an empty list matches nothing."""
    return glob.compile(list(globs), flags=FLAGS)


def load_rows(profile: dict[str, Any]) -> tuple[Row, ...]:
    value = profile.get("risk")
    if value is None:
        return ()
    rows = []
    for item in array(value):
        row = obj(item, "id", "paths keywords")
        rows.append(Row(text(row["id"]), strings(row.get("paths", [])), strings(row.get("keywords", []))))
    unique(tuple(rows))
    return tuple(rows)


def classify(paths: Iterable[str], added_text: str, rows: Iterable[Row]) -> list[str]:
    """Sorted ids of the rows the change matches; an empty list when none does."""
    changed = list(paths)
    hits = set()
    for row in rows:
        match = matcher(row.paths).match
        if any(match(path) for path in changed) or any(k in added_text for k in row.keywords):
            hits.add(row.id)
    return sorted(hits)
