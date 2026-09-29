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
