"""Run-throughput metrics over local Claude Code subagent transcripts. Stdlib only.

Definitions (they match the 14-day evidence analyzer, so a baseline taken with it compares):

- A span is one subagent transcript, `**/subagents/**/agent-*.jsonl`, with at least two timestamped
  rows. It is in a window when its last timestamp is (start inclusive, end exclusive); the whole
  span counts, never a clipped part. Files whose mtime is before the window start are not opened.
- Active seconds: the sum of consecutive timestamp gaps of IDLE_S (600 s) or less. A longer gap is
  idle time (waiting), not work.
- Group: the `workflows/wf_*` directory a span sits in; outside a workflow, its graph run (the
  `<run8>:` prefix of the meta description). A span with neither has no group.
- Concurrency of a group: the time-weighted mean number of running spans over the time at least
  one runs, each span running over [first, last]. Groups of fewer than two spans are skipped.

Only `timestamp` and the meta file's `agentType` and `description` are read; no transcript text
is kept or returned.
"""
from collections import defaultdict
import json
import math
from typing import NamedTuple

from session_usage import identity, instant

IDLE_S = 600


class Span(NamedTuple):
    role: str
    group: str | None
    first: float
    last: float
    active: float


def active_seconds(timestamps):
    ordered = sorted(timestamps)
    return sum(gap for gap in (b - a for a, b in zip(ordered, ordered[1:])) if gap <= IDLE_S)


def p90(values):
    """Nearest-rank p90: the value at rank ceil(0.9 * n) of the ascending values; None when empty."""
    ordered = sorted(values)
    return ordered[math.ceil(0.9 * len(ordered)) - 1] if ordered else None


def timestamps(path):
    found = []
    with path.open(errors='replace') as stream:
        for line in stream:
            try:
                row = json.loads(line)
                found.append(instant(row['timestamp']).timestamp())
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
    return found


def group_of(relative, run):
    workflow = next((parent for parent in relative.parents if parent.name.startswith('wf_')), None)
    if workflow is not None:
        return f'wf:{workflow}'
    return f'run:{run}' if run else None


def agent_spans(root, start, end):
    spans = []
    floor = start.timestamp()
    for path in root.rglob('agent-*.jsonl'):
        relative = path.relative_to(root)
        if 'subagents' not in relative.parts or path.stat().st_mtime < floor:
            continue
        found = timestamps(path)
        if len(found) < 2 or not floor <= max(found) < end.timestamp():
            continue
        role, run = identity(path)
        spans.append(Span(role, group_of(relative, run), min(found), max(found), active_seconds(found)))
    return spans


def busy_mean(intervals):
    """Time-weighted mean of running intervals over the time at least one runs; None if no time."""
    events = sorted([(first, 1) for first, _ in intervals] + [(last, -1) for _, last in intervals])
    running, busy, weighted, previous = 0, 0.0, 0.0, None
    for at, step in events:
        if running and previous is not None:
            busy += at - previous
            weighted += running * (at - previous)
        running += step
        previous = at
    return weighted / busy if busy else None


def concurrency(spans):
    groups = defaultdict(list)
    for span in spans:
        if span.group is not None:
            groups[span.group].append((span.first, span.last))
    means = [busy_mean(intervals) for intervals in groups.values() if len(intervals) >= 2]
    means = [mean for mean in means if mean is not None]
    return sum(means) / len(means) if means else None
