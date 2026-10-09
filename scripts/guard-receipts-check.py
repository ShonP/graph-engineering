#!/usr/bin/env python3
"""Receipt coverage check (advisory): guard lines a task adds with no killed mutation receipt.

    python3 guard-receipts-check.py <base> <receipts-dir> [--repo <path>] [--exclude <glob>]...

Run by an implementer before it reports DONE, from anywhere: `--repo` (default:
the current directory) is the task's worktree, <base> the dispatch base SHA and
<receipts-dir> the run's `.graph/<run>/mutants/`, where `mutate-witness.sh`
writes its receipts. Only committed work is read (`git diff <base>...HEAD`),
because the witness builds its mutant from HEAD.

A guard line is an added line, comments skipped, that either opens a branch
(`if`, `elif`, `else if`, `guard`, `unless`) or refuses (`raise`, `throw`,
`assert`, `die`, `exit`/`sys.exit` with a nonzero literal). Quoted and
backticked spans are dropped before matching, and Python's
`if __name__ == "__main__":` is not a guard. Also skipped, as noise: the lines of a
Python docstring, an `if` that opens a line inside an open `[`/`(` or a literal
`{` (a comprehension filter, a Dart collection-`if`), and a lone Dart-style
`if (...) Element(),` line ending in a comma. It is an advisory line
heuristic, not a parser: it still over-reports a plain `if` that refuses
nothing, which the implementer notes in the report; a listed line is a
checklist item, never a blocker by itself. Test files,
fixtures, docs and data files (see SKIPPED) are never scanned; `--exclude` adds
more fnmatch globs, matched against the repo-relative path.

A line is covered when a receipt with `killed: true` names the same `file` and
its `lines` range holds it. A receipt observed on an earlier commit is carried
forward through `git diff <receipt head> HEAD`: a range shifted by edits
elsewhere in the file still covers, a range that a later commit touched is
stale and covers nothing. An unreadable receipt is named on stderr and ignored.

Exit: 0 every guard line covered; 1 the uncovered lines are listed as
`<file>:<line>: <text>`; 2 usage or git error. Stdlib only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

GUARD = re.compile(
    r"^(?:\}\s*)?(?:if|elif|else\s+if|guard|unless)\b"
    r"|\b(?:raise|throw|assert|die)\b"
    r"|\bexit\s+[1-9]|\bsys\.exit\(\s*[1-9]"
)
COMMENT = ("#", "//", "/*", "*")
LITERAL = re.compile(r'"[^"]*"|\'[^\']*\'|`[^`]*`')
MAIN_BLOCK = re.compile(r"""if __name__ == ["']__main__["']:""")
SKIPPED = (
    "test_*", "*_test.*", "*.test.*", "*.spec.*", "*Tests.*", "conftest.py",
    "*.md", "*.txt", "*.rst", "*.json", "*.yaml", "*.yml", "*.toml", "*.lock", "*.csv", "*.svg",
)
SKIPPED_DIRS = {"test", "tests", "__tests__", "spec", "fixtures", "testdata", ".graph"}
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class GitError(Exception):
    pass


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} exited {result.returncode}")
    return result.stdout


def hunks(diff: str):
    """(old_start, old_count, new_start, new_count) per hunk of a -U0 diff."""
    for row in diff.splitlines():
        match = HUNK.match(row)
        if match:
            old, old_n, new, new_n = match.groups()
            yield int(old), int(old_n or 1), int(new), int(new_n or 1)


def scanned(path: str, excludes: list[str]) -> bool:
    parts = path.split("/")
    if SKIPPED_DIRS.intersection(parts[:-1]):
        return False
    if any(fnmatch.fnmatch(parts[-1], glob) for glob in SKIPPED):
        return False
    return not any(fnmatch.fnmatch(path, glob) for glob in excludes)


def is_guard(text: str) -> bool:
    line = text.strip()
    if not line or line.startswith(COMMENT) or MAIN_BLOCK.match(line):
        return False
    return bool(GUARD.search(LITERAL.sub("", line)))


LITERAL_OPEN = re.compile(r"[=:,(\[]\s*\{$")
BRANCH_START = re.compile(r"^(?:if|elif)\b")
ELEMENT_IF = re.compile(r"^if\s*\(.*\)[^{;]*,$")


