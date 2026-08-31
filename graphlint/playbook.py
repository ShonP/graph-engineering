"""Parse and validate playbook files."""

from __future__ import annotations

import re
from pathlib import Path

NODE_HEADING = re.compile(r"^##\s*node\s*:(.*)$")
KEY_LINE = re.compile(r"^(\w+):\s*(.*)$")
REQUIRED_KEYS = ("agent", "in", "out", "gate", "next")
LIST_KEYS = ("next", "skills")
GATE_TRUE = {"yes", "true"}
GATE_VALUES = {"yes", "no", "true", "false"}
END = "END"


def _coerce(key: str, value: str) -> object:
    if key == "gate":
        return value.strip().lower() in GATE_TRUE
    if key in LIST_KEYS:
        return [part.strip() for part in value.strip().strip("[]").split(",") if part.strip()]
    return value.strip()


def _read(path: Path) -> tuple[str | None, str | None]:
    """Return (text, error). Never raises on a path the linter was pointed at."""
    if not path.exists():
        return None, f"{path.name}: file is missing at {path}"
    if path.is_dir():
        return None, f"{path.name}: expected a file but found a directory at {path}"
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, f"{path.name}: file is not valid UTF-8"
    except OSError as exc:
        return None, f"{path.name}: file could not be read: {exc}"


def _check_required(nodes: list[dict], name: str) -> list[str]:
    errors: list[str] = []
    for node in nodes:
        for key in REQUIRED_KEYS:
            if key not in node:
                errors.append(f"{name}: node '{node['id']}' is missing required key '{key}'")
            elif node[key] == "" or node[key] == []:
                errors.append(f"{name}: node '{node['id']}' has an empty required key '{key}'")
    return errors


def _parse_text(text: str, name: str) -> tuple[list[dict], list[str]]:
    nodes: list[dict] = []
    errors: list[str] = []
    current: dict | None = None

    for lineno, line in enumerate(text.splitlines(), start=1):
        heading = NODE_HEADING.match(line)
        if heading:
            node_id = heading.group(1).strip()
            if not node_id or any(ch.isspace() for ch in node_id):
                errors.append(
                    f"{name}: line {lineno}: malformed node heading {line.strip()!r}; "
                    f"expected '## node: <id>'"
                )
                current = None
                continue
            current = {"id": node_id}
            nodes.append(current)
            continue
        if current is None or not line.strip():
            continue
        if line.startswith("#"):
            current = None
            continue
        match = KEY_LINE.match(line)
        if match is None:
            head = line.split(":", 1)[0].strip() if ":" in line else ""
            if head and not any(ch.isspace() for ch in head):
                errors.append(
                    f"{name}: line {lineno}: malformed key line {line.strip()!r}; "
                    f"expected 'key: value'"
                )
            continue
        key, value = match.group(1), match.group(2)
        if key == "id":
            errors.append(
                f"{name}: node '{current['id']}': 'id' is not a settable key; "
                f"the id comes from the '## node:' heading"
            )
            continue
        if key in current:
            errors.append(f"{name}: node '{current['id']}': duplicate key '{key}'")
        if key == "gate" and value.strip().lower() not in GATE_VALUES:
            errors.append(
                f"{name}: node '{current['id']}': gate must be one of "
                f"{sorted(GATE_VALUES)}, got {value.strip()!r}"
            )
        current[key] = _coerce(key, value)

    return nodes, errors + _check_required(nodes, name)


def parse_playbook(path: Path) -> tuple[list[dict], list[str]]:
    text, err = _read(path)
    if err is not None:
        return [], [err]
    return _parse_text(text, path.name)


def _reachable(entry: str, by_id: dict[str, dict]) -> set[str]:
    if entry not in by_id:
        return set()
    reachable = {entry}
    frontier = [entry]
    while frontier:
        node = by_id[frontier.pop()]
        for target in node.get("next", []):
            if target != END and target in by_id and target not in reachable:
                reachable.add(target)
                frontier.append(target)
    return reachable


def _index(nodes: list[dict], name: str) -> tuple[set[str], dict[str, dict], list[str]]:
    ids: set[str] = set()
    by_id: dict[str, dict] = {}
    errors: list[str] = []
    for node in nodes:
        node_id = node["id"]
        if node_id == END:
            errors.append(
                f"{name}: node id {END!r} is reserved as the terminator; rename the node"
            )
        if node_id in ids:
            errors.append(f"{name}: duplicate node id '{node_id}'; node ids must be unique")
        else:
            by_id[node_id] = node
        ids.add(node_id)
    return ids, by_id, errors


def validate_playbook(path: Path, known_agents: set[str]) -> list[str]:
    nodes, errors = parse_playbook(path)
    if not nodes:
        if not errors:
            errors.append(f"{path.name}: contains no nodes")
        return errors

    ids, by_id, index_errors = _index(nodes, path.name)
    errors += index_errors

    for node in nodes:
        agent = node.get("agent")
        if agent and agent not in known_agents:
            errors.append(f"{path.name}: node '{node['id']}' references unknown agent '{agent}'")
        for target in node.get("next", []):
            if target != END and target not in ids:
                errors.append(f"{path.name}: node '{node['id']}' points to unknown node '{target}'")

    entry = nodes[0]["id"]
    for node_id in sorted(ids - _reachable(entry, by_id)):
        errors.append(
            f"{path.name}: node '{node_id}' is unreachable from the entry node '{entry}'"
        )

    return errors
