"""Small append-only artifact store, bounded attempts and coalesced events."""

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .common import array, choice, integer, load, obj, require, strings, text, version
from .identity import timestamp
from .receipts import Receipt


@contextmanager
def locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def write(path: Path, value: Any) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def store_items(path: Path) -> list[Any]:
    row = obj(load(path), "schema_version receipts")
    version(row["schema_version"])
    items = array(row["receipts"])
    for item in items:
        Receipt.parse(item)
    return items


def record(path: Path, receipt: Any) -> int:
    with locked(path):
        items = store_items(path) if path.exists() else []
        prior = [item for item in items if item.get("check_id") == receipt["check_id"]]
        require(not prior or timestamp(receipt["observed_at"]) > timestamp(prior[-1]["observed_at"]),
                "check receipt observations must increase")
        items.append(receipt)
        write(path, {"schema_version": 1, "receipts": items})
    return len(items)


def validate_attempts(value: Any) -> dict[str, Any]:
    row = obj(value, "schema_version max_fix_rounds task_ids attempts")
    version(row["schema_version"])
    limit = integer(row["max_fix_rounds"], 1)
    tasks = set(strings(row["task_ids"], empty=False))
    rounds: dict[str, int] = {}
    failures: dict[tuple[str, str], int] = {}
    stopped: set[str] = set()
    for item in array(row["attempts"]):
        attempt = obj(item, "task_id round decision candidate reason hypothesis outcome")
        task = text(attempt["task_id"])
        require(task in tasks, "attempt references unknown task")
        require(task not in stopped, f"{task}: repair requires a new approved plan after replan/blocked")
        number = integer(attempt["round"], 1)
        require(number == rounds.get(task, 0) + 1, f"{task}: rounds must be consecutive, never reset")
        decision = choice(attempt["decision"], {"fix", "replan", "blocked"})
        hypothesis = text(attempt["hypothesis"])
        outcome = choice(attempt["outcome"], {"pending", "passed", "failed"})
        require(decision != "fix" or failures.get((task, hypothesis), 0) < 2,
                f"{task}: same hypothesis failed twice; fresh diagnosis or replan required")
        require(number <= limit or decision in {"replan", "blocked"}, f"{task}: fix limit exceeded; replan or block")
        text(attempt["candidate"])
        text(attempt["reason"])
        rounds[task] = number
        if outcome == "failed":
            failures[(task, hypothesis)] = failures.get((task, hypothesis), 0) + 1
        if decision != "fix":
            stopped.add(task)
    return {"rounds": rounds, "requires_replan": sorted(stopped)}


def event_row(value: Any) -> dict[str, Any]:
    row = obj(value, "task_id sequence kind summary")
    text(row["task_id"])
    integer(row["sequence"], 1)
    choice(row["kind"], {"progress", "yielded", "completed", "failed", "decision"})
    text(row["summary"])
    return row


def event(path: Path, value: Any) -> dict[str, Any]:
    row = event_row(value)
    task, number, kind = row["task_id"], row["sequence"], row["kind"]
    with locked(path):
        state = obj(load(path), "schema_version tasks") if path.exists() else {"schema_version": 1, "tasks": {}}
        version(state["schema_version"])
        require(isinstance(state["tasks"], dict), "event state tasks must be an object")
        for key, item in state["tasks"].items():
            require(event_row(item)["task_id"] == key, "event task key differs from event identity")
        previous = state["tasks"].get(task)
        if previous is not None:
            require(number > integer(previous["sequence"], 1), "event sequence must increase")
        state["tasks"][task] = row
        write(path, state)
    return {"task_id": task, "wake": kind in {"completed", "failed", "decision"}, "kind": kind}
