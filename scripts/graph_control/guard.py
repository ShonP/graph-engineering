"""Pure PreToolUse(Agent|Task) policy: which subagent types and models a repo allows.

decide() reads only the hook payload and the parsed profile. It never touches
files; the guard-agent command owns I/O. No `policy:` block means no opinion.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

PREFIX = "graph-engineering:"
DEFAULT_ROLES = {"planner": "opus", "ux-designer": "opus", "implementer": "opus", "reviewer": "opus",
                 "implementer-simple": "sonnet", "researcher": "sonnet", "qa": "sonnet", "retro": "sonnet"}
DEFAULT_NEVER = ("haiku", "fable")
DEFAULT_BLOCK_TYPES = ("general-purpose",)
# The host runs general-purpose when an Agent call names no subagent_type.
HOST_FALLBACK_TYPE = "general-purpose"
# localAgents keys name a playbook leg or a role; both resolve to a role.
LEG_ROLES = {"plan": "planner", "design": "ux-designer", "implement": "implementer", "review": "reviewer",
             "research": "researcher", "verify": "qa"}
OVERRIDE = re.compile(r"^policy-override: (.+)$", re.MULTILINE)
ROSTER = "graph-engineering:implementer, implementer-simple, reviewer, researcher, qa, planner, ux-designer, retro"


@dataclass(frozen=True)
class Decision:
    kind: str  # none | deny | rewrite | override
    output: dict[str, Any] | None = None
    ledger_line: str | None = None


def _strip(name: str) -> str:
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


def _names(value: Any, default: tuple[str, ...]) -> set[str]:
    if not isinstance(value, list):
        return set(default)
    return {item for item in value if isinstance(item, str)}


def _roles(policy: dict[str, Any]) -> dict[str, str]:
    roles = dict(DEFAULT_ROLES)
    custom = policy.get("roles")
    if isinstance(custom, dict):
        roles.update({key: value for key, value in custom.items() if isinstance(key, str) and isinstance(value, str)})
    return roles


def _local_roles(local_agents: Any) -> dict[str, str]:
    """Map each local agent name to the role its localAgents key names (string or stack mapping)."""
    result: dict[str, str] = {}
    if not isinstance(local_agents, dict):
        return result
    for key, value in local_agents.items():
        names = value.values() if isinstance(value, dict) else [value]
        for name in names:
            if isinstance(key, str) and isinstance(name, str):
                result.setdefault(_strip(name), LEG_ROLES.get(key, key))
    return result


def _field(value: Any) -> str:
    """One ledger field: whitespace and control characters collapse so a value cannot forge a line."""
    return " ".join("".join(ch if ch.isprintable() else " " for ch in str(value)).split())[:200]


def _hook(decision: str, reason: str, updated: dict[str, Any] | None = None) -> dict[str, Any]:
    output = {"hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}
    if updated is not None:
        output["updatedInput"] = updated
    return {"hookSpecificOutput": output}


def decide(payload: dict[str, Any], profile: dict[str, Any] | None, *, now: datetime | None = None) -> Decision:
    policy = profile.get("policy") if isinstance(profile, dict) else None
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(policy, dict) or not isinstance(tool_input, dict):
        return Decision("none")
    raw_type = tool_input.get("subagent_type")
    agent_type = raw_type if isinstance(raw_type, str) and raw_type.strip() else HOST_FALLBACK_TYPE
    model = tool_input.get("model")
    prompt = tool_input.get("prompt")
    override = OVERRIDE.search(prompt) if isinstance(prompt, str) else None
    if override:
        stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        line = (f"- {stamp} policy-override: type={_field(agent_type)} model={_field(model or 'default')} "
                f"agent={_field(payload.get('agent_id') or 'main')} reason={_field(override.group(1))}")
        return Decision("override", ledger_line=line)
    name = _strip(agent_type)
    roles = _roles(policy)
    role = name if name in roles else _local_roles(profile.get("localAgents")).get(name)
    tier = roles.get(role) if role else None
    if name in _names(policy.get("block_types"), DEFAULT_BLOCK_TYPES):
        return Decision("deny", _hook("deny", f"graph-engineering policy: subagent type {name} is blocked in this "
                                              f"repo. Dispatch a roster agent ({ROSTER}), or add a line "
                                              "policy-override: <reason> to the prompt."))
    if isinstance(model, str) and model in _names(policy.get("never"), DEFAULT_NEVER):
        hint = f"Omit model or use {tier}." if tier else "Omit model."
        return Decision("deny", _hook("deny", f"graph-engineering policy: model {model} is not allowed here "
                                              f"(policy.never). {hint}"))
    if tier and model != tier:
        return Decision("rewrite", _hook("allow", f"graph-engineering policy: {name} runs on {tier} (policy.roles)",
                                         {**tool_input, "model": tier}))
    return Decision("none")
