"""Profile `writable_companions` pairs and the plan tasks that miss a companion glob."""

from typing import Any

from .common import Invalid
from .plan import Plan
from .risk import matcher

SHAPE = "writable_companions must be a list of {when: <glob>, also: <glob>}"


def _glob(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def parse(profile: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    value = profile.get("writable_companions", [])
    if not isinstance(value, list) or not all(
            isinstance(row, dict) and set(row) == {"when", "also"} and _glob(row["when"]) and _glob(row["also"])
            for row in value):
        raise Invalid(SHAPE)
    return tuple((row["when"], row["also"]) for row in value)


def missing_companions(plan: Plan, pairs: tuple[tuple[str, str], ...]) -> list[str]:
    messages = []
    for task in plan.tasks:
        for when, also in pairs:
            companion = matcher([also])
            if any(matcher([when]).match(path) for path in task.writable_paths) and not any(
                    path == also or companion.match(path) for path in task.writable_paths):
                messages.append(f'task {task.id}: writable_paths match "{when}" but not its companion "{also}"; '
                                f'add "{also}"')
    return messages
