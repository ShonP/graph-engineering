"""surfaces: the report-only sweep. A directory matching surfaces.roots that holds tracked files is
proposed for deletion when its last commit is idleDays or more old and fewer than minCallers tracked
files outside it mention its path or its basename as a whole word. callers is an upper bound: a
basename that is a common word also counts its ordinary uses. The proposals go to
.graph/sweep-<UTC date>.md under the root; nothing else is written and nothing is removed."""

import subprocess
from datetime import timezone
from pathlib import PurePosixPath

from . import Context, Finding
from ..risk import matcher
from .docs_age import DAY, _last_commits

ID = "surfaces"
MODES = frozenset({"sweep"})
QUICK = False
SMALL = 3
HEADER = "| path | idle days | callers | lines | proposal |\n|-|-|-|-|-|"
FIX = "review the rows and delete what is dead in its own PR; the sweep deletes nothing"
NO_ROOTS_FIX = "set hygiene.surfaces.roots to the globs of directories that may go idle, such as tools/*"


def _dirs(ctx: Context) -> dict[str, list[str]]:
    match = matcher(ctx.config.surfaces.roots)
    members: dict[str, list[str]] = {}
    for item in ctx.files:
        for parent in PurePosixPath(item.path).parents:
            folder = parent.as_posix()
            if folder != "." and match.match(folder):
                members.setdefault(folder, []).append(item.path)
    return members


def _grep(ctx: Context, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(ctx.root), "--literal-pathspecs", "grep", "--cached", "-I", "-z", *args],
                            capture_output=True, text=True)
    return result.stdout


def _lines(ctx: Context, folders: list[str]) -> dict[str, int]:
    if not folders:
        return {}
    output = _grep(ctx, "-c", "-e", "", "--", *folders)
    pairs = (line.split("\0") for line in output.splitlines())
    return {path: int(count) for path, count in pairs}


def _callers(ctx: Context, folder: str) -> int:
    output = _grep(ctx, "-l", "-F", "-w", "-e", folder, "-e", PurePosixPath(folder).name)
    return sum(1 for path in output.split("\0") if path and not path.startswith(f"{folder}/"))


def _idle(ctx: Context, folders: list[str]) -> dict[str, int]:
    stamps = _last_commits(ctx, folders)
    now = int(ctx.now.timestamp())
    idle = {}
    for folder in folders:
        latest = max((stamp for path, stamp in stamps.items() if path.startswith(f"{folder}/")), default=None)
        if latest is not None:
            idle[folder] = (now - latest) // DAY
    return idle


def _report(ctx: Context, rows: list[str], small: int) -> str:
    surfaces = ctx.config.surfaces
    roots = ", ".join(surfaces.roots) or "none"
    return (f"# Surface sweep {ctx.now.astimezone(timezone.utc):%Y-%m-%d}\n\n"
            f"Report only: nothing was deleted. roots: {roots}; idleDays {surfaces.idleDays}; "
            f"minCallers {surfaces.minCallers}. callers is an upper bound: a basename that is a common word "
            f"also counts its ordinary uses.\n\n{HEADER}\n" + "".join(f"{row}\n" for row in rows)
            + f"\nsmall_files: {small}\n")


def run(ctx: Context) -> list[Finding]:
    surfaces = ctx.config.surfaces
    members = _dirs(ctx)
    folders = sorted(members)
    text = {item.path for item in ctx.files if not item.binary}
    counts = _lines(ctx, folders)
    under = {path for paths in members.values() for path in paths} & text
    small = sum(1 for path in under if counts.get(path, 0) <= SMALL)
    rows = []
    for folder, days in sorted(_idle(ctx, folders).items()):
        if days < surfaces.idleDays:
            continue
        callers = _callers(ctx, folder)
        if callers < surfaces.minCallers:
            lines = sum(counts.get(path, 0) for path in members[folder])
            rows.append(f"| {folder} | {days} | {callers} | {lines} | delete |")
    relative = f".graph/sweep-{ctx.now.astimezone(timezone.utc):%Y-%m-%d}.md"
    target = ctx.root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_report(ctx, rows, small), encoding="utf-8")
    findings = [Finding("info", "sweep", str(target), FIX, relative)]
    if not surfaces.roots:
        findings.append(Finding("info", "sweep-no-roots", "hygiene.surfaces.roots is empty, so the sweep "
                                "checked no directory", NO_ROOTS_FIX))
    return findings
