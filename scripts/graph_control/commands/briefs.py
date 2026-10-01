"""validate-briefs: every plan task has a short, mostly prose brief at <run-dir>/tasks/<id>.md.

A brief is BLOCKED when it is missing or blank, longer than MAX_LINES lines, or
when more than MAX_FENCED_PERCENT of its lines sit in fenced code blocks, fence
lines included. Fences follow CommonMark: up to three spaces of indent, then
three or more backticks or tildes; the closing fence uses the same character,
is at least as long and carries nothing else; an unclosed fence runs to the end
of the file. Every failing task is named, in plan order. Reads files only.
"""

import re
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

NAME = "validate-briefs"
HELP = "check each plan task's tasks/<id>.md: present, at most 300 lines, at most 35 percent fenced code"
MAX_LINES = 300
MAX_FENCED_PERCENT = 35
FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")


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


def problem(run: Path, task: str) -> str | None:
    tasks = run / "tasks"
    path = tasks / f"{task}.md"
    if path.parent != tasks:
        return f"{task}: task id is not a file name under tasks/"
    name = f"tasks/{task}.md"
    if not path.is_file():
        return f"{task}: {name} is missing"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not any(line.strip() for line in lines):
        return f"{task}: {name} is empty"
    if len(lines) > MAX_LINES:
        return f"{task}: {name} has {len(lines)} lines (limit {MAX_LINES})"
    fenced = fenced_lines(lines)
    if fenced * 100 > len(lines) * MAX_FENCED_PERCENT:
        return f"{task}: {name} has {fenced} of {len(lines)} lines fenced (limit {MAX_FENCED_PERCENT}%)"
    return None


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load, require
    from ..plan import Plan

    plan = Plan.parse(load(args.run / "plan.json"))
    problems = [found for found in (problem(args.run, task.id) for task in plan.tasks) if found]
    require(not problems, "; ".join(problems))
    return {"briefs": len(plan.tasks)}
