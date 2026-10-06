#!/usr/bin/env python3
"""Print one run-throughput aggregate from local Claude Code subagent transcripts. Stdlib only.

  throughput.py <metric> [--days N] [--root PATH]

Metrics (definitions in throughput_metrics.py):
  implementer-p90-active  nearest-rank p90 of active minutes, role `implementer` (name after the
                          last `:` of agentType), 2 decimals
  implementer-over-90     count of `implementer` or `implementer-simple` spans over 90 active minutes
  workflow-concurrency    mean across groups of time-weighted running agents, 2 decimals

The window ends at GRAPH_MEASURE_AT (ISO 8601 with an explicit timezone; unset means now, UTC) and
spans --days (1-90, default 14). Prints one bare number and exits 0. With no data, p90 and
concurrency print nothing, write one stderr line naming the metric and window, and exit 1; the
count prints 0. A naive or unparseable GRAPH_MEASURE_AT, an unknown metric or --days out of range
exits 2.
"""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

from session_usage import instant
from throughput_metrics import agent_spans, concurrency, p90

METRICS = ('implementer-p90-active', 'implementer-over-90', 'workflow-concurrency')
OVER_S = 90 * 60


def days(value):
    number = int(value)
    if not 1 <= number <= 90:
        raise argparse.ArgumentTypeError('--days must be 1-90')
    return number


def name(role):
    return role.rsplit(':', 1)[-1]


def measure(metric, spans):
    if metric == 'implementer-p90-active':
        value = p90([span.active for span in spans if name(span.role) == 'implementer'])
        return None if value is None else f'{value / 60:.2f}'
    if metric == 'implementer-over-90':
        roles = ('implementer', 'implementer-simple')
        return str(sum(1 for span in spans if name(span.role) in roles and span.active > OVER_S))
    value = concurrency(spans)
    return None if value is None else f'{value:.2f}'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('metric', choices=METRICS)
    parser.add_argument('--days', type=days, default=14)
    parser.add_argument('--root', type=Path, default=Path.home() / '.claude/projects')
    args = parser.parse_args()
    raw = os.environ.get('GRAPH_MEASURE_AT')
    try:
        end = instant(raw) if raw else datetime.now(timezone.utc)
    except ValueError:
        parser.error('GRAPH_MEASURE_AT must be ISO 8601 with an explicit timezone')
    if not args.root.is_dir():
        parser.error('--root must be an existing directory')
    start = end - timedelta(days=args.days)
    value = measure(args.metric, agent_spans(args.root, start, end))
    if value is None:
        print(f'throughput: no data for {args.metric} in [{start.isoformat()}, {end.isoformat()})', file=sys.stderr)
        return 1
    print(value)
    return 0


if __name__ == '__main__':
    sys.exit(main())
