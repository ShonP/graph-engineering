"""Deterministic review depth for a diff: lint, single or panel.

The diff is the working tree against `base` (`git diff <base>`): committed,
staged and unstaged changes to tracked files. Untracked files are excluded, and
the result says so. Precedence, first match wins:

1. panel  any `risk:` row matches (a changed path, or a keyword in an added line)
2. lint   every changed path is prose (*.md, *.txt, docs/**) and none matches
          `instructionPaths`; also an empty diff. Scripted checks only, no LLM.
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
from .risk import classify, load_rows, matcher

PROSE = ("**/*.{md,txt}", "docs/**")
PANEL_LINES = 2000
LINT = "prose only: every changed file matches *.md, *.txt or docs/** and none matches instructionPaths"
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


def decide(root: Path, base: str, profile: dict[str, Any]) -> dict[str, Any]:
    panel_lines = integer(_mapping(profile.get("review"), "review").get("panel_lines", PANEL_LINES), 1)
    instruction = matcher(strings(profile.get("instructionPaths", [])))
    seams, rows = _seams(profile), load_rows(profile)
    commit = _commit(root, base)
    lines, files, paths = _numstat(git(root, *DIFF, "--numstat", "-z", commit, "--"))
    risk_rows = classify(paths, _added(git(root, *DIFF, "--unified=0", commit, "--")), rows)
    prose = matcher(PROSE)

    def result(depth: str, reasons: list[str]) -> dict[str, Any]:
        return {"depth": depth, "changed_lines": lines, "files": files, "risk_rows": risk_rows,
                "reasons": reasons, "untracked_excluded": True}

    reasons = [f"risk rows: {', '.join(risk_rows)}"] if risk_rows else []
    if not reasons and all(prose.match(path) and not instruction.match(path) for path in paths):
        return result("lint", [LINT if paths else EMPTY])
    if lines > panel_lines:
        reasons.append(f"{lines} changed lines > review.panel_lines {panel_lines}")
    for label, stacks in seams:
        if all(any(stack.match(path) for path in paths) for stack in stacks):
            reasons.append(f"seam {label}: every stack touched")
    if reasons:
        return result("panel", reasons)
    return result("single", [f"default: no risk row or seam, {lines} changed lines <= review.panel_lines {panel_lines}"])
