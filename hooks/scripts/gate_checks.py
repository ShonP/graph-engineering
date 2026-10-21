#!/usr/bin/env python3
"""Run the `checks` of <root>/.claude/graph-checks.json in order, one line per check.

  gate_checks.py <root> [--today YYYY-MM-DD]

  ok <id>                                    passed
  FAIL <id> exit=<n>                         blocking check failed; its output tail follows
  FAIL <id> timeout                          blocking check did not finish; its process group is killed
  FAIL <id> not found <program>              blocking check could not start
  advisory <id> failed, blocks from <date>   advisory check failed before its expires date
  FAIL <id> expired <date>                   advisory check failed on or after its expires date

Exit 2 on any FAIL or an invalid config, 77 when there is no config or no checks, else 0.
A check runs in <root> with the Stop hook's runner: no shell, stdin closed, its own session.
"""
import argparse
from datetime import date
from pathlib import Path
import subprocess
import sys

from checks_config import GateCheck, load
from configured_check import CONFIG, NOT_CONFIGURED, run, tail

FAILED = 2


def outcome(check: GateCheck, root: Path) -> tuple[str | None, str]:
    try:
        code, output = run(check.argv, root, check.timeout)
    except subprocess.TimeoutExpired:
        return 'timeout', ''
    except FileNotFoundError:
        return f'not found {check.argv[0]}', ''
    except OSError as exc:
        return f'could not start {check.argv[0]} ({exc.strerror})', ''
    return (f'exit={code}' if code else None), tail(output, 20)


def verdict(check: GateCheck, failure: str, today: date) -> tuple[str, bool]:
    if check.mode == 'blocking':
        return f'FAIL {check.id} {failure}', True
    if today < check.expires:
        return f'advisory {check.id} failed, blocks from {check.expires}', False
    return f'FAIL {check.id} expired {check.expires}', True


def gate(root: Path, today: date) -> int:
    path = root / CONFIG
    if not path.is_file():
        return NOT_CONFIGURED
    try:
        checks = load(path).checks
    except (ValueError, OSError) as exc:
        print(f'{CONFIG} is invalid: {exc}. No checks ran; fix it.', file=sys.stderr)
        return FAILED
    if not checks:
        return NOT_CONFIGURED
    failed = False
    for check in checks:
        failure, output = outcome(check, root)
        if failure is None:
            print(f'ok {check.id}', flush=True)
            continue
        line, blocks = verdict(check, failure, today)
        print(line, flush=True)
        if blocks and output:
            print(output, flush=True)
        failed = failed or blocks
    return FAILED if failed else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='gate_checks.py')
    parser.add_argument('root', type=Path)
    parser.add_argument('--today', type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    return gate(args.root.resolve(), args.today)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
