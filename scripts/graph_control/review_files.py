from pathlib import Path
from typing import Any

from .common import require
from .plan import Plan

CADENCES = ("per-task", "per-run")
RUN_LEG = "run"


def cadence(profile: dict[str, Any]) -> str:
    review = profile.get("review") or {}
    require(isinstance(review, dict), "review must be a mapping")
    value = review.get("cadence", CADENCES[0])
    require(value in CADENCES, f"review.cadence must be one of {', '.join(CADENCES)}, not {value!r}")
    return value


def review_files(run_dir: Path, profile: dict[str, Any], plan: Any) -> dict[str, Any]:
    chosen = cadence(profile)
    legs = [RUN_LEG] if chosen == "per-run" else [task.id for task in Plan.parse(plan).tasks]
    latest = [run_dir / f"findings.{leg}.json" for leg in legs]
    rounds = sorted(str(path) for leg in legs for path in run_dir.glob(f"findings.{leg}.r*.json"))
    return {"cadence": chosen, "legs": legs, "latest": [str(path) for path in latest], "rounds": rounds,
            "missing": [str(path) for path in latest if not path.is_file()]}
