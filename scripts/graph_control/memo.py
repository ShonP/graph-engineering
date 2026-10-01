"""Tree-keyed memo of configured check verdicts, so an unchanged tree never reruns a suite.

The file is <git common dir>/graph-engineering/checks-state.json:

  {"schema_version": 1, "entries": {<key>: <verdict>}}   at most MAX_ENTRIES, newest kept

It lives outside every worktree, so writing it never changes the dirty hash it
is keyed by, and linked worktrees share it (the key includes the root). A
missing, corrupt or foreign file reads as empty and an invalid entry never
replays: a memo may only skip work when it is sound. Stdlib only; the Stop hook
imports this module without PyYAML, so keep identity/state/common free of
third-party packages.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .common import choice, fingerprint, load, obj, require, version
from .identity import git, snapshot, timestamp
from .state import locked, write

DISABLE = "GRAPH_CHECKS_NO_MEMO"
MAX_ENTRIES = 200
MAX_TAIL = 4000


def disabled() -> bool:
    """The kill switch: any nonempty GRAPH_CHECKS_NO_MEMO means no lookup and no store."""
    return bool(os.environ.get(DISABLE))


def memo_path(root: Path) -> Path:
    root = Path(root).resolve(strict=True)
    common = Path(os.fsdecode(git(root, "rev-parse", "--git-common-dir")).strip())
    return (root / common).resolve() / "graph-engineering" / "checks-state.json"


def memo_key(root: Path, argv: Iterable[str], config_sha256: str) -> str:
    """SHA-256 of the candidate identity (revision, dirty tree incl. untracked), argv and config.

    `root` is the directory holding the config: the worktree root, or a package inside it. The tree
    identity is always the whole worktree's; a package adds its path, so two packages with identical
    configs never share a verdict, and a root-level key is unchanged."""
    directory = Path(root).resolve(strict=True)
    top = Path(os.fsdecode(git(directory, "rev-parse", "--show-toplevel")).strip()).resolve()
    source = snapshot(top, "candidate")
    key = {"root": source.root, "revision": source.revision, "dirty_sha256": source.dirty_sha256,
           "argv": list(argv), "config_sha256": config_sha256}
    if directory != top:
        key["dir"] = directory.relative_to(top).as_posix()
    return fingerprint(key)


def checked(value: Any) -> dict[str, Any]:
    """Validate one verdict; raise Invalid (a ValueError) when it cannot be replayed as recorded."""
    row = obj(value, "status exit_code observed_at tail argv")
    status, code = choice(row["status"], {"pass", "fail", "timeout"}), row["exit_code"]
    if status == "timeout":
        require(code is None, "a timeout has no exit code")
    else:
        require(type(code) is int and (code == 0) == (status == "pass"), "exit code contradicts the status")
    timestamp(row["observed_at"])
    require(isinstance(row["tail"], str) and len(row["tail"]) <= MAX_TAIL, f"tail must be text of <= {MAX_TAIL} chars")
    argv = row["argv"]
    require(isinstance(argv, list) and bool(argv) and all(isinstance(a, str) and a for a in argv),
            "argv must be a nonempty array of nonempty strings")
    return row


def verdict(status: str, exit_code: int | None, tail: str, argv: Iterable[str]) -> dict[str, Any]:
    return checked({"status": status, "exit_code": exit_code, "observed_at": datetime.now(timezone.utc).isoformat(),
                    "tail": tail[-MAX_TAIL:], "argv": list(argv)})


def _entries(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = obj(load(path), "schema_version entries")
        version(data["schema_version"])
        require(isinstance(data["entries"], dict), "entries must be an object")
    except (ValueError, OSError):
        return {}
    result = {}
    for key, value in data["entries"].items():
        try:
            result[key] = checked(value)
        except ValueError:
            continue
    return result


def lookup(root: Path, key: str) -> dict[str, Any] | None:
    return _entries(memo_path(root)).get(key)


def store(root: Path, key: str, value: Any) -> None:
    row = checked(value)
    path = memo_path(root)
    with locked(path):
        entries = _entries(path)
        entries[key] = row
        newest = sorted(entries.items(), key=lambda item: timestamp(item[1]["observed_at"]), reverse=True)
        write(path, {"schema_version": 1, "entries": dict(newest[:MAX_ENTRIES])})
