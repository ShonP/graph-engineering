"""Per-dispatch budget of full-suite runs for wait-run.sh --full.

A start with --full is counted in <dir>/<GRAPH_RUN_ID>.full, where <dir> is
${GRAPH_WAIT_RUN_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/graph-engineering/wait-run}
(mode 0700; the file is 0600, opened without following a symlink). One line per
counted start, appended under flock:

  <UTC ISO> full <n>[ reason=<text>]

The first FREE_FULL_RUNS starts run freely; a later one without --reason is
refused before anything starts and is not counted. Fail open: no GRAPH_RUN_ID,
an id outside [A-Za-z0-9._-]{1,128} or equal to . or .., or a counter that
cannot be written prints one note on stderr and the run goes ahead uncounted.
"""
import fcntl
import os
import re
import sys
import time
from collections.abc import Mapping
from pathlib import Path

FREE_FULL_RUNS = 2
REASON_CHARS = 200
SAFE_ID = re.compile(r'[A-Za-z0-9._-]{1,128}')


def open_private(path: Path, flags: int) -> int:
    """Create or open mode 0600, never through a symlink planted in a shared temp dir."""
    return os.open(path, flags | os.O_CREAT | os.O_NOFOLLOW, 0o600)


def counter_path(env: Mapping[str, str]) -> Path | None:
    run_id = env.get('GRAPH_RUN_ID', '')
    if not SAFE_ID.fullmatch(run_id) or run_id in ('.', '..'):
        return None
    cache = env.get('XDG_CACHE_HOME') or str(Path.home() / '.cache')
    directory = env.get('GRAPH_WAIT_RUN_DIR') or str(Path(cache) / 'graph-engineering' / 'wait-run')
    return Path(directory) / f'{run_id}.full'


def one_line(reason: str) -> str:
    return ' '.join(reason.split())[:REASON_CHARS]


def count_and_check(path: Path, reason: str | None) -> tuple[bool, int]:
    """(allowed, n): n is this start's number; a refused start is not appended."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(open_private(path, os.O_RDWR | os.O_APPEND), 'a+', encoding='utf-8') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        count = handle.read().count('\n') + 1
        if count > FREE_FULL_RUNS and not reason:
            return False, count
        stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        handle.write(f'{stamp} full {count}' + (f' reason={one_line(reason)}' if reason else '') + '\n')
    return True, count


def note(text: str) -> None:
    print(f'wait-run: note: {text}; full-suite run not counted', file=sys.stderr)


def allow_full_run(env: Mapping[str, str], reason: str | None) -> bool:
    """Count one --full start; False (refusal printed) when the budget needs a reason."""
    run_id = env.get('GRAPH_RUN_ID', '')
    path = counter_path(env)
    if path is None:
        note('GRAPH_RUN_ID is not set' if not run_id else 'GRAPH_RUN_ID is not a safe file name')
        return True
    try:
        allowed, count = count_and_check(path, reason)
    except OSError as error:
        note(f'cannot write the counter: {error.strerror}')
        return True
    if not allowed:
        print(f'wait-run: refused: full-suite run {count} for {run_id} needs --reason "<why>"')
    return allowed
