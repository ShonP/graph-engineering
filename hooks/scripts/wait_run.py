"""Bounded blocking wait for a long command: start it detached, or attach to it.

  wait_run.py --log <absolute path> [--max-block S] [--full [--reason TEXT]] [-- <argv...>]

With argv: refuse (exit 2) while <log>.pid names a live job that has not
written <log>.exit; otherwise start argv as an orphan in its own session
(double fork + setsid, so neither a process-group kill nor a tree kill of the
caller reaches it), stdout and stderr to <log>, stdin from /dev/null, and record
the supervisor's pid in <log>.pid; it is also the job's process group, so
`kill -- -<pid>` stops the job. The supervisor writes the exit code to
<log>.exit (128+N on signal N, 127 when argv cannot start). Then, and without argv, wait up to S
seconds (default 270, clamped to 590) for <log>.exit and print one line:

  wait-run: exit=<n>|running state=complete|partial elapsed=<s>s max_block=<S>s log=<path>

elapsed is the job's age. A completed nonzero job adds the last 20 lines of the
log (at most 2000 chars). Exit: the job's code when complete, 75 when partial,
2 on a usage error, a refusal, no job, or a job that died without an exit code.
Argv is spawned directly: no shell, no network.

--full declares a full-suite start. Each GRAPH_RUN_ID gets two free full runs;
a later one needs --reason or is refused (exit 2) before anything starts.
wait_count.py owns the count; attach calls and starts without --full never count.
"""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

import wait_count
from wait_count import open_private

DEFAULT_BLOCK, MAX_BLOCK = 270, 590
PARTIAL, ERROR = 75, 2
POLL_SECONDS = 0.2
TAIL_LINES, TAIL_CHARS = 20, 2000
REFUSAL = 'a job for this log is still running; call again without a command to attach'


def parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    split = argv.index('--') if '--' in argv else len(argv)
    parser = argparse.ArgumentParser(prog='wait-run.sh')
    parser.add_argument('--log', required=True, type=Path)
    parser.add_argument('--max-block', type=int, default=DEFAULT_BLOCK, metavar='S')
    parser.add_argument('--full', action='store_true', help='a full-suite run: counted per GRAPH_RUN_ID')
    parser.add_argument('--reason', metavar='TEXT', help='why a full run past the free budget is needed')
    args = parser.parse_args(argv[:split])
    command = argv[split + 1:]
    if args.reason is not None and not args.reason.strip():
        parser.error('--reason must not be empty')
    if args.reason is not None and not args.full:
        parser.error('--reason needs --full')
    if not args.log.is_absolute():
        parser.error('--log must be an absolute path')
    if args.max_block < 0:
        parser.error('--max-block must be 0 or more')
    if split < len(argv) and not command:
        parser.error('nothing to run after --')
    args.max_block = min(args.max_block, MAX_BLOCK)
    return args, command


def sibling(log: Path, suffix: str) -> Path:
    return log.with_name(log.name + suffix)


def read_pid(path: Path) -> int | None:
    try:
        pid = int(path.read_text(encoding='ascii').strip())
    except (OSError, ValueError):
        return None
    return pid if pid > 1 else None  # never probe 0 or 1: kill(0) is our own group


def alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_exit(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding='ascii').strip())
    except (OSError, ValueError):
        return None


def busy(log: Path) -> bool:
    return alive(read_pid(sibling(log, '.pid'))) and read_exit(sibling(log, '.exit')) is None


def detach_descriptors(log_fd: int) -> None:
    """stdin from /dev/null, stdout and stderr to the log, every other fd closed.

    A caller's pipe held open here would keep its harness waiting for EOF for
    the job's whole life, so nothing above 2 survives.
    """
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.dup2(log_fd, 1)
    os.dup2(log_fd, 2)
    for name in os.listdir('/dev/fd'):
        if int(name) > 2:
            try:
                os.close(int(name))
            except OSError:
                pass


