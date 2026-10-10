"""qa-lanes: which qa leaves have finished, read from their per-lane `.done` markers.

The qa-lead waits on these markers, never on its own turn ending: a leaf that
still runs has written no marker, so its lane is pending. Each lane id (a lane,
or a shard of one such as `mobile-2`) is read from the qa directory:

  <id>.done             written by the leaf as its LAST act: verdict counts plus
                        the report and findings paths; counts must add up and
                        the findings file must pass the `findings` validator
  <id>.checkpoint.json  written by a leaf that stopped at its turn budget: the
                        rows done and the rows a continuation leaf resumes from

Exit 0 with PASS when every lane has a valid marker; exit 75 with PENDING
(running and checkpointed lanes listed) when any has not; exit 1 with BLOCKED
when a marker or checkpoint is malformed. `--wait <s>` (at most 270) blocks
until every marker is present or the time is up, so the lead never writes a
sleep loop. Templates: skills/process/qa-verification/templates/.
"""

import json
import re
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from . import Output

NAME = "qa-lanes"
HELP = "report which qa lanes wrote a valid .done marker; exit 75 while any is pending"
MAX_WAIT = 270
POLL_SECONDS = 2
LANE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
COUNTS = ("verified", "failed", "blocked")


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("qa_dir", type=Path, help="the run's qa directory, .graph/<run>/qa")
    parser.add_argument("--lanes", required=True, help="comma-separated lane or shard ids the lead dispatched")
    parser.add_argument("--wait", type=int, default=0, help=f"seconds to block for pending markers (0-{MAX_WAIT})")


def _lanes(value: str) -> list[str]:
    from ..common import require

    lanes = value.split(",")
    require(all(LANE_ID.fullmatch(lane) for lane in lanes), f"lane ids must match {LANE_ID.pattern}: {value!r}")
    require(len(set(lanes)) == len(lanes), f"a lane id is named twice: {value!r}")
    return lanes


def _done(path: Path, lane: str) -> dict[str, int]:
    from ..common import integer, obj, require, text, version
    from ..findings import read

    row = obj(json.loads(path.read_text(encoding="utf-8")), "schema_version lane rows report findings " + " ".join(COUNTS))
    version(row["schema_version"])
    require(row["lane"] == lane, f"{path.name}: lane {row['lane']!r} does not match its file")
    counts = {key: integer(row[key]) for key in ("rows", *COUNTS)}
    require(sum(counts[key] for key in COUNTS) == counts["rows"],
            f"{path.name}: verified + failed + blocked must equal rows")
    require(Path(text(row["report"])).is_file(), f"{path.name}: report {row['report']} is absent")
    read(Path(text(row["findings"])))
    return counts


def _checkpoint(path: Path, lane: str) -> dict[str, Any]:
    from ..common import obj, require, strings, version

    row = obj(json.loads(path.read_text(encoding="utf-8")),
              "schema_version lane rows_done next_row remaining_rows drivers fixtures")
    version(row["schema_version"])
    require(row["lane"] == lane, f"{path.name}: lane {row['lane']!r} does not match its file")
    done, remaining = strings(row["rows_done"]), strings(row["remaining_rows"])
    strings(row["drivers"]), strings(row["fixtures"])
    require(not set(done) & set(remaining), f"{path.name}: a row is both done and remaining")
    require(row["next_row"] == (remaining[0] if remaining else None),
            f"{path.name}: next_row must be the first remaining row")
    return {"next_row": row["next_row"], "remaining_rows": list(remaining)}


def _scan(qa_dir: Path, lanes: list[str]) -> dict[str, Any]:
    from ..common import Invalid

    done, checkpointed, running = {}, {}, []
    for lane in lanes:
        try:
            if (qa_dir / f"{lane}.done").is_file():
                done[lane] = _done(qa_dir / f"{lane}.done", lane)
            elif (qa_dir / f"{lane}.checkpoint.json").is_file():
                checkpointed[lane] = _checkpoint(qa_dir / f"{lane}.checkpoint.json", lane)
            else:
                running.append(lane)
        except (Invalid, ValueError) as error:
            raise Invalid(f"lane {lane}: {error}") from None
    return {"done": done, "checkpointed": checkpointed, "running": running}


def run(args: Namespace) -> Output:
    from ..common import require

    require(0 <= args.wait <= MAX_WAIT, f"--wait must be 0 to {MAX_WAIT} seconds")
    require(args.qa_dir.is_dir(), f"no qa directory: {args.qa_dir}")
    lanes = _lanes(args.lanes)
    deadline = time.monotonic() + args.wait
    while True:
        state = _scan(args.qa_dir, lanes)
        pending = len(state["done"]) < len(lanes)
        # A checkpointed lane changes only when the lead dispatches its continuation: stop waiting.
        if not state["running"] or time.monotonic() >= deadline:
            break
        time.sleep(POLL_SECONDS)
    status, code = ("PENDING", 75) if pending else ("PASS", 0)
    return Output(json.dumps({"status": status, **state}, sort_keys=True) + "\n", code)
