#!/usr/bin/env python3
"""Aggregate local Claude usage metadata without exporting conversation content."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
import statistics

KEYS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
TTL_KEYS = ('ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens')
RUN8 = re.compile(r'[0-9A-Za-z]{8}')
RUN_PREFIX = re.compile(r'([0-9A-Za-z]{8}):')
PER_AGENT = ('output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamps require an explicit timezone')
    return parsed


def run8(value):
    if not RUN8.fullmatch(value):
        raise ValueError('a run is the first 8 letters or digits of its id')
    return value


def identity(path):
    """(role, run8) of a transcript: meta.json agentType and description prefix; main-thread files are main."""
    if 'subagents' not in path.parts:
        return 'main', None
    try:
        meta = json.loads(path.with_suffix('.meta.json').read_text())
    except (OSError, ValueError):
        meta = None
    meta = meta if isinstance(meta, dict) else {}
    description = meta.get('description') if isinstance(meta.get('description'), str) else ''
    prefix = RUN_PREFIX.match(description)
    return str(meta.get('agentType') or 'unknown'), prefix.group(1) if prefix else None


def medians(requests):
    """Per role: agent count and the median per agent of first-turn input, output, cache reads and writes."""
    agents = defaultdict(list)
    for request in requests.values():
        agents[(request['role'], request['agent'])].append(request)
    roles = defaultdict(list)
    for (role, _), rows in agents.items():
        first = min(rows, key=lambda row: row['at'])['counts']
        context = first['input_tokens'] + first['cache_creation_input_tokens'] + first['cache_read_input_tokens']
        roles[role].append((context, *(sum(row['counts'][key] for row in rows) for key in PER_AGENT)))
    names = ('first_turn_input_median', 'output_median', 'cache_read_median', 'cache_write_median')
    return [{'role': role, 'agents': len(rows),
             **{name: statistics.median(row[index] for row in rows) for index, name in enumerate(names)}}
            for role, rows in sorted(roles.items())]


def aggregate(root, start, end, session=None, role=None, run=None, medians_table=False):
    requests = {}
    malformed = 0
    conflicts = 0
    for path in root.rglob('*.jsonl'):
        if session and path.stem != session and session not in path.parts[:-1]:
            continue
        path_role, path_run = identity(path)
        if role and role not in (path_role, path_role.rsplit(':', 1)[-1]) or run and path_run != run:
            continue
        with path.open(errors='replace') as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict) or row.get('type') != 'assistant':
                        continue
                    if not isinstance(row.get('timestamp'), str):
                        raise ValueError('invalid timestamp')
                    at = instant(row['timestamp'])
                    if not start <= at < end:
                        continue
                    message = row.get('message', {})
                    if not isinstance(message, dict):
                        raise ValueError('invalid message')
                    key, model = message.get('id'), message.get('model')
                    if not isinstance(key, str) or not isinstance(model, str):
                        raise ValueError('invalid message identity')
                    if not key or not model or model == '<synthetic>':
                        continue
                    usage = message.get('usage', {})
                    if not isinstance(usage, dict):
                        raise ValueError('invalid usage')
                    ttl = usage.get('cache_creation', {}) or {}
                    if not isinstance(ttl, dict):
                        raise ValueError('invalid cache usage')
                    counts = {k: usage.get(k, 0) for k in KEYS}
                    counts.update({k: ttl.get(k, 0) for k in TTL_KEYS})
                    if any(type(v) is not int or v < 0 for v in counts.values()):
                        raise ValueError('invalid token count')
                    bucket = 'worker' if 'subagents' in path.parts else 'main'
                    previous = requests.get(key)
                    if previous and previous['model'] != model:
                        conflicts += 1
                        continue
                    if previous is None:
                        requests[key] = {'model': model, 'bucket': bucket, 'counts': counts,
                                         'role': path_role, 'agent': str(path), 'at': at}
                    else:
                        # Streamed rows and copied sessions may repeat a message.
                        for name, value in counts.items():
                            previous['counts'][name] = max(previous['counts'][name], value)
                        if previous['bucket'] != bucket:
                            previous['bucket'] = 'ambiguous'
                except (ValueError, KeyError, TypeError):
                    malformed += 1
    groups = defaultdict(list)
    for request in requests.values():
        groups[(request['model'], request['bucket'])].append(request['counts'])
    result = []
    for (model, bucket), rows in sorted(groups.items()):
        totals = {key: sum(row[key] for row in rows) for key in (*KEYS, *TTL_KEYS)}
        contexts = [row['input_tokens'] + row['cache_creation_input_tokens'] + row['cache_read_input_tokens'] for row in rows]
        total_input = sum(contexts)
        result.append({'model': model, 'bucket': bucket, 'requests': len(rows), **totals,
                       'input_context_median': statistics.median(contexts),
                       'input_context_max': max(contexts),
                       'cache_read_fraction': totals['cache_read_input_tokens'] / total_input if total_input else None})
    report = {'start': start.isoformat(), 'end_exclusive': end.isoformat(),
              'unique_requests': len(requests), 'malformed_rows': malformed,
              'conflicting_model_rows': conflicts, 'groups': result,
              'filters': {'session': session, 'role': role, 'run': run},
              'billing_note': 'Local token evidence, not reconciled spend; no conversation content included.'}
    if medians_table:
        report['roles'] = medians(requests)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / '.claude/projects')
    parser.add_argument('--start', type=instant, required=True)
    parser.add_argument('--end', type=instant, required=True)
    parser.add_argument('--session', help='only this session id: its main transcript and its subagents')
    parser.add_argument('--role', help='only this agent type from meta.json, or its name after the last colon; '
                                       'main-thread requests are role main')
    parser.add_argument('--run', type=run8, help='only agents whose description starts with <run8>:')
    parser.add_argument('--medians', action='store_true',
                        help='add per role: agent count and per-agent medians of first-turn input, '
                             'output, cache reads and cache writes')
    args = parser.parse_args()
    if not args.root.is_dir() or args.end <= args.start:
        parser.error('require an existing session directory and end after start')
    print(json.dumps(aggregate(args.root, args.start, args.end, args.session, args.role, args.run, args.medians),
                     indent=2))


if __name__ == '__main__':
    main()
