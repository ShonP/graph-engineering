"""Run the checks a repository opted into in .claude/graph-checks.json.

  configured_check.py test <root>          0 pass or not verified, 2 fail or broken opt-in,
                                           77 no config or no test block
  configured_check.py lint <root> <file>   0 always; PostToolUse context JSON on stdout

Argv runs directly: no shell, cwd=root, its own session, output spooled to a
temp file so a verbose suite never floods the model. A timeout kills the whole
process group and reports "not verified" instead of blocking: a check that
cannot finish is not evidence of a failure.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from checks_config import FILE, load

CONFIG = '.claude/graph-checks.json'
NOT_CONFIGURED = 77
TAIL_BYTES = 4000


def run(argv: tuple[str, ...], root: Path, timeout: int) -> tuple[int, str]:
    """Return (exit code, last TAIL_BYTES of output); raise OSError or TimeoutExpired."""
    with tempfile.TemporaryFile() as log:
        with subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                              start_new_session=True) as process:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise
        log.seek(0, os.SEEK_END)
        log.seek(max(0, log.tell() - TAIL_BYTES))
        return process.returncode, log.read().decode(errors='replace')


def tail(output: str, lines: int) -> str:
    return '\n'.join(output.rstrip().splitlines()[-lines:])[-TAIL_BYTES:]


def test(root: Path) -> int:
    path = root / CONFIG
    if not path.is_file():
        return NOT_CONFIGURED
    try:
        config = load(path)
    except (ValueError, OSError) as exc:
        print(f'{CONFIG} is invalid: {exc}. No checks ran; fix or delete it.', file=sys.stderr)
        return 2
    if config.test is None:
        return NOT_CONFIGURED
    if config.precheck:
        pre = config.precheck
        try:
            code, detail = run(pre.argv, root, pre.timeout)[0], ''
        except subprocess.TimeoutExpired:
            code, detail = 124, f' (did not finish within {pre.timeout} s)'
        except OSError as exc:
            code, detail = 127, f' ({exc.strerror})'
        if code:
            print(f'precheck {pre.argv[0]} failed (exit {code}): tests not verified{detail}', file=sys.stderr)
            return 0
    argv = config.test.argv
    try:
        code, output = run(argv, root, config.test.timeout)
    except subprocess.TimeoutExpired:
        print(f'tests not verified: {argv[0]} did not finish within {config.test.timeout} s', file=sys.stderr)
        return 0
    except OSError as exc:
        reason = 'not found' if isinstance(exc, FileNotFoundError) else f'could not start ({exc.strerror})'
        print(f'Test runner {argv[0]} {reason} in {root}. Install it or fix {CONFIG}. No tests ran.', file=sys.stderr)
        return 2
    if code == 0:
        return 0
    print(f'Tests failed: {" ".join(argv)} in {root} (exit {code}). Fix them, then finish. '
          f'This check runs once per prompt.\n{tail(output, 20)}', file=sys.stderr)
    return 2


def inside(root: Path, file: str) -> str | None:
    """`file` relative to root when it is a regular file strictly inside root.

    The separator keeps a sibling such as /repo-evil out of /repo; realpath
    first, so a symlink cannot smuggle an outside file in.
    """
    if not file or not os.path.isabs(file):
        return None
    base, real = os.path.realpath(root), os.path.realpath(file)
    if not real.startswith(base + os.sep) or not os.path.isfile(real):
        return None
    return os.path.relpath(real, base)


def context(text: str) -> int:
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': text}}))
    return 0


def lint(root: Path, file: str) -> int:
    path = root / CONFIG
    try:
        check = load(path).lint if path.is_file() else None
    except (ValueError, OSError):
        return 0  # The Stop hook reports a broken config; an edit is no place for it.
    relative = inside(root, file) if check else None
    if relative is None or not relative.endswith(check.extensions):
        return 0
    argv = tuple(relative if a == FILE else a for a in check.argv)
    try:
        code, output = run(argv, root, check.timeout)
    except subprocess.TimeoutExpired:
        return context(f'lint not verified: {argv[0]} did not finish within {check.timeout} s.')
    except FileNotFoundError:
        return context(f'lint skipped: {argv[0]} not found in {root} - dependencies not installed '
                       'in this worktree? Lint not verified.')
    except OSError as exc:
        return context(f'lint not verified: {argv[0]} could not start ({exc.strerror}).')
    if code == 0:
        return 0
    return context(f'Lint on {relative} reported problems (exit {code}). This is information, '
                   f'not a block.\n\n{tail(output, 60)}')


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == 'test':
        return test(Path(argv[2]).resolve())
    if len(argv) == 4 and argv[1] == 'lint':
        try:
            return lint(Path(argv[2]).resolve(), argv[3])
        except OSError:
            return 0
    print('usage: configured_check.py test <root> | lint <root> <file>', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
