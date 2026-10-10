"""qa-lanes: which qa leaves have finished this round, read from their per-lane `.done` markers.

The qa-lead waits on these markers, never on its own turn ending: a leaf that
still runs has written no marker, so its lane is pending. Each lane id (a lane,
or a shard of one such as `mobile-2`) is read from the round's qa directory
(`.graph/<run>/qa/r<N>/`):

  <id>.done             written by the leaf as its LAST act: the round, verdict
                        counts plus the report and findings paths; counts must
                        add up and the findings file must pass `findings`
  <id>.checkpoint.json  written by a leaf that stopped at its turn budget: the
                        round, the rows done and the rows (at least one) a
                        continuation leaf resumes from

Rounds are unambiguous: every marker carries `round`, and one whose round is
not `--round N` is stale, never finished (the lane stays `running` and is
listed under `stale`). When both files are this round's, a checkpoint newer
than the `.done` means a later leaf stopped mid-lane: the lane is
`checkpointed`, not done.

Exit 0 with PASS when every lane has a valid marker for the round; exit 75
with PENDING (running, stale and checkpointed lanes listed) when any has not;
exit 1 with BLOCKED when a marker or checkpoint is malformed. `--wait <s>` (at
most 270) blocks until every lane has a marker or the time is up, so the lead
never writes a sleep loop. Templates: skills/process/qa-verification/templates/.
"""

import json
import re
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from . import Output

NAME = "qa-lanes"
HELP = "report which qa lanes wrote a valid .done marker for this round; exit 75 while any is pending"
MAX_WAIT = 270
POLL_SECONDS = 2
LANE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
COUNTS = ("verified", "failed", "blocked")


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("qa_dir", type=Path, help="the round's qa directory, .graph/<run>/qa/r<N>")
    parser.add_argument("--lanes", required=True, help="comma-separated lane or shard ids the lead dispatched")
    parser.add_argument("--round", type=int, required=True, dest="round_id",
                        help="the qa round the lead was dispatched for (1 = first); other rounds' markers are stale")
    parser.add_argument("--wait", type=int, default=0, help=f"seconds to block for pending markers (0-{MAX_WAIT})")


def _lanes(value: str) -> list[str]:
    from ..common import require

    lanes = value.split(",")
    require(all(LANE_ID.fullmatch(lane) for lane in lanes), f"lane ids must match {LANE_ID.pattern}: {value!r}")
    require(len(set(lanes)) == len(lanes), f"a lane id is named twice: {value!r}")
    return lanes


def _header(path: Path, lane: str, fields: str) -> tuple[dict[str, Any], int]:
    """(the parsed marker, its round) after the checks every marker shares."""
    from ..common import integer, obj, require, version

    row = obj(json.loads(path.read_text(encoding="utf-8")), "schema_version lane round " + fields)
    version(row["schema_version"])
    require(row["lane"] == lane, f"{path.name}: lane {row['lane']!r} does not match its file")
    return row, integer(row["round"], 1)


def _done(row: dict[str, Any], name: str) -> dict[str, int]:
    from ..common import integer, require, text
    from ..findings import read

    counts = {key: integer(row[key]) for key in ("rows", *COUNTS)}
    require(sum(counts[key] for key in COUNTS) == counts["rows"],
            f"{name}: verified + failed + blocked must equal rows")
    require(Path(text(row["report"])).is_file(), f"{name}: report {row['report']} is absent")
    read(Path(text(row["findings"])))
    return counts


def _checkpoint(row: dict[str, Any], name: str) -> dict[str, Any]:
    from ..common import require, strings

    done, remaining = strings(row["rows_done"]), strings(row["remaining_rows"])
    strings(row["drivers"]), strings(row["fixtures"])
    require(bool(remaining), f"{name}: a checkpoint needs remaining rows; with none left write the .done marker")
    require(not set(done) & set(remaining), f"{name}: a row is both done and remaining")
    require(row["next_row"] == remaining[0], f"{name}: next_row must be the first remaining row")
    return {"next_row": row["next_row"], "remaining_rows": list(remaining)}


DONE_FIELDS = "rows report findings " + " ".join(COUNTS)
CHECKPOINT_FIELDS = "rows_done next_row remaining_rows drivers fixtures"


def _lane(qa_dir: Path, lane: str, round_id: int) -> tuple[str, Any]:
    """('done', counts) | ('checkpointed', resume point) | ('stale', None) | ('running', None)."""
    marker, checkpoint = qa_dir / f"{lane}.done", qa_dir / f"{lane}.checkpoint.json"
    current: dict[str, tuple[dict[str, Any], int]] = {}
    stale = False
    for kind, path, fields in (("done", marker, DONE_FIELDS), ("checkpointed", checkpoint, CHECKPOINT_FIELDS)):
        if path.is_file():
            row, marked = _header(path, lane, fields)
            if marked == round_id:
                current[kind] = (row, path.stat().st_mtime_ns)
            else:
                stale = True
    if "done" in current and current["done"][1] >= current.get("checkpointed", (None, -1))[1]:
        return "done", _done(current["done"][0], marker.name)
    if "checkpointed" in current:
        return "checkpointed", _checkpoint(current["checkpointed"][0], checkpoint.name)
    return ("stale" if stale else "running"), None


def _scan(qa_dir: Path, lanes: list[str], round_id: int) -> dict[str, Any]:
    from ..common import Invalid

    state: dict[str, Any] = {"done": {}, "checkpointed": {}, "running": [], "stale": []}
    for lane in lanes:
        try:
            kind, value = _lane(qa_dir, lane, round_id)
        except (Invalid, ValueError) as error:
            raise Invalid(f"lane {lane}: {error}") from None
        if kind in ("done", "checkpointed"):
            state[kind][lane] = value
        else:
            state["running"].append(lane)
            if kind == "stale":
                state["stale"].append(lane)
    return state


def run(args: Namespace) -> Output:
    from ..common import require

    require(0 <= args.wait <= MAX_WAIT, f"--wait must be 0 to {MAX_WAIT} seconds")
    require(args.round_id >= 1, "--round must be 1 or more")
    require(args.qa_dir.is_dir(), f"no qa directory: {args.qa_dir}")
    lanes = _lanes(args.lanes)
    deadline = time.monotonic() + args.wait
    while True:
        state = _scan(args.qa_dir, lanes, args.round_id)
        pending = len(state["done"]) < len(lanes)
        # A checkpointed lane changes only when the lead dispatches its continuation: stop waiting.
        if not state["running"] or time.monotonic() >= deadline:
            break
        time.sleep(POLL_SECONDS)
    status, code = ("PENDING", 75) if pending else ("PASS", 0)
    return Output(json.dumps({"status": status, **state}, sort_keys=True) + "\n", code)
