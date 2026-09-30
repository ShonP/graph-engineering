"""Change digest: markdown of at most 60 lines for a merge exhibit or a PR body, from git alone.

The diff is the working tree against `base`, as in depth.py: committed, staged
and unstaged changes to tracked files; untracked files are excluded. Small (at
most 10 files and 300 changed lines, binary files counting 0): the per-file stat,
grouped by plan task. A file joins every task whose `writable_paths` match it
(the profile's glob dialect); files no task claims go under `unplanned`. Large:

- size: files and lines, split by the profile's `digest.exclude` globs;
- new public surfaces: added files matching the `api-surface` risk row's globs;
- hotspots: the top 5 of churn (lines added plus deleted per file in
  `git log --numstat` over the 90 days up to base) times the lines this diff
  changes; files `digest.exclude` matches are left out;
- ux evidence: files added under the profile's `uxEvidence.path`.

Read-only: `diff.autoRefreshIndex=false` stops `git diff` from rewriting the
index's stat cache. The dependency-graph delta is deferred: it needs project
tooling, and graph_control executes none.
"""

import os
import re
from pathlib import Path
from typing import Any

from .common import require, strings, text
from .depth import DIFF, _commit
from .identity import git
from .plan import Plan
from .risk import load_rows, matcher

SMALL_FILES, SMALL_LINES, LIST_MAX, TOP = 10, 300, 15, 5
API, UNPLANNED, WINDOW = "api-surface", "unplanned", "--since=90.days.ago"
READ_ONLY = ("-c", "diff.autoRefreshIndex=false")


def _tokens(root: Path, *args: str) -> list[str]:
    return os.fsdecode(git(root, *READ_ONLY, *args)).split("\0")


def _changes(root: Path, commit: str) -> dict[str, tuple[int, int]]:
    """Path -> (added, deleted) from `--numstat -z`; binary counts 0; a rename is keyed by its new path."""
    tokens, files, index = _tokens(root, *DIFF, "--numstat", "-z", commit, "--"), {}, 0
    while index < len(tokens) and tokens[index]:
        added, deleted, path = tokens[index].split("\t", 2)
        files[path or tokens[index + 2]] = (0 if added == "-" else int(added), 0 if deleted == "-" else int(deleted))
        index += 1 if path else 3
    return files


def _churn(root: Path, commit: str) -> dict[str, int]:
    """Lines added plus deleted per path over the 90 days of history up to `commit`."""
    churn: dict[str, int] = {}
    for token in _tokens(root, "log", WINDOW, "--numstat", "--format=", "--no-renames", "-z", commit, "--"):
        if token.strip("\n"):
            added, deleted, path = token.lstrip("\n").split("\t", 2)
            churn[path] = churn.get(path, 0) + sum(0 if count == "-" else int(count) for count in (added, deleted))
    return churn


def _code(path: str) -> str:
    """A CommonMark code span that holds any path: a fence longer than its longest backtick run."""
    path = "".join(char if char.isprintable() else "?" for char in path)
    fence = "`" * (max(map(len, re.findall("`+", path)), default=0) + 1)
    pad = " " if path[:1] == "`" or path[-1:] == "`" else ""
    return f"{fence}{pad}{path}{pad}{fence}"


def _mapping(profile: dict[str, Any], key: str) -> dict[str, Any]:
    value = profile.get(key) or {}
    require(isinstance(value, dict), f"{key} must be a mapping")
    return value


def _listing(title: str, paths: list[str], missing: str | None = None) -> list[str]:
    rows = [f"- {_code(path)}" for path in paths[:LIST_MAX]] or ["- none"]
    more = [f"- ... {len(paths) - LIST_MAX} more"] if len(paths) > LIST_MAX else []
    return ["", f"### {title} ({len(paths)})", *rows, *more] if missing is None else ["", f"### {title}", missing]


def _small(files: dict[str, tuple[int, int]], plan: Any) -> list[str]:
    stat = {path: f"- {_code(path)} +{added} -{deleted}" for path, (added, deleted) in files.items()}
    if plan is None:
        return ["", *stat.values()]
    tasks = [(task.id, matcher(task.writable_paths)) for task in Plan.parse(plan).tasks]
    rank = {key: index for index, (key, _) in enumerate(tasks)}
    groups: dict[str, list[str]] = {}
    for path in files:
        groups.setdefault(", ".join(key for key, match in tasks if match.match(path)) or UNPLANNED, []).append(path)
    ordered = sorted(groups.items(), key=lambda item: rank.get(item[0].split(", ")[0], len(rank)))
    return [row for name, paths in ordered for row in ("", f"### {name}", *(stat[path] for path in paths))]


def _large(root: Path, commit: str, files: dict[str, tuple[int, int]], profile: dict[str, Any]) -> list[str]:
    excluded = matcher(strings(_mapping(profile, "digest").get("exclude", [])))
    split = {flag: {path: sum(size) for path, size in files.items() if bool(excluded.match(path)) is flag}
             for flag in (False, True)}
    sizes = [f"{len(rows)} files, +{sum(files[path][0] for path in rows)} -{sum(files[path][1] for path in rows)}"
             for rows in split.values()]
    added = sorted(path for path in _tokens(root, *DIFF, "--diff-filter=A", "--name-only", "-z", commit, "--") if path)
    api = next((row for row in load_rows(profile) if row.id == API), None)
    ux = _mapping(profile, "uxEvidence").get("path")
    churn = _churn(root, commit)
    scores = sorted((-churn.get(path, 0) * lines, path) for path, lines in split[False].items() if churn.get(path))
    hot = [f"- {_code(path)} {churn[path]} x {split[False][path]} = {-score}" for score, path in scores[:TOP]]
    surfaces = [] if api is None else [path for path in added if matcher(api.paths).match(path)]
    evidence = [] if ux is None else [path for path in added if path.startswith(text(ux).rstrip("/") + "/")]
    return ["", "### Size", f"- counted: {sizes[0]}", f"- excluded by digest.exclude: {sizes[1]}",
            *_listing("New public surfaces", surfaces, None if api else f"- no `{API}` risk row in the profile"),
            "", "### Hotspots: 90-day churn x changed lines", *(hot or ["- none"]),
            *_listing("UX evidence", evidence, None if ux else "- no uxEvidence.path in the profile")]


def digest(root: Path, base: str, profile: dict[str, Any], plan: Any = None) -> str:
    commit = _commit(root, base)
    files = _changes(root, commit)
    added, deleted = sum(size[0] for size in files.values()), sum(size[1] for size in files.values())
    small = len(files) <= SMALL_FILES and added + deleted <= SMALL_LINES
    head = [f"## Change digest: {commit[:8]}..working tree",
            f"{len(files)} files changed, +{added} -{deleted} (tracked changes; untracked files excluded)"]
    body = _small(files, plan) if small else _large(root, commit, files, profile)
    return "\n".join(head + body) + "\n"