def supervise(argv: list[str], log_fd: int, exit_path: Path) -> None:
    """Run in the orphaned grandchild: run argv, record its code, never return."""
    code = 127
    try:
        detach_descriptors(log_fd)
        code = subprocess.call(argv)
        code = 128 - code if code < 0 else code
    except OSError as error:
        os.write(2, f'wait-run: cannot start {argv[0]}: {error.strerror}\n'.encode(errors='replace'))
    finally:
        try:
            temporary = sibling(exit_path, '.tmp')
            fd = open_private(temporary, os.O_WRONLY | os.O_TRUNC)
            os.write(fd, f'{code}\n'.encode())
            os.close(fd)
            os.replace(temporary, exit_path)  # an attach never reads half a code
        finally:
            os._exit(0)


def spawn(argv: list[str], log_fd: int, exit_path: Path) -> int:
    """Double fork; return the supervisor's pid, which is also its session and group id.

    The middle child exits at once, so the supervisor is reparented to init and
    no tree walk from the caller finds it. It reports its pid only after setsid,
    so it is never in the caller's process group once this returns.
    """
    read_end, write_end = os.pipe()
    child = os.fork()
    if child == 0:
        try:
            os.close(read_end)
            if os.fork() == 0:
                os.setsid()
                os.write(write_end, str(os.getpid()).encode())
                supervise(argv, log_fd, exit_path)
        finally:
            os._exit(0)
    os.close(write_end)
    os.waitpid(child, 0)
    with os.fdopen(read_end, 'rb') as pipe:
        data = pipe.read()  # EOF once the supervisor closed its inherited fds
    return int(data) if data.isdigit() else 0


def start(log: Path, argv: list[str]) -> int:
    pid_path, exit_path = sibling(log, '.pid'), sibling(log, '.exit')
    try:
        with os.fdopen(open_private(pid_path, os.O_RDWR), 'r+', encoding='ascii') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)  # two starts on one log: the second one refuses
            if busy(log):
                print(f'wait-run: {REFUSAL}', file=sys.stderr)
                return ERROR
            exit_path.unlink(missing_ok=True)
            log_fd = open_private(log, os.O_WRONLY | os.O_TRUNC)
            try:
                pid = spawn(argv, log_fd, exit_path)
            finally:
                os.close(log_fd)
            if pid <= 1:
                print('wait-run: could not start the job', file=sys.stderr)
                return ERROR
            handle.seek(0)
            handle.truncate()
            handle.write(f'{pid}\n')
    except OSError as error:
        print(f'wait-run: cannot start: {error.strerror}: {error.filename}', file=sys.stderr)
        return ERROR
    return 0


def tail(log: Path) -> str:
    try:
        with open(log, 'rb') as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 4 * TAIL_CHARS))  # utf-8: 2000 chars fit in 8000 bytes
            text = handle.read().decode(errors='replace')
    except OSError:
        return ''
    return '\n'.join(text.rstrip().splitlines()[-TAIL_LINES:])[-TAIL_CHARS:]


def mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def wait(log: Path, block: int) -> int:
    pid_path, exit_path = sibling(log, '.pid'), sibling(log, '.exit')
    pid = read_pid(pid_path)
    deadline = time.monotonic() + block
    while (code := read_exit(exit_path)) is None:
        if not alive(pid) and (code := read_exit(exit_path)) is None:
            problem = 'the job for this log ended without an exit code (killed?)' if pid else 'no job for this log'
            print(f'wait-run: {problem}; start one with -- <argv>', file=sys.stderr)
            return ERROR
        if time.monotonic() >= deadline:
            break
        time.sleep(min(POLL_SECONDS, max(0.0, deadline - time.monotonic())))
    started = mtime(pid_path) or mtime(exit_path) or time.time()
    ended = mtime(exit_path) if code is not None else time.time()
    elapsed = max(0, round((ended or time.time()) - started))
    state = f'exit={code} state=complete' if code is not None else 'exit=running state=partial'
    print(f'wait-run: {state} elapsed={elapsed}s max_block={block}s log={log}')
    if code and (text := tail(log)):
        print(text)
    return PARTIAL if code is None else code


def main(argv: list[str]) -> int:
    args, command = parse(argv)
    if command and args.full and not busy(args.log) and not wait_count.allow_full_run(os.environ, args.reason):
        return ERROR
    if command and (status := start(args.log, command)):
        return status
    return wait(args.log, args.max_block)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
