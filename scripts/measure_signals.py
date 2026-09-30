#!/usr/bin/env python3
"""Late success measures for a merged graph-engineering run. Stdlib only, no LLM.

  measure_signals.py <run-dir> [--now ISO]           measure each elapsed signal with no measure.md row
  measure_signals.py <run-dir> --remeasure [--now ISO]  also replace the rows of signals already measured
  measure_signals.py <run-dir> --baseline --now ISO  write post-deploy/baseline.json as of ISO
  measure_signals.py --due <repo> [--now ISO]        one line when measures are due; runs no command

A signal's argv runs with no shell from the repo root, 60 s, and must print one aggregate (a number
or JSON {"value": n}); anything else is rejected, never stored. Contract: post-deploy-verification.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timedelta, timezone
import json
import math
import operator
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile

TIMEOUT_S = 60
MAX_OUTPUT = 4096
NUMBER = r'-?[0-9]+(?:\.[0-9]+)?'
CONDITION = re.compile(
    rf'\s*value\s*(<=|>=|==|<|>)\s*(?:({NUMBER})|baseline\s*\*\s*({NUMBER})(?:\s*\+\s*({NUMBER}))?)\s*')
SCALAR = re.compile(r'-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?')
MERGED = re.compile(r'\bmerged:\s*([0-9a-f]{7,40})\b')
OWN_LINE = re.compile(r'- \[[^\]]*\] measure: ')
CONTROL = re.compile(r'[\x00-\x1f\x7f]')
OPS = {'<=': operator.le, '<': operator.lt, '>=': operator.ge, '>': operator.gt, '==': operator.eq}
GIT_VARS = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE')
HEADER = '# Success measures\n\n| goal | status | value | observed_at |\n| --- | --- | --- | --- |\n'
REJECTED = 'no data (rejected: non-aggregate output)'


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def clean(value: object) -> str:
    """One table cell or ledger field: a newline, control character or pipe cannot forge a row or a line."""
    return ' '.join(CONTROL.sub(' ', str(value)).replace('|', '/').split())


def number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def shown(value: float | None) -> str:
    return '-' if value is None else str(int(value)) if value.is_integer() and abs(value) < 1e15 else repr(value)


def load_json(path: Path) -> object:
    with contextlib.suppress(OSError, ValueError):
        return json.loads(path.read_text())
    return None


def env_for(**extra: str) -> dict[str, str]:  # minus GIT_DIR and co: a git hook exports them, -C does not win
    return {**{key: value for key, value in os.environ.items() if key not in GIT_VARS}, **extra}


def signals_of(run: Path) -> list:
    plan = load_json(run / 'plan.json')
    items = plan.get('success_signals') if isinstance(plan, dict) else None
    return items if isinstance(items, list) else []


def condition_of(text: object) -> tuple | None:
    match = CONDITION.fullmatch(text) if isinstance(text, str) else None
    op, absolute, factor, offset = match.groups() if match else ('', None, None, None)
    return (op, float(absolute) if absolute else None, float(factor or 1), float(offset or 0)) if match else None


def valid(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    command, days = item.get('command'), item.get('window_days')
    return (isinstance(item.get('goal'), str) and bool(clean(item['goal']))
            and isinstance(command, list) and bool(command) and all(isinstance(a, str) and a for a in command)
            and number(days) and days > 0 and condition_of(item.get('success_condition')) is not None)


def merged_at(run: Path, repo: Path) -> datetime | None:
    """Commit time of the ledger's last `merged: <sha>`; this script's own lines never count."""
    try:
        lines = (run / 'ledger.md').read_text().splitlines()
        shas = [m.group(1) for line in lines if not OWN_LINE.match(line) for m in MERGED.finditer(line)]
        if not shas:
            return None
        done = subprocess.run(['git', '-C', str(repo), 'show', '-s', '--format=%cI', shas[-1], '--'],
                              capture_output=True, text=True, timeout=10, env=env_for())
        return instant(done.stdout) if done.returncode == 0 and done.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def read_rows(path: Path) -> dict[str, str]:
    """measure.md rows by goal, in file order; rows start after the `| ---` separator."""
    try:
        lines = path.read_text().partition('\n| ---')[2].splitlines()[1:]
    except OSError:
        return {}
    return {line.strip().strip('|').split('|')[0].strip(): line for line in lines if line.startswith('| ')}


def scalar(raw: bytes) -> float | None:
    """The one aggregate a command may print; None for rows, text, several lines or oversized output."""
    text = raw.decode(errors='replace').strip() if len(raw) <= MAX_OUTPUT else ''
    if SCALAR.fullmatch(text):
        return float(text) if math.isfinite(float(text)) else None
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    ok = isinstance(parsed, dict) and list(parsed) == ['value'] and number(parsed['value'])
    return float(parsed['value']) if ok else None


def run_command(argv: list[str], repo: Path, env: dict[str, str]) -> tuple[str, float | None]:
    """(status, value): the value is set only for a clean exit printing one aggregate."""
    with tempfile.TemporaryFile() as out:
        try:
            process = subprocess.Popen(argv, cwd=repo, stdin=subprocess.DEVNULL, stdout=out,
                                       stderr=subprocess.DEVNULL, env=env, start_new_session=True)
        except OSError as error:
            return f'no data (command {"not found" if isinstance(error, FileNotFoundError) else "not runnable"})', None
        try:
            code = process.wait(timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)  # the whole group: a wrapper's children die too
            process.wait()
            return 'no data (timeout)', None
        if code != 0:
            return f'no data (command exit {code})', None
        out.seek(0)
        value = scalar(out.read(MAX_OUTPUT + 1))
    return ('', value) if value is not None else (REJECTED, None)


def evaluate(item: dict, baseline: object, repo: Path, env: dict[str, str]) -> tuple[str, float | None]:
    op, target, factor, offset = condition_of(item['success_condition'])
    if target is None:
        base = baseline.get(item['goal']) if isinstance(baseline, dict) else None
        if not number(base):
            return 'no data (no baseline)', None  # checked first: never run what cannot be judged
        target = base * factor + offset
    status, value = run_command(item['command'], repo, env)
    return (status, None) if value is None else ('met' if OPS[op](value, target) else 'not met', value)


def record_baseline(run: Path, repo: Path, items: list, env: dict[str, str]) -> int:
    """post-deploy/baseline.json {goal: value} as of GRAPH_MEASURE_AT; a goal with no clean aggregate stays out."""
    values = {}
    for item in filter(valid, items):
        status, value = run_command(item['command'], repo, env)
        values.update({} if value is None else {item['goal']: value})
        print(f'baseline: {clean(item["goal"])}: {status or shown(value)}')
    (run / 'post-deploy').mkdir(exist_ok=True)
    (run / 'post-deploy' / 'baseline.json').write_text(json.dumps(values, indent=2) + '\n')
    return 0


def measure(run: Path, now: datetime, baseline_only: bool = False, remeasure: bool = False) -> int:
    """Each signal once its window has passed (the set --due counts); only remeasure replaces a row."""
    repo, items = run.parent.parent, signals_of(run)
    merged = merged_at(run, repo) if items else None
    if merged is None:
        why = 'no `merged: <sha>` line in ledger.md that git resolves' if items else 'no success_signals in plan.json'
        print(f'measure: {why}; nothing measured')
        return 0
    env = env_for(GRAPH_MERGED_AT=stamp(merged), GRAPH_MEASURE_AT=stamp(now))
    if baseline_only:
        return record_baseline(run, repo, items, env)
    baseline = load_json(run / 'post-deploy' / 'baseline.json')
    rows, results = read_rows(run / 'measure.md'), []
    for index, item in enumerate(items):
        goal = (clean(item.get('goal') or '') if isinstance(item, dict) else '') or f'signal {index + 1}'
        if goal in rows and not remeasure:
            print(f'measure: {goal}: measured {rows[goal].rsplit("|", 2)[-2].strip()}; --remeasure to replace')
            continue
        if not valid(item):
            results.append((goal, 'no data (invalid signal)', None, ''))
            continue
        due_at = merged + timedelta(days=item['window_days'])
        if now < due_at:
            print(f'measure: {goal}: window open until {stamp(due_at)}; not measured')
            continue
        results.append((goal, *evaluate(item, baseline, repo, env), clean(item['success_condition'])))
    if not results:
        return 0
    for goal, status, value, _ in results:
        rows[goal] = f'| {goal} | {status} | {shown(value)} | {stamp(now)} |'
        print(f'measure: {goal}: {status} (value {shown(value)})'
              + ('; a late miss is a suggested bug run' if status == 'not met' else ''))
    tmp = run / '.measure.md.tmp'  # replaced whole, so a crash never leaves half a table
    tmp.write_text(HEADER + ''.join(f'{row}\n' for row in rows.values()))
    os.replace(tmp, run / 'measure.md')
    ledger = run / 'ledger.md'
    lead = '' if ledger.read_text().endswith('\n') else '\n'
    with ledger.open('a') as out:
        out.write(lead + ''.join(f'- [{stamp(now)}] measure: {goal} | {status} | value={shown(value)} | {cond}\n'
                                 for goal, status, value, cond in results))
    return 0


def due(repo: Path, now: datetime) -> int:
    """Print the SessionStart line for signals whose window elapsed with no measure.md row. Runs no signal."""
    found: list[tuple[str, int]] = []
    for run in (plan.parent for plan in sorted(repo.resolve().glob('.graph/*/plan.json'))):
        measured = read_rows(run / 'measure.md')
        waiting = [i for i in signals_of(run) if valid(i) and clean(i['goal']) not in measured]
        merged = merged_at(run, run.parent.parent) if waiting else None
        count = sum(now >= merged + timedelta(days=i['window_days']) for i in waiting) if merged else 0
        if count:
            found.append((clean(run.name), count))
    if found:
        print(f'graph-engineering: {sum(n for _, n in found)} success measure(s) due'
              f' ({", ".join(r for r, _ in found)}). Run: python3 {Path(__file__).resolve()} .graph/<run>')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure a merged run's success signals.")
    parser.add_argument('run_dir', nargs='?', help='<repo>/.graph/<run>')
    parser.add_argument('--due', metavar='REPO', help='list due measures under REPO/.graph; runs nothing')
    parser.add_argument('--baseline', action='store_true', help='write post-deploy/baseline.json as of --now')
    parser.add_argument('--remeasure', action='store_true', help='replace the rows of signals already measured')
    parser.add_argument('--now', type=instant, help='evaluation time, ISO 8601 (default: now)')
    args = parser.parse_args(argv)
    now = args.now or datetime.now(timezone.utc)
    if args.due:
        return due(Path(args.due), now)
    run = Path(args.run_dir or '').resolve()
    if not args.run_dir or run.parent.name != '.graph' or not (run / 'plan.json').is_file():
        parser.error('<run-dir> must be <repo>/.graph/<run> holding a plan.json')
    if args.baseline and not args.now:
        parser.error('--baseline needs --now <deployedAt>: a baseline taken later already holds the change')
    return measure(run, now, args.baseline, args.remeasure)


if __name__ == '__main__':
    raise SystemExit(main())
