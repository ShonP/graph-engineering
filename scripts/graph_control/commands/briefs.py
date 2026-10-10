"""validate-briefs: every plan task has a short, mostly prose brief at <run-dir>/tasks/<id>.md.

A brief is BLOCKED when it is missing or blank, longer than MAX_LINES lines, or
when more than MAX_FENCED_PERCENT of its lines sit in fenced code blocks, fence
lines included. Fences follow CommonMark: up to three spaces of indent, then
three or more backticks or tildes; the closing fence uses the same character,
is at least as long and carries nothing else; an unclosed fence runs to the end
of the file. It is also BLOCKED for each `graph-engineering:<skill>` name in a
skills list that resolves neither to the plugin's skills/*/<skill>/SKILL.md nor to the repo's
.claude/skills/<skill>/SKILL.md, the repo being the run dir's grandparent
(<repo>/.graph/<run>). A skills list is a line that starts, after optional
spaces, `-`, `*` or `**`, with `REQUIRED skills:`, plus the lines continuing it
up to a blank line, a list item or a heading; prose that mentions or quotes
REQUIRED is not one. Bare names and other plugins' names are never checked: a
host built-in cannot be resolved from disk. Every failing task is named, in
plan order. Reads files only.
"""

import re
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from ..skill_resolve import resolves
from .doctor import PLUGIN_ROOT

NAME = "validate-briefs"
HELP = ("check each plan task's tasks/<id>.md: present, at most 300 lines, at most 35 percent fenced code, "
        "and every graph-engineering: skill in a 'REQUIRED skills:' list shipped by this plugin")
MAX_LINES = 300
MAX_FENCED_PERCENT = 35
FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
PLUGIN = "graph-engineering"
SKILLS_LIST = re.compile(r"[\s*-]*REQUIRED skills:")
LIST_END = re.compile(r"\s*$|\s*(?:[-*+]|\d+[.)])(?:\s|$)|\s*#")
PLUGIN_SKILL = re.compile(rf"(?<![\w.:-]){PLUGIN}:[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("run", type=Path, help="the run directory holding plan.json and tasks/")


def fenced_lines(lines: list[str]) -> int:
    """Lines inside fenced code blocks, opening and closing fences included."""
    count, opening = 0, ""
    for line in lines:
        match = FENCE.match(line)
        if opening:
            count += 1
            if (match and match[1][0] == opening[0] and len(match[1]) >= len(opening)
                    and not match[2].strip()):
                opening = ""
        elif match and not (match[1][0] == "`" and "`" in match[2]):
            count, opening = count + 1, match[1]
    return count


def skills_lists(lines: list[str]) -> list[str]:
    """Each `REQUIRED skills:` label line and the lines continuing it, up to a blank line, list item or heading."""
    found, inside = [], False
    for line in lines:
        if SKILLS_LIST.match(line):
            inside = True
        elif inside and LIST_END.match(line):
            inside = False
        if inside:
            found.append(line)
    return found


def unshipped(lines: list[str], repo: Path) -> list[str]:
    """Plugin skill names in skills lists, deduplicated in order, that resolve nowhere."""
    names = dict.fromkeys(match[0] for line in skills_lists(lines) for match in PLUGIN_SKILL.finditer(line))
    return [name for name in names if resolves(name, PLUGIN_ROOT, repo, PLUGIN) is False]


def size(lines: list[str], name: str) -> str | None:
    if len(lines) > MAX_LINES:
        return f"{name} has {len(lines)} lines (limit {MAX_LINES})"
    fenced = fenced_lines(lines)
    if fenced * 100 > len(lines) * MAX_FENCED_PERCENT:
        return f"{name} has {fenced} of {len(lines)} lines fenced (limit {MAX_FENCED_PERCENT}%)"
    return None


def problems(run: Path, task: str) -> list[str]:
    tasks = run / "tasks"
    path = tasks / f"{task}.md"
    if path.parent != tasks:
        return [f"{task}: task id is not a file name under tasks/"]
    name = f"tasks/{task}.md"
    if not path.is_file():
        return [f"{task}: {name} is missing"]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not any(line.strip() for line in lines):
        return [f"{task}: {name} is empty"]
    found = [size(lines, name)] + [f"{name} names {skill}, which this plugin does not ship"
                                   for skill in unshipped(lines, run.resolve().parents[1])]
    return [f"{task}: {item}" for item in found if item]


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load, require
    from ..plan import Plan

    plan = Plan.parse(load(args.run / "plan.json"))
    found = [item for task in plan.tasks for item in problems(args.run, task.id)]
    require(not found, "; ".join(found))
    return {"briefs": len(plan.tasks)}
