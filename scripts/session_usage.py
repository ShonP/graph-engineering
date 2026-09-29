#!/usr/bin/env python3
"""Aggregate local Claude usage metadata without exporting conversation content."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import statistics

KEYS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
TTL_KEYS = ('ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens')


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamps require an explicit timezone')
    return parsed


def aggregate(root, start, end):
    requests = {}
    malformed = 0
    conflicts = 0
    for path in root.rglob('*.jsonl'):
        with path.open(errors='replace') as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict) or row.get('type') != 'assistant':
                        continue
                    if not isinstance(row.get('timestamp'), str):
                        raise ValueError('invalid timestamp')
                    if not start <= instant(row['timestamp']) < end:
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
                        requests[key] = {'model': model, 'bucket': bucket, 'counts': counts}
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
    return {'start': start.isoformat(), 'end_exclusive': end.isoformat(),
            'unique_requests': len(requests), 'malformed_rows': malformed,
            'conflicting_model_rows': conflicts, 'groups': result,
            'billing_note': 'Local token evidence, not reconciled spend; no conversation content included.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / '.claude/projects')
    parser.add_argument('--start', type=instant, required=True)
    parser.add_argument('--end', type=instant, required=True)
    args = parser.parse_args()
    if not args.root.is_dir() or args.end <= args.start:
        parser.error('require an existing session directory and end after start')
    print(json.dumps(aggregate(args.root, args.start, args.end), indent=2))


if __name__ == '__main__':
    main()
