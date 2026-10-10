"""Which skills a subagent's transcript shows it loading. Stdlib only; reads one file.

A subagent transcript is `<config>/projects/<slug>/<session>/subagents/agent-<id>.jsonl`,
one JSON object per line with the content under `message.content` (witness:
tests/graph_control/fixtures/sessions/README.md). An invoked skill is an assistant
`tool_use` named `Skill` with `input.skill`; a preloaded one is a `<command-name>`
tag in user content; a repo-local skill loaded by path is a `Read` of its SKILL.md.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .common import require
from .session import config_dir

AGENT_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
COMMAND_NAME = re.compile(r"<command-name>\s*([^<\s]+)\s*</command-name>")
LOCAL_SKILL = re.compile(r"/\.claude/skills/([^/]+)/SKILL\.md$")


def subagent_transcript(agent_id: str) -> Path | None:
    """The transcript of subagent `agent_id` under any project, or None; Invalid on a malformed id.

    The engine runs from the repo root and its children may run in worktrees, so every project
    is searched. Two matches (the same id in two projects) give the first in path order. A match
    that resolves outside `<config>/projects`, such as a symlink, is skipped."""
    require(isinstance(agent_id, str) and AGENT_ID.fullmatch(agent_id) is not None,
            f"agent id must match {AGENT_ID.pattern}, got {agent_id!r}")
    projects = config_dir() / "projects"
    root = projects.resolve()
    for path in sorted(projects.glob(f"*/*/subagents/agent-{agent_id}.jsonl")):
        if path.resolve().is_relative_to(root) and path.is_file():
            return path
    return None


def observed_skills(path: Path) -> frozenset[str]:
    """Lowercased skill names the transcript shows loading; an errored tool call loads nothing."""
    calls: dict[str, str] = {}
    failed: set[str] = set()
    preloaded: set[str] = set()
    for row in _rows(path):
        kind, content = row.get("type"), (row.get("message") or {}).get("content")
        if kind == "user" and isinstance(content, str):
            preloaded.update(COMMAND_NAME.findall(content))
        for block in content if isinstance(content, list) else ():
            if not isinstance(block, dict):
                continue
            if kind == "user" and block.get("type") == "text" and isinstance(block.get("text"), str):
                preloaded.update(COMMAND_NAME.findall(block["text"]))
            elif kind == "user" and block.get("type") == "tool_result" and block.get("is_error") is True:
                failed.add(block.get("tool_use_id"))
            elif kind == "assistant" and block.get("type") == "tool_use":
                name = _loaded_by(block)
                if name:
                    calls[block.get("id")] = name
    names = preloaded | {name for call, name in calls.items() if call not in failed}
    return frozenset(name.lower() for name in names)


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and isinstance(row.get("message") or {}, dict):
                yield row


def _loaded_by(block: dict[str, Any]) -> str | None:
    tool, given = block.get("name"), block.get("input")
    if not isinstance(given, dict):
        return None
    if tool == "Skill" and isinstance(given.get("skill"), str):
        return given["skill"].strip() or None
    if tool == "Read" and isinstance(given.get("file_path"), str):
        match = LOCAL_SKILL.search(given["file_path"])
        return match.group(1) if match else None
    return None
