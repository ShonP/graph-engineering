"""Bind hooks to an authorized candidate, including linked Git worktrees."""
import json
import os
from pathlib import Path
import subprocess
import sys


def git_path(directory: Path, flag: str) -> Path | None:
    result = subprocess.run(['git', '-C', str(directory), 'rev-parse', flag], capture_output=True, text=True, check=False)
    if result.returncode:
        return None
    path = Path(result.stdout.strip())
    return (directory / path).resolve() if not path.is_absolute() else path.resolve()


def project_root(payload: dict, original: Path, *, touched: bool = False) -> Path:
    original = original.resolve()
    tool_input = payload.get('tool_input')
    raw = (tool_input.get('file_path') if isinstance(tool_input, dict) else None) if touched else payload.get('cwd')
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        return original
    candidate = Path(raw).resolve()
    if touched:
        candidate = candidate.parent
    if not candidate.is_dir():
        return original
    # Resolve linked worktrees before containment: they may live inside the
    # original checkout as well as alongside it.
    common = git_path(original, '--git-common-dir')
    if common and common == git_path(candidate, '--git-common-dir'):
        root = git_path(candidate, '--show-toplevel')
        if root:
            return root
    if candidate == original or candidate.is_relative_to(original):
        # Multi-repository workspaces have no Git root of their own. Select the
        # contained candidate repo instead of silently checking the workspace.
        root = git_path(candidate, '--show-toplevel')
        if common is None and root and root.is_relative_to(original):
            return root
        return original
    if not touched and git_path(candidate, '--show-toplevel'):
        raise ValueError('Hook cwd is a different repository; set CLAUDE_PROJECT_DIR to the authorized candidate. No checks ran.')
    return original


def within(root: Path, start: Path) -> Path | None:
    """`start` as a directory inside `root`: itself, or its place in root's worktree when it sits in
    another worktree of the same repository (a package CLAUDE_PROJECT_DIR while Claude works in a
    linked worktree). None when it is neither."""
    start = start.resolve()
    if start.is_relative_to(root):
        return start if start.is_dir() else None
    common = git_path(root, '--git-common-dir')
    if not start.is_dir() or common is None or common != git_path(start, '--git-common-dir'):
        return None
    prefix = subprocess.run(['git', '-C', str(start), 'rev-parse', '--show-prefix'],
                            capture_output=True, text=True, check=False).stdout.strip()
    mapped = (root / prefix).resolve()
    return mapped if prefix and mapped.is_relative_to(root) and mapped.is_dir() else None


def checks_dir(root: Path, starts: list[Path], config: str) -> Path | None:
    """The directory holding the `config` nearest the first start that has one, walking up to `root` and
    never above it: the nearest config wins, the way linters find theirs, so a package in a monorepo
    keeps its own checks. `root` itself is the last start."""
    for start in (*starts, root):
        here = within(root, start)
        while here is not None:
            if (here / config).is_file():
                return here
            here = here.parent if here != root else None
    return None


def main() -> int:
    try:
        try:
            payload = json.loads(os.environ.get('HOOK_INPUT', '{}'))
        except json.JSONDecodeError:
            payload = {}  # No candidate hint; still execute the bound project's gate.
        if not isinstance(payload, dict):
            payload = {}
        root = project_root(payload, Path(os.environ['CLAUDE_PROJECT_DIR']), touched='--touched' in sys.argv)
        print(root)
        return 0
    except (ValueError, OSError) as exc:
        print(f'Graph Engineering: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
