"""The profile's single risk table: which rows a change matches.

`risk:` is a list of rows {id, paths: [globs], keywords: [strings]}, the one
shape the profile template documents; any other shape is Invalid with SHAPE in
the message, which doctor reports verbatim. A row matches when any changed path
matches any of its globs, or any keyword occurs in one added line: literally and
case-sensitively, spelled the way the code spells it (SQL convention is
uppercase; case-insensitive matching caught Tailwind `truncate`, prose "Stripe"
and UI copy "Delete from favorites"). A keyword starting with `re:` is a Python
regex instead, compiled once when the table is read; an invalid one, or one that
matches an empty line, is BadPattern. `re` backtracks, so a regex reads only
added lines of at most LONG_LINE characters (skipped_lines counts the rest) and
one classify has a time budget: past it, Overrun names the row being matched.
doctor flags obviously nested quantifiers (NESTED). The caller passes only the
added lines that keywords may read (depth drops prose files). A row with neither
is a placeholder the repo or the engine fills (`public-copy`, `outside-the-run`);
it matches nothing here. Globs use the dialect the profile template names:
wcmatch GLOBSTAR | BRACE | DOTGLOB against repo-relative paths. No I/O; on the
POSIX main thread classify arms SIGALRM for its budget and restores the handler.

One row is built in and reserved: `agent-control`, the agent's own control
plane (CONTROL_PATHS plus the profile's `instructionPaths`). A diff there
rewrites the checks, hooks, permissions, gates and prompts later runs obey, so
it is never class `none`, and no profile can drop or redefine it.
"""

import re
import signal
import threading
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from .common import Invalid, obj, require, strings, text

CONTROL = "agent-control"
CONTROL_PATHS = ("**/.claude/**", "**/CLAUDE.md", "**/AGENTS.md", "**/.mcp.json", ".github/**")
SHAPE = "risk must be a list of rows, each {id, paths: [globs], keywords: [strings]}"
REGEX = "re:"
LONG_LINE = 4096  # characters; a `re:` keyword skips longer added lines
BUDGET = 5.0  # seconds one classify may take
NESTED = re.compile(r"\([^)]*[+*]\)[+*]")  # a quantified group holding a quantifier, e.g. (a+)+


class BadPattern(Invalid):
    """A `re:` keyword that does not compile, or matches an empty line (it would gate every diff)."""


class Overrun(Invalid):
    """classify ran past its budget, almost always on a `re:` keyword that backtracks exponentially."""


class _Expired(Exception):
    """The budget ran out: raised between lines, or by SIGALRM inside a running regex."""


def _regex(row: str, keyword: str) -> re.Pattern[str]:
    try:
        pattern = re.compile(keyword[len(REGEX):])
    except re.error as error:
        raise BadPattern(f"risk row {row}: keyword {keyword!r} is not a valid regex: {error}") from error
    if pattern.search(""):
        raise BadPattern(f"risk row {row}: keyword {keyword!r} matches an empty line, so it would match every diff")
    return pattern


@dataclass(frozen=True)
class Row:
    id: str
    paths: tuple[str, ...]
    keywords: tuple[str, ...]
    literals: tuple[str, ...] = field(init=False, repr=False, compare=False)
    regexes: tuple[re.Pattern[str], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "literals", tuple(k for k in self.keywords if not k.startswith(REGEX)))
        object.__setattr__(self, "regexes", tuple(_regex(self.id, k) for k in self.keywords if k.startswith(REGEX)))


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
        except BadPattern:
            raise
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


def classify(paths: Iterable[str], added_text: str, rows: Iterable[Row], budget: float = BUDGET) -> list[str]:
    """Sorted ids of the rows the change matches; an empty list when none does.

    Keywords are searched line by line, so a regex never spans two added lines.
    Past `budget` seconds this raises Overrun naming the row being matched."""
    changed, lines = list(paths), added_text.split("\n")
    short = [line for line in lines if len(line) <= LONG_LINE]
    deadline, hits, row = time.monotonic() + budget, set(), None
    try:
        with _alarm(budget):
            for row in rows:
                if _hit(row, changed, lines, short, deadline):
                    hits.add(row.id)
    except _Expired:
        name = row.id if row is not None else "(none yet)"
        raise Overrun(f"risk row {name}: keyword matching ran past its {budget:g}s budget; a `re:` keyword with "
                      "nested quantifiers such as (a+)+ backtracks exponentially, so rewrite it") from None
    return sorted(hits)


def _hit(row: Row, changed: list[str], lines: list[str], short: list[str], deadline: float) -> bool:
    match = matcher(row.paths).match
    if any(match(path) for path in changed) or any(k in line for k in row.literals for line in lines):
        return True
    for pattern in row.regexes:
        for line in short:
            if time.monotonic() > deadline:
                raise _Expired
            if pattern.search(line):
                return True
    return False


@contextmanager
def _alarm(seconds: float) -> Iterator[None]:
    """SIGALRM at the deadline: `re` checks for signals while it backtracks, so a
    runaway search inside one line stops too. POSIX main thread only; elsewhere the
    deadline is checked between lines, and one runaway line can run past it."""
    if not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        yield
        return

    def expire(signum: int, frame: Any) -> None:
        raise _Expired

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL if previous is None else previous)


def skipped_lines(added_text: str, rows: Iterable[Row]) -> int:
    """Added lines no `re:` keyword read because they exceed LONG_LINE; 0 when no row has one."""
    if not any(row.regexes for row in rows):
        return 0
    return sum(len(line) > LONG_LINE for line in added_text.split("\n"))


def nested(rows: Iterable[Row]) -> list[str]:
    """`<row> <keyword>` for each `re:` keyword with an obviously nested quantifier (doctor's warning)."""
    return [f"{row.id} {k!r}" for row in rows for k in row.keywords if k.startswith(REGEX) and NESTED.search(k)]
