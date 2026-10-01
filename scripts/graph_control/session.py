"""Which Claude Code session the status view reads. Stdlib only, like status.

Precedence: an explicit `--session <id>`, then the status-line stdin JSON the
host pipes to a `statusLine` command (`transcript_path`, then `session_id`),
then the newest top-level transcript of the project. A session that is named
but not found shows nothing: falling back to the newest would show another
session's agents. Transcripts live in `<config>/projects/<slug of root>/`,
config $CLAUDE_CONFIG_DIR or ~/.claude.
"""

import json
import os
import re
import select
from pathlib import Path
from typing import IO

SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
STDIN_WAIT, STDIN_MAX = 0.5, 64 * 1024


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def session_id(value: str) -> str:
    """A session id is a file name stem, never a path; ValueError otherwise."""
    if not isinstance(value, str) or not SESSION_ID.fullmatch(value):
        raise ValueError(f"session id must match {SESSION_ID.pattern}, got {value!r}")
    return value


def read_hint(stream: IO[str] | None) -> dict[str, str]:
    """`session_id` and `transcript_path` from the status-line JSON on stdin; {} when absent or unreadable.

    A terminal is never read, and a pipe that stays silent for STDIN_WAIT seconds is left alone, so a
    manual `--line` run never hangs.
    """
    if stream is None or stream.closed or stream.isatty():
        return {}
    try:
        ready = select.select([stream], [], [], STDIN_WAIT)[0] if _has_fd(stream) else [stream]
        data = json.loads(stream.read(STDIN_MAX)) if ready else None
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: data[key] for key in ("session_id", "transcript_path") if isinstance(data.get(key), str)}


def _has_fd(stream: IO[str]) -> bool:
    try:
        stream.fileno()
    except (OSError, ValueError):  # an in-memory stream cannot block
        return False
    return True


def locate(root: Path, session: str | None = None, hint: dict[str, str] | None = None) -> Path | None:
    """`<project>/<session id>` of the session to read, or None when there is none to show."""
    projects = config_dir() / "projects"
    project = projects / re.sub(r"[^A-Za-z0-9]", "-", str(root))
    hint = hint or {}
    if session is None and "transcript_path" in hint:
        transcript = Path(hint["transcript_path"])
        inside = transcript.suffix == ".jsonl" and transcript.resolve().is_relative_to(projects.resolve())
        return transcript.with_suffix("") if inside and transcript.is_file() else None
    if session is None and "session_id" in hint:
        session = hint["session_id"] if SESSION_ID.fullmatch(hint["session_id"]) else ""
    if session is not None:
        return project / session if session and (project / f"{session}.jsonl").is_file() else None
    try:
        mains = [(entry.stat().st_mtime, entry.path) for entry in os.scandir(project)
                 if entry.name.endswith(".jsonl") and entry.is_file()]
    except OSError:
        return None
    return Path(max(mains)[1]).with_suffix("") if mains else None