class Scan:
    """Per-file state over a run of consecutive added lines: docstring and open brackets."""

    def __init__(self, path: str):
        self.python = path.endswith((".py", ".pyi"))
        self.in_doc = False
        self.stack: list[str] = []

    def noise(self, text: str) -> bool:
        """True when the line is docstring prose or a branch word inside a list/call/map literal."""
        line = text.strip()
        if line.startswith(COMMENT) and not self.in_doc:
            return False
        if self.python:
            marks = line.count('"""') + line.count("'''")
            was_doc = self.in_doc
            if marks % 2:
                self.in_doc = not self.in_doc
            if was_doc or self.in_doc:
                return True
        code = LITERAL.sub("", line).split("//")[0]
        inside = bool(self.stack) and self.stack[-1] != "block"
        skip = bool(BRANCH_START.match(line)) and (inside or bool(ELEMENT_IF.match(line)))
        for char in code:
            if char in "[(":
                self.stack.append(char)
            elif char == "{":
                self.stack.append("literal" if LITERAL_OPEN.search(code.rstrip()) else "block")
            elif char in "])}" and self.stack:
                self.stack.pop()
        return skip


def added_lines(repo: Path, base: str):
    path, number = None, 0
    for row in git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", f"{base}...HEAD").splitlines():
        if row.startswith("+++ "):
            path = row[6:] if row.startswith("+++ b/") else None
        elif row.startswith("@@"):
            match = HUNK.match(row)
            number = int(match.group(3)) if match else 0
        elif row.startswith("+") and path:
            yield path, number, row[1:]
            number += 1


def guard_lines(repo: Path, base: str, excludes: list[str]):
    found, scan, last = [], None, (None, 0)
    for path, number, text in added_lines(repo, base):
        if not scanned(path, excludes):
            continue
        if scan is None or last != (path, number - 1):
            scan = Scan(path)
        last = (path, number)
        if not scan.noise(text) and is_guard(text):
            found.append((path, number, text))
    return found


def carry(repo: Path, head: str, file: str, low: int, high: int) -> tuple[int, int] | None:
    """The receipt's range in HEAD's numbering, or None when a later commit touched it."""
    try:
        diff = git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", head, "HEAD", "--", file)
    except GitError:
        return None
    shift = 0
    for old, old_n, new, new_n in hunks(diff):
        old_end = old + old_n - 1 if old_n else old
        if old_n and old <= high and old_end >= low:
            return None
        if not old_n and low <= old < high:
            return None
        if (old_end if old_n else old) < low:
            shift += new_n - old_n
    return low + shift, high + shift


def receipts(repo: Path, folder: Path, current: str):
    count = 0
    ranges: dict[str, list[tuple[int, int]]] = {}
    for path in sorted(folder.rglob("*.json")) if folder.is_dir() else []:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            low, _, high = str(body["lines"]).partition("-")
            span = (int(low), int(high or low))
            file, killed, head = str(body["file"]), body["killed"] is True, str(body.get("head") or current)
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"guard-receipts: ignoring unreadable receipt {path}: {error}", file=sys.stderr)
            continue
        count += 1
        if not killed:
            continue
        moved = span if head == current else carry(repo, head, file, *span)
        if moved:
            ranges.setdefault(file, []).append(moved)
    return count, ranges


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="guard-receipts-check.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("base", help="the task's base commit (the dispatch base SHA)")
    parser.add_argument("receipts", type=Path, help="directory of mutate-witness receipts")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="the task worktree (default: cwd)")
    parser.add_argument("--exclude", action="append", default=[], help="fnmatch glob of paths not to scan")
    args = parser.parse_args(argv)
    try:
        current = git(args.repo, "rev-parse", "--verify", "HEAD").strip()
        git(args.repo, "rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}")
        guards = guard_lines(args.repo, args.base, args.exclude)
        count, ranges = receipts(args.repo, args.receipts, current)
    except GitError as error:
        print(f"guard-receipts: {args.base}: {error}", file=sys.stderr)
        return 2
    missing = [f"{p}:{n}: {t.strip()[:100]}" for p, n, t in guards
               if not any(low <= n <= high for low, high in ranges.get(p, []))]
    tally = f"{len(guards)} guard lines, {count} receipt{'' if count == 1 else 's'}"
    if missing:
        print("\n".join(missing))
        print(f"guard-receipts: {len(missing)} added guard lines have no killed receipt ({tally})")
        return 1
    print(f"guard-receipts: every added guard line has a killed receipt ({tally})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
