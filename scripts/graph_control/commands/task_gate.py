"""task-gate: the check a task passes before the engine moves it to `gated`.

Three conditions, every failing one reported in a single BLOCKED reason. The
report's first status line is DONE or DONE_WITH_CONCERNS; a PARTIAL never
gates, it is superseded once its green commit's gate passes and its `<id>b`
follow-on carries the rest. Every name in the brief's `REQUIRED skills:` list
appears in the report's last `skills_loaded:` line. Every plan case the task
owns that sets `evidence` has that file under `--root`, or under the repo
holding `.graph/` when no root is given. Reads files only.
"""

import re
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

NAME = "task-gate"
HELP = ("before `gated`: the report's status is DONE or DONE_WITH_CONCERNS, its skills_loaded line covers "
        "the brief's REQUIRED skills, and each owned case's evidence file exists")
STATUS = re.compile(r"\W*(?:(?i:status):?\s*)?\W*"
                    r"(DONE_WITH_CONCERNS|DONE|PARTIAL|BLOCKED|NEEDS_CONTEXT|NEEDS_SETUP|ESCALATE)\b")
GATES = {"DONE", "DONE_WITH_CONCERNS"}
LOADED = "skills_loaded:"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("run", type=Path, help="the run directory holding plan.json and tasks/")
    parser.add_argument("--task", required=True, help="the plan task id")
    parser.add_argument("--report", required=True, type=Path, help="the task's report")
    parser.add_argument("--root", type=Path, help="the task worktree; evidence is read there when given")


def status_reason(lines: list[str], task: str) -> str | None:
    found = next((match[1] for line in lines if (match := STATUS.match(line))), None)
    if found is None:
        return "report has no status line"
    if found == "PARTIAL":
        return (f"PARTIAL never gates: mark it superseded once its green commit's gate passes; "
                f"{task}b carries the rest")
    return None if found in GATES else f"status {found} does not gate"


def skills_reason(brief: list[str], report: list[str]) -> str | None:
    from ..common import Invalid
    from ..skills import missing, names
    from .briefs import SKILLS_LIST, skills_lists

    listed = skills_lists(brief)
    if not listed:
        return "brief has no REQUIRED skills line"
    after = [line[match.end():] if (match := SKILLS_LIST.match(line)) else line for line in listed]
    loaded = [line.replace("`", "").strip(" -*") for line in report]
    last = next((line for line in reversed(loaded) if line.lower().startswith(LOADED)), "")
    try:
        gone = missing(names(",".join(part.strip(" *.") for part in after)), names(last))
    except Invalid as error:
        return f"skills unreadable: {error}"
    return f"skills not loaded: {', '.join(gone)}" if gone else None


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load, require, unique
    from ..plan import Plan

    plan = Plan.parse(load(args.run / "plan.json"))
    tasks = unique(plan.tasks)
    require(args.task in tasks, f"unknown task {args.task!r}: not in plan.json")
    brief = args.run / "tasks" / f"{args.task}.md"
    require(brief.parent == args.run / "tasks" and brief.is_file(), f"tasks/{args.task}.md is missing")
    report = args.report.read_text(encoding="utf-8", errors="replace").splitlines()
    root = args.root if args.root is not None else args.run.resolve().parents[1]
    cases = unique(plan.cases)
    reasons = [status_reason(report, args.task),
               skills_reason(brief.read_text(encoding="utf-8", errors="replace").splitlines(), report),
               *(f"case {key}: evidence {cases[key].evidence} missing" for key in tasks[args.task].case_ids
                 if cases[key].evidence is not None and not (root / cases[key].evidence).exists())]
    found = [reason for reason in reasons if reason]
    require(not found, "; ".join(found))
    return {"task": args.task, "gated": True}
