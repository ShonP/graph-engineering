"""Deterministic review depth for a diff: lint, single or panel.

The diff is the working tree against `base` (`git diff <base>`): committed,
staged and unstaged changes to tracked files. Untracked files are excluded, and
the result says so. Precedence, first match wins:

1. panel  any `risk:` row matches (a changed path, or a keyword in an added line);
          with a plan, `outside-the-run` matches a changed path in no task's
          `writable_paths` when the profile keeps that row. The built-in
          `agent-control` row (risk.control_row) always applies: the agent's
          control plane and `instructionPaths`, so CLAUDE.md is never lint
2. lint   every changed path is prose and no row matched; also
          an empty diff. Scripted checks only, no LLM. Prose is an extension
          (*.md, *.markdown, *.rst, *.adoc) or a named prose file (README,
          CHANGELOG, LICENSE and the like, bare or .txt); never a directory or
          any other .txt, since docs/conf.py, requirements.txt and CMakeLists.txt
          are code. MDX is not prose: it imports and runs JSX.
3. panel  changed lines exceed `review.panel_lines` (default 2000), or the diff
          touches every stack of any `review.seams` list (stacks from `stacks[*].paths`)
4. single otherwise

Size and seams do not lift prose to panel: a long doc or a README in two stacks
is still prose. A rename counts as one file; both its paths are matched.
"""

import os
from pathlib import Path
from typing import Any

from .common import Invalid, array, integer, require, strings
from .identity import git
from .plan import Plan
from .risk import Row, classify, control_row, load_rows, matcher

PROSE_NAMES = "README,CHANGELOG,CHANGES,HISTORY,NEWS,AUTHORS,CONTRIBUTORS,CONTRIBUTING,LICENSE,LICENCE,NOTICE,COPYING"
PROSE = ("**/*.{md,markdown,rst,adoc}", f"**/{{{PROSE_NAMES}}}{{,.txt}}")
PANEL_LINES = 2000
OUTSIDE = "outside-the-run"
LINT = ("prose only: every changed file is *.md, *.markdown, *.rst, *.adoc or a named prose file "
        "(README, CHANGELOG, LICENSE and the like) and none matches instructionPaths")
EMPTY = "no tracked change against base; untracked files are excluded"
DIFF = ("diff", "--no-ext-diff", "--no-textconv", "--no-color", "--no-relative", "--find-renames")


def _mapping(value: Any, name: str) -> dict[str, Any]:
    value = {} if value is None else value
    require(isinstance(value, dict), f"{name} must be a mapping")
    return value


def _seams(profile: dict[str, Any]) -> list[tuple[str, list[Any]]]:
    """Each seam as (label, one compiled path matcher per stack)."""
    review = _mapping(profile.get("review"), "review")
    stacks = _mapping(profile.get("stacks"), "stacks")
    result = []
    for value in array(review.get("seams", [])):
        seam = strings(value)
        require(len(seam) >= 2, "a review.seams list names at least two stacks")
        for name in seam:
            require(isinstance(stacks.get(name), dict), f"review.seams names unknown stack {name}")
        result.append(("+".join(seam), [matcher(strings(stacks[name].get("paths", []))) for name in seam]))
    return result


def _numstat(raw: bytes) -> tuple[int, int, list[str]]:
    """(changed lines, files, paths) from `--numstat -z`; binary `-` counts 0, a rename gives two paths."""
    tokens = os.fsdecode(raw).split("\0")
    lines, files, paths, index = 0, 0, [], 0
    while index < len(tokens) and tokens[index]:
        added, deleted, path = tokens[index].split("\t", 2)
        lines += sum(0 if count == "-" else int(count) for count in (added, deleted))
        files += 1
        paths += [path] if path else tokens[index + 1:index + 3]
        index += 1 if path else 3
    return lines, files, paths


def _added(raw: bytes) -> str:
    """Added lines of a `--unified=0` patch; a `+++` inside a hunk is content, not a header."""
    lines, header = [], True
    for line in raw.decode("utf-8", "replace").split("\n"):
        if line.startswith("diff --git "):
            header = True
        elif line.startswith("@@"):
            header = False
        elif not header and line.startswith("+"):
            lines.append(line[1:])
    return "\n".join(lines)


def _commit(root: Path, base: str) -> str:
    require(bool(base.strip()) and not base.startswith("-"), "base must be a revision, not an option")
    try:
        return git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").decode().strip()
    except Invalid as error:
        raise Invalid(f"base {base!r} is not a commit in {root}") from error


def _outside(paths: list[str], rows: tuple[Row, ...], plan: Any) -> list[str]:
    """Changed paths no task's `writable_paths` covers; evaluated only with a plan and the profile's row."""
    if plan is None or OUTSIDE not in {row.id for row in rows}:
        return []
    owned = matcher(glob for task in Plan.parse(plan).tasks for glob in task.writable_paths)
    return [path for path in paths if not owned.match(path)]


def decide(root: Path, base: str, profile: dict[str, Any], plan: Any = None) -> dict[str, Any]:
    panel_lines = integer(_mapping(profile.get("review"), "review").get("panel_lines", PANEL_LINES), 1)
    rows = (*load_rows(profile), control_row(strings(profile.get("instructionPaths", []))))
    seams = _seams(profile)
    commit = _commit(root, base)
    lines, files, paths = _numstat(git(root, *DIFF, "--numstat", "-z", commit, "--"))
    risk_rows = classify(paths, _added(git(root, *DIFF, "--unified=0", commit, "--")), rows)
    outside = _outside(paths, rows, plan)
    risk_rows = sorted({*risk_rows, OUTSIDE}) if outside else risk_rows
    prose = matcher(PROSE)

    def result(depth: str, reasons: list[str]) -> dict[str, Any]:
        return {"depth": depth, "changed_lines": lines, "files": files, "risk_rows": risk_rows,
                "reasons": reasons, "untracked_excluded": True}

    reasons = [f"risk rows: {', '.join(risk_rows)}"] if risk_rows else []
    if outside:
        shown = ", ".join(outside[:5]) + (f" and {len(outside) - 5} more" if len(outside) > 5 else "")
        plural = "path" if len(outside) == 1 else "paths"
        reasons.append(f"{OUTSIDE}: {len(outside)} changed {plural} in no task's writable_paths: {shown}")
    if not reasons and all(prose.match(path) for path in paths):
        return result("lint", [LINT if paths else EMPTY])
    if lines > panel_lines:
        reasons.append(f"{lines} changed lines > review.panel_lines {panel_lines}")
    for label, stacks in seams:
        if all(any(stack.match(path) for path in paths) for stack in stacks):
            reasons.append(f"seam {label}: every stack touched")
    if reasons:
        return result("panel", reasons)
    return result("single", [f"default: no risk row or seam, {lines} changed lines <= review.panel_lines {panel_lines}"])
