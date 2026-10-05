"""Per-task budget keys in a schema 2 plan: a time estimate, a bounded write surface, a proof class.

All three keys are optional, and the limits bind only a task that carries `estimate_min`, so plans
written before the keys existed keep validating unchanged.

- `estimate_min`: integer minutes, 1 to MAX_ESTIMATE_MIN; a bool is not an integer.
- `path_cap_reason`: nonempty text, required once an estimated task names more than
  MAX_WRITABLE_PATHS writable paths.
- `proof`: one of PROOF. A `full_device` or `cluster` task proves on real devices or a cluster and
  builds nothing, so it produces no contract; building and proving are separate tasks.
- `path_cap_reason` and `proof` are valid only beside `estimate_min`.
- A schema_version 1 plan carries none of the three keys.
"""

from typing import Any

from .common import require

MAX_ESTIMATE_MIN = 45
MAX_WRITABLE_PATHS = 8
PROOF = frozenset({"focused", "full_device", "cluster"})
PROVING = frozenset({"full_device", "cluster"})
KEYS = ("estimate_min", "path_cap_reason", "proof")


def budget_fields(row: dict[str, Any]) -> dict[str, Any]:
    """The budget keys a task row carries; an explicit null is rejected rather than read as absent."""
    present = {key: row[key] for key in KEYS if key in row}
    for key, value in present.items():
        require(value is not None, f"task {row.get('id')}: {key} must not be null; omit the key instead")
    return present


def check_budget(task: Any, schema: int) -> None:
    """Raise Invalid, naming the task and the limit, when its budget keys break a rule above."""
    present = [key for key in KEYS if getattr(task, key) is not None]
    where = f"task {task.id}"
    require(schema == 2 or not present, f"{where}: {', '.join(present)} need schema_version 2")
    if task.estimate_min is None:
        require(not present, f"{where}: {', '.join(present)} need estimate_min")
        return
    estimate = task.estimate_min
    require(type(estimate) is int, f"{where}: estimate_min must be an integer, got {estimate!r}")
    require(1 <= estimate <= MAX_ESTIMATE_MIN,
            f"{where}: estimate_min must be 1-{MAX_ESTIMATE_MIN} minutes, got {estimate}; split the task")
    reason = task.path_cap_reason
    require(reason is None or (isinstance(reason, str) and bool(reason.strip())),
            f"{where}: path_cap_reason must be nonempty text")
    count = len(task.writable_paths)
    require(count <= MAX_WRITABLE_PATHS or reason is not None,
            f"{where}: {count} writable_paths exceed {MAX_WRITABLE_PATHS} without a path_cap_reason")
    proof = task.proof
    require(proof is None or (isinstance(proof, str) and proof in PROOF),
            f"{where}: proof must be one of {sorted(PROOF)}, got {proof!r}")
    require(proof not in PROVING or not task.produces,
            f"{where}: proof {proof} builds nothing, so produces must be empty; "
            f"split the build from the proof")
