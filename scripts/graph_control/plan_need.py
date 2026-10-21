"""Per-task need and measure keys in a schema 2 plan, and the profile rule that requires them.

Both keys are optional, so plans written before they existed keep validating unchanged.

- `need`: `{user, trigger, run}`: who the new surface is for, the measured trigger that asks for it,
  and the argv that runs it. `user` and `trigger` are nonempty text, `run` a nonempty argv of
  nonempty strings.
- `measure`: `{command, baseline}`: the argv that measures, and the baseline it read before the change.
- An explicit null, a missing or unknown subkey, an empty value or a schema_version 1 plan is Invalid.

`enforce` runs only for `validate-plan --profile P --root R`. The directory part of a writable path's
static prefix (the text before the first glob character, up to its last `/`) and each of its
ancestors is a candidate; one matching a `hygiene.surfaces.roots` glob with no tracked file at HEAD
of R is a new surface and needs `need`. So `tools/**` names no directory under `tools/*` and
needs nothing, while `tools/newtool/**` and `tools/newtool/run.sh` both name `tools/newtool`. A
writable path that itself matches a `hygiene.measure.paths` glob needs `measure`; a glob writable
path is matched as written, so `web/**` does not match `**/package.json`.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import Invalid, require

KEYS = ("need", "measure")


@dataclass(frozen=True)
class Need:
    user: str
    trigger: str
    run: tuple[str, ...]


@dataclass(frozen=True)
class Measure:
    command: tuple[str, ...]
    baseline: str


SHAPES = {"need": (Need, {"user": "text", "trigger": "text", "run": "argv"}),
          "measure": (Measure, {"command": "argv", "baseline": "text"})}


def _value(value: Any, kind: str, where: str) -> Any:
    if kind == "text":
        require(isinstance(value, str) and bool(value.strip()), f"{where} must be nonempty text")
        return value
    argv = value if isinstance(value, list) else []
    require(bool(argv) and all(isinstance(item, str) and item.strip() for item in argv),
            f"{where} must be a nonempty argv of nonempty strings")
    return tuple(argv)


def need_fields(row: dict[str, Any], schema: int) -> dict[str, Any]:
    """The need and measure keys a task row carries, parsed; Invalid names the task and the key."""
    result = {}
    for key in KEYS:
        if key not in row:
            continue
        where, value = f"task {row.get('id')}: {key}", row[key]
        require(value is not None, f"{where} must not be null; omit the key instead")
        require(schema == 2, f"{where} requires schema_version 2")
        require(isinstance(value, dict), f"{where} must be an object")
        cls, shape = SHAPES[key]
        require(not value.keys() - shape.keys(), f"{where} has unknown fields {sorted(value.keys() - shape.keys())}")
        require(not shape.keys() - value.keys(), f"{where} is missing fields {sorted(shape.keys() - value.keys())}")
        result[key] = cls(**{name: _value(value[name], kind, f"{where}.{name}") for name, kind in shape.items()})
    return result


def load_config(path: Path) -> Any:
    import yaml

    from .hygiene.config import parse

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise Invalid(f"profile {path} cannot be read: {error}") from error
    return parse(data)


def _tracked_dirs(root: Path) -> set[str]:
    result = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "-z", "--name-only", "--full-tree", "HEAD"],
                            capture_output=True, text=True)
    require(result.returncode == 0, f"not a git repository with a HEAD commit: {root}")
    dirs = set()
    for path in filter(None, result.stdout.split("\0")):
        parts = path.split("/")[:-1]
        dirs.update("/".join(parts[:end]) for end in range(1, len(parts) + 1))
    return dirs


def _ancestors(path: str) -> list[str]:
    from .plan import static_prefix

    parts = static_prefix(path).split("/")[:-1]
    return ["/".join(parts[:end]) for end in range(1, len(parts) + 1)]


def enforce(plan: Any, root: Path, config: Any) -> None:
    """Raise Invalid listing every task that creates a new surface without need or changes a measure path
    without measure."""
    from .risk import matcher

    tracked, roots, measured = _tracked_dirs(root), matcher(config.surfaces.roots), matcher(config.measure.paths)
    problems = []
    for task in plan.tasks:
        surfaces = {d: None for path in task.writable_paths for d in _ancestors(path)
                    if roots.match(d) and d not in tracked}
        if task.need is None:
            problems += [f"task {task.id}: creates new surface {d} without need" for d in surfaces]
        if task.measure is None:
            problems += [f"task {task.id}: changes {path} without measure"
                         for path in task.writable_paths if measured.match(path)]
    require(not problems, "; ".join(problems))
