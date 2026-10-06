#!/usr/bin/env python3
"""Count trigger-shaped plugin-script Bash calls by graph-engineering agents. Stdlib only.

  plugin_shell_calls.py [--days N] [--root PATH]

Counts Bash tool_use blocks (assistant rows, message.content[]) in subagent transcripts whose
role (agentType from the sibling .meta.json) starts with `graph-engineering:` and whose command
the PreToolUse guard's detector, hooks/scripts/plugin_shell.py find_violation, flags. One
definition: the metric and the guard share it. A block repeated by streaming or a copied
session counts once (by its tool_use id).

The window ends at GRAPH_MEASURE_AT (ISO 8601 with an explicit timezone; unset means now, UTC)
and spans --days (1-90, default 14); the end is exclusive. Prints one bare integer and exits 0;
an empty tree prints 0. Malformed lines are skipped and counted in one stderr line. A naive or
unparseable GRAPH_MEASURE_AT, --days out of range or a missing --root exits 2. Output is
aggregate only: no command, path or message text is ever printed.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hooks' / 'scripts'))

from plugin_shell import find_violation  # noqa: E402
from session_usage import identity, instant  # noqa: E402

ROLE_PREFIX = 'graph-engineering:'


def days(value):
    number = int(value)
    if not 1 <= number <= 90:
        raise argparse.ArgumentTypeError('--days must be 1-90')
    return number


def bash_commands(row):
    """(id, command) for each Bash tool_use block of an assistant row."""
    content = row['message']['content']
    if not isinstance(content, list):
        raise ValueError('invalid content')
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Bash':
            command = (block.get('input') or {}).get('command')
            if isinstance(command, str):
                yield block.get('id'), command


def count(root, start, end):
    """(violations, malformed lines) over graph-engineering subagent transcripts in [start, end)."""
    seen, hits, malformed = set(), 0, 0
    for path in root.rglob('*.jsonl'):
        if not identity(path)[0].startswith(ROLE_PREFIX):
            continue
        with path.open(errors='replace') as stream:
            for number, line in enumerate(stream):
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict) or row.get('type') != 'assistant':
                        continue
                    if not isinstance(row.get('timestamp'), str):
                        raise ValueError('invalid timestamp')
                    if not start <= instant(row['timestamp']) < end:
                        continue
                    for index, (key, command) in enumerate(bash_commands(row)):
                        key = key if isinstance(key, str) and key else (str(path), number, index)
                        if key not in seen and find_violation(command) is not None:
                            seen.add(key)
                            hits += 1
                except (ValueError, KeyError, TypeError, AttributeError):
                    malformed += 1
    return hits, malformed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
    hits, malformed = count(args.root, end - timedelta(days=args.days), end)
    if malformed:
        print(f'plugin_shell_calls: skipped {malformed} malformed lines', file=sys.stderr)
    print(hits)
    return 0


if __name__ == '__main__':
    sys.exit(main())
