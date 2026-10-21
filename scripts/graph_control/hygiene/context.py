from collections.abc import Iterable
from pathlib import Path

import yaml

from . import Context, Finding, Row

ID = "context"
MODES = frozenset({"staged", "base", "tracked", "doctor"})
QUICK = True
DIFF_MODES = frozenset({"staged", "base"})
FINDING = "context-budget"
BUILTIN = "always-on"
BUILTIN_TOTAL = 24000
BUILTIN_FILE = 8000
ROOT_FILES = ("CLAUDE.md", "AGENTS.md")
RULES = Path(".claude") / "rules"
FENCE = "---"
BUILTIN_FIX = ("trim it, or give a rule pack `paths:` frontmatter so it loads only for matching files; "
               "hygiene.context.builtin false turns this budget off")


def _sizes(root: Path, paths: Iterable[Path]) -> list[tuple[str, int]]:
    seen, sizes = set(), []
    for path in paths:
        if not path.is_file():
            continue
        target = path.resolve()
        if target in seen:
            continue
        seen.add(target)
        sizes.append((path.relative_to(root).as_posix(), target.stat().st_size))
    return sizes


def _scoped(path: Path) -> bool:
    try:
        lines = path.read_bytes().decode("utf-8", "replace").splitlines()
    except OSError:
        return False
    if not lines or lines[0].strip() != FENCE:
        return False
    end = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == FENCE), None)
    if end is None:
        return False
    try:
        front = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError:
        return False
    return isinstance(front, dict) and "paths" in front


def _always_on(root: Path) -> list[Path]:
    rules = sorted(path for path in (root / RULES).glob("*.md") if path.is_file() and not _scoped(path))
    return [root / name for name in ROOT_FILES] + rules


def _relation(size: int, cap: int) -> str:
    return "over" if size > cap else f"at {size * 100 // cap}% of"


def _near(size: int, cap: int, pct: int) -> bool:
    return size * 100 >= cap * pct


def _total(ident: str, sizes: list[tuple[str, int]], cap: int, pct: int, level: str, fix: str) -> list[Finding]:
    total = sum(size for _, size in sizes)
    if not _near(total, cap, pct):
        return []
    path, largest = max(sizes, key=lambda item: item[1])
    level = level if total > cap else "warn"
    return [Finding(level, FINDING, f"context budget {ident} is {total} bytes, {_relation(total, cap)} its "
                    f"{cap}-byte cap; largest file {path} ({largest} bytes)", fix, path)]


def _in_scope(ctx: Context, sizes: list[tuple[str, int]]) -> bool:
    if ctx.mode not in DIFF_MODES:
        return True
    changed = {item.path for item in ctx.files}
    return any(path in changed for path, _ in sizes)


def _builtin(ctx: Context) -> list[Finding]:
    sizes, pct = _sizes(ctx.root, _always_on(ctx.root)), ctx.config.context.warn_pct
    if not _in_scope(ctx, sizes):
        return []
    per_file = [Finding("warn", FINDING, f"context budget {BUILTIN} file {path} is {size} bytes, "
                        f"{_relation(size, BUILTIN_FILE)} the {BUILTIN_FILE}-byte per-file cap", BUILTIN_FIX, path)
                for path, size in sizes if _near(size, BUILTIN_FILE, pct)]
    return _total(BUILTIN, sizes, BUILTIN_TOTAL, pct, "warn", BUILTIN_FIX) + per_file


def _profile(ctx: Context) -> list[Finding]:
    found = []
    for budget in ctx.config.context.budgets:
        paths = sorted({path for glob in budget.globs for path in ctx.root.glob(glob)})
        fix = f"trim the files budget {budget.id} matches, or raise its max_bytes in hygiene.context.budgets"
        sizes = _sizes(ctx.root, paths)
        if _in_scope(ctx, sizes):
            found += _total(budget.id, sizes, budget.max_bytes, ctx.config.context.warn_pct, "error", fix)
    return found


def run(ctx: Context) -> list[Finding]:
    return (_builtin(ctx) if ctx.config.context.builtin else []) + _profile(ctx)


def doctor(ctx: Context) -> list[Row]:
    return [(finding.level, finding.id, finding.message, finding.fix) for finding in run(ctx)]
