"""Skill receipt: every REQUIRED skill a dispatch named appears in the child's `skills_loaded:` line.

Names compare by the part after the last colon, so `graph-engineering:bruno` and
`bruno` are one skill. A bare loaded name that is also a host built-in proves
nothing: the host may have resolved it to its own skill of that name (bare
`security-review` did, in 7 of 7 measured reviews), so it counts as not loaded.
Pure: no I/O.
"""

import re

from .common import require

# Witness: the unprefixed skills a Claude Code 2.1.286 session listed on
# 2026-10-01, minus the owner's ~/.claude/skills. The host ships these, so a
# bare one may be the host's own. One list, for any check that meets bare names.
HOST_BUILTINS = frozenset({
    "artifact-capabilities", "artifact-design", "artifact-diagramming", "claude-api", "claude-in-chrome",
    "code-review", "dataviz", "fewer-permission-prompts", "init", "keybindings-help", "loop", "run",
    "schedule", "security-review", "simplify", "update-config", "workflow-authoring",
})
NAME = re.compile(r"(?:[A-Za-z0-9][\w.-]*:)*[A-Za-z0-9][\w.-]*")
PREFIX = "skills_loaded:"


def names(value: str) -> tuple[str, ...]:
    """Comma-separated names, trimmed, empties dropped, first occurrence kept.

    The child's whole return line is accepted too: a leading `skills_loaded:` is dropped."""
    value = value.strip()
    value = value[len(PREFIX):] if value.startswith(PREFIX) else value
    result = []
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        require(NAME.fullmatch(item) is not None, f"not a skill name: {item!r}")
        if item not in result:
            result.append(item)
    return tuple(result)


def bare(name: str) -> str:
    return name.rpartition(":")[2]


def missing(required: tuple[str, ...], loaded: tuple[str, ...]) -> list[str]:
    """The required names, in order, that the loaded names do not prove."""
    proven = {bare(name) for name in loaded if ":" in name or name not in HOST_BUILTINS}
    return [name for name in required if bare(name) not in proven]
