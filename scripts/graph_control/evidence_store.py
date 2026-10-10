"""Doctor checks for the optional `uxEvidence.store`: UX evidence media kept outside git.

The store names a repo's own push, pull and link commands. These checks never run
them: a configured command is the repo's to run, and doctor stays read-only. They
check the block's shape, that each command's program resolves (on PATH, or as a
repo-relative file), and that git ignores the media under `uxEvidence.path`, so a
capture cannot be committed by accident. The only process started is
`git check-ignore`.
"""

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

MEDIA = ("png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "mov")
KEYS = ("push", "pull", "link")
REQUIRED = ("push", "pull")
DEFAULT_PATH = "docs/ux/changes"
SHAPE_FIX = "write `uxEvidence.store` as `{push: <command>, pull: <command>, link: <command>}`, or leave all three empty"

Row = tuple[str, str, str, str]  # level, id, message, fix


def check(profile: dict[str, Any], root: Path) -> list[Row]:
    """Findings for `uxEvidence.store`; none when the store is empty (the media is committed)."""
    evidence = profile.get("uxEvidence")
    store = evidence.get("store") if isinstance(evidence, dict) else None
    if not store:
        return []
    if not isinstance(store, dict):
        return [("warn", "ux-store-shape", f"uxEvidence.store is {store!r}; it must be a mapping of commands", SHAPE_FIX)]
    commands = {key: store.get(key) for key in KEYS}
    if not any(isinstance(value, str) and value.strip() for value in commands.values()):
        return []
    rows: list[Row] = []
    missing = [key for key in REQUIRED if not (isinstance(commands[key], str) and commands[key].strip())]
    if missing:
        rows.append(("warn", "ux-store-shape", f"uxEvidence.store is set but has no {' or '.join(missing)} command, "
                     "so agents cannot keep the media out of git", SHAPE_FIX))
    unresolved = [f"uxEvidence.store.{key} ({_program(value) or value!r})" for key, value in commands.items()
                  if isinstance(value, str) and value.strip() and not _resolves(value, root)]
    if unresolved:
        rows.append(("warn", "ux-store-command", f"evidence store commands name a program that is not on PATH or "
                     f"in the repo: {', '.join(unresolved)}", "install the CLI, or correct the command in the profile"))
    path = evidence.get("path") if isinstance(evidence.get("path"), str) and evidence["path"].strip() else DEFAULT_PATH
    unignored = _unignored(root, path.strip().rstrip("/"))
    if unignored:
        rows.append(("warn", "ux-store-unignored", f"uxEvidence.store is set, but git does not ignore media under "
                     f"{path}: {', '.join('.' + ext for ext in unignored)}",
                     f"add `{path.rstrip('/')}/**/*.<ext>` lines to .gitignore for each listed type, so a capture "
                     "cannot be committed"))
    return rows


def _program(command: str) -> str:
    try:
        words = shlex.split(command)
    except ValueError:
        return ""
    return words[0] if words else ""


def _resolves(command: str, root: Path) -> bool:
    program = _program(command)
    return bool(program) and (shutil.which(program) is not None or (root / program).is_file())


def _unignored(root: Path, path: str) -> list[str]:
    """Media extensions git would not ignore under `path`; [] when git cannot answer."""
    probes = {f"{path}/graph-doctor-probe/capture.{ext}": ext for ext in MEDIA}
    try:
        result = subprocess.run(["git", "-C", str(root), "check-ignore", "--", *probes],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode not in (0, 1):  # 128: not a repository, or a path outside it
        return []
    ignored = set(result.stdout.splitlines())
    return [ext for probe, ext in probes.items() if probe not in ignored]
