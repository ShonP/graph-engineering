"""ready: the tasks that may start now, given the ids already done and running.

A task is ready when it is neither done nor running and every depends_on id is
done. Ready tasks are ordered longest remaining chain first, then plan order,
and capped at --max-width minus the running count. --hold ids (started, holding
no writer slot) are never ready and do not count against the width. Ids are
comma-separated; `--done ""` means nothing is done. An invalid plan is BLOCKED
with the validation message before any id is checked; an unknown id, one both
done and running, or a held id listed twice or also done or running, is
BLOCKED naming the id.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from .waves import DEFAULT_WIDTH, positive

NAME = "ready"
HELP = "tasks from plan.json that may start now, given --done and --running ids, capped at --max-width"


def ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("plan", type=Path, help="the run's plan.json")
    parser.add_argument("--done", required=True, type=ids, help="comma-separated finished task ids; \"\" for none")
    parser.add_argument("--running", type=ids, default=[], help="comma-separated task ids in flight")
    parser.add_argument("--hold", type=ids, default=[],
                        help="comma-separated started task ids holding no writer slot; never ready, not counted")
    parser.add_argument("--max-width", type=positive, default=DEFAULT_WIDTH,
                        help=f"most tasks in flight at once (default {DEFAULT_WIDTH})")


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load
    from ..plan import Plan
    from ..plan_queue import critical_path, ready_set

    plan = Plan.parse(load(args.plan))
    done, running = set(args.done), set(args.running)
    ready = ready_set(plan, done, running, args.max_width, held=args.hold)
    return {"ready": ready,
            "running": [task.id for task in plan.tasks if task.id in running],
            "remaining": sum(task.id not in done for task in plan.tasks),
            "critical_path": critical_path(plan),
            "max_width": args.max_width}
