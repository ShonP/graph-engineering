"""Run a repository's explicit test argv; 77 means no configuration exists."""
from dataclasses import dataclass
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile


@dataclass(frozen=True)
class Check:
    argv: tuple[str, ...]
    timeout: int


def load(path: Path) -> Check:
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError('graph-checks.json requires version: 1')
    test = data.get('test')
    if not isinstance(test, dict):
        raise ValueError('graph-checks.json requires test.argv')
    argv = test.get('argv')
    timeout = test.get('timeout_seconds', 600)
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or '\x00' in a for a in argv):
        raise ValueError('test.argv must be a nonempty array of nonempty strings')
    if type(timeout) is not int or not 1 <= timeout <= 600:
        raise ValueError('test.timeout_seconds must be an integer from 1 to 600')
    return Check(tuple(argv), timeout)


def main(root: Path) -> int:
    path = root / '.claude/graph-checks.json'
    if not path.exists():
        return 77
    try:
        check = load(path)
        # Spool verbose suite output instead of copying it into model context.
        # Execute argv directly; a pipeline cannot mask the runner's exit code.
        with tempfile.TemporaryFile() as log:
            with subprocess.Popen(check.argv, cwd=root, stdout=log, stderr=log, start_new_session=True) as process:
                try:
                    process.wait(timeout=check.timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
            if process.returncode == 0:
                return 0
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 4000))
            tail = log.read().decode(errors='replace')
        print(f'Configured check {check.argv[0]} failed in {root} (exit {process.returncode}).\n{tail}', file=sys.stderr)
    except FileNotFoundError as exc:
        print(f'Configured check runner not found: {exc.filename}. No checks ran.', file=sys.stderr)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'Configured check BLOCKED: {exc}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
