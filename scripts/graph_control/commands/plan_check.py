"""plan check: every path a brief names outside fenced code exists in the worktree, and every line ref fits.

For each plan task with a brief at <run-dir>/tasks/<id>.md (a missing brief is
validate-briefs' job), each backticked token outside fenced code is a path
reference when it holds a `/`, none of `<>*?{}[]$|"'(),=@~`, no segment of dots
only, and does not start with `http`, `-`, `/`, `.graph/`, `.worktrees/` or
`.git/`. An optional
trailing `:<n>` or `:<n>-<m>` is a line ref. A reference is checked when it
exists under --root, or when it names a file (a suffix, no trailing `/`) in an
existing directory below the root that is not a run-dir or plugin file, so
branch names, packages, directories still to be made and other repos' paths
pass. A checked path that is missing is a problem unless a writable_paths glob of the
task or of any task it transitively depends on matches it (that task will
create it); a line ref past the file's line count is a problem.
Reads files only.
"""

import re
from argparse import ArgumentParser, Namespace
from pathlib import Path, PurePosixPath
from typing import Any

from .briefs import PLUGIN_ROOT, fence_mask

NAME = "plan"
HELP = "check plan briefs against a worktree: named paths exist and file:line refs fit"
TOKEN = re.compile(r"`([^`\s]+)`")
LINE_REF = re.compile(r"(.+?):(\d+)(?:-(\d+))?")
NOT_PATH_CHARS = frozenset("<>*?{}[]$|\"'(),=@~")
NOT_PATH_PREFIXES = ("http", "-", "/", ".graph/", ".worktrees/", ".git/")


def add_arguments(parser: ArgumentParser) -> None:
    steps = parser.add_subparsers(dest="plan_step", required=True)
    check = steps.add_parser("check", help="find stale paths and line refs in the run's briefs")
    check.add_argument("run_dir", type=Path, help="the run directory holding plan.json and tasks/")
    check.add_argument("--root", required=True, type=Path, help="the worktree the briefs refer to")


def path_ref(token: str) -> tuple[str, int | None] | None:
    if ("/" not in token or NOT_PATH_CHARS & set(token) or token.startswith(NOT_PATH_PREFIXES)
            or any(segment and not segment.strip(".") for segment in token.split("/"))):
        return None
    match = LINE_REF.fullmatch(token)
    if match is None:
        return token, None
    return match[1], max(int(match[2]), int(match[3] or 0))


def names_repo_file(ref: str, root: Path, elsewhere: tuple[Path, ...]) -> bool:
    path = PurePosixPath(ref)
    return (not ref.endswith("/") and bool(path.suffix) and path.parent != PurePosixPath(".")
            and (root / path.parent).is_dir() and not any((base / ref).exists() for base in elsewhere))


def owners(plan: Any) -> dict[str, Any]:
    from ..risk import matcher

    tasks = {task.id: task for task in plan.tasks}
    globs: dict[str, list[str]] = {}
    for level in plan.levels():
        for key in level:
            globs[key] = [*tasks[key].writable_paths,
                          *(glob for parent in tasks[key].depends_on for glob in globs[parent])]
    return {key: matcher(dict.fromkeys(paths)) for key, paths in globs.items()}


def brief_problems(name: str, lines: list[str], root: Path, owned: Any,
                   elsewhere: tuple[Path, ...]) -> tuple[list[str], int]:
    found, checked = [], 0
    for number, (line, fenced) in enumerate(zip(lines, fence_mask(lines)), 1):
        if fenced:
            continue
        for token in TOKEN.findall(line):
            ref = path_ref(token)
            if ref is None:
                continue
            path, last = root / ref[0], ref[1]
            exists = path.exists()
            if not exists and not names_repo_file(ref[0], root, elsewhere):
                continue
            checked += 1
            if not exists:
                if not owned.match(ref[0]):
                    found.append(f"{name}:{number}: `{token}` does not exist")
            elif last is not None and path.is_file():
                count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                if last > count:
                    found.append(f"{name}:{number}: `{token}` line {last} past end ({count} lines)")
    return found, checked


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load, require
    from ..plan import Plan

    plan = Plan.parse(load(args.run_dir / "plan.json"))
    owned = owners(plan)
    found: list[str] = []
    briefs = refs = 0
    for task in plan.tasks:
        path = args.run_dir / "tasks" / f"{task.id}.md"
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        problems, checked = brief_problems(f"tasks/{task.id}.md", lines, args.root, owned[task.id],
                                           (args.run_dir, PLUGIN_ROOT))
        found += problems
        briefs, refs = briefs + 1, refs + checked
    require(not found, "; ".join(found))
    return {"briefs": briefs, "refs": refs}
