"""Ready queue over a parsed plan: which tasks may start now, and how long the longest chain is.

List scheduling: among tasks whose dependencies are all done, start the one heading the longest
remaining chain first, then plan order, so the critical path never waits behind short branches.
"""

from collections.abc import Collection

from .common import require
from .plan import Plan


def tail_length(plan: Plan) -> dict[str, int]:
    """Tasks on the longest chain from each task to a sink, the task itself included."""
    dependents: dict[str, list[str]] = {task.id: [] for task in plan.tasks}
    for task in plan.tasks:
        for dependency in task.depends_on:
            dependents[dependency].append(task.id)
    tail: dict[str, int] = {}
    for level in reversed(plan.levels()):
        for key in level:
            tail[key] = 1 + max((tail[child] for child in dependents[key]), default=0)
    return {task.id: tail[task.id] for task in plan.tasks}


def critical_path(plan: Plan) -> int:
    """Tasks on the longest depends_on chain; a lone task is 1."""
    return max(tail_length(plan).values(), default=0)


def ready_set(plan: Plan, done: Collection[str], running: Collection[str], width: int,
              held: Collection[str] = ()) -> list[str]:
    """Tasks that may start now, longest remaining chain first, capped at the free slots.

    Held tasks are started but hold no writer slot (in review, merged awaiting the gate,
    parked): never ready, never counted against the width, and their dependents wait.
    """
    known = {task.id for task in plan.tasks}
    for key in [*done, *running, *held]:
        require(key in known, f"unknown task id {key!r}")
    for key in done:
        require(key not in running, f"task id {key!r} is both done and running")
    seen: set[str] = set()
    for key in held:
        require(key not in seen, f"task id {key!r} is held twice")
        require(key not in done, f"task id {key!r} is both held and done")
        require(key not in running, f"task id {key!r} is both held and running")
        seen.add(key)
    tail = tail_length(plan)
    candidates = [task.id for task in plan.tasks
                  if task.id not in done and task.id not in running and task.id not in seen
                  and set(task.depends_on) <= set(done)]
    ordered = sorted(candidates, key=lambda key: -tail[key])
    return ordered[:max(0, width - len(running))]
