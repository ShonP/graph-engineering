"""Validate agent definition files."""

from __future__ import annotations

from pathlib import Path

import yaml

ALLOWED_MODELS = {"opus", "sonnet"}
REQUIRED_FIELDS = ("name", "description", "tools", "model")
EM_DASH = "—"


def split_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """Return (frontmatter, body, error)."""
    if not text.startswith("---\n"):
        return None, text, "file does not start with a YAML frontmatter block"
    _, _, rest = text.partition("---\n")
    raw, sep, body = rest.partition("\n---")
    if not sep:
        return None, text, "frontmatter block is not closed with ---"
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return None, body, f"frontmatter is not valid YAML: {exc}"
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, body, "frontmatter must be a mapping"
    return data, body, None


def validate_agent(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text()
    front, body, err = split_frontmatter(text)
    if err:
        return [f"{path.name}: {err}"]
    assert front is not None

    for field in REQUIRED_FIELDS:
        if not front.get(field):
            errors.append(f"{path.name}: missing required field '{field}'")

    name = front.get("name")
    if name is not None:
        if not isinstance(name, str):
            errors.append(f"{path.name}: name must be a string, got {type(name).__name__}")
        elif name != path.stem:
            errors.append(f"{path.name}: name {name!r} must match the filename stem {path.stem!r}")

    tools = front.get("tools")
    if tools is not None and not isinstance(tools, list):
        errors.append(f"{path.name}: tools must be a list, got {type(tools).__name__}")

    model = front.get("model")
    if model is not None:
        if not isinstance(model, str):
            errors.append(f"{path.name}: model must be a string, got {type(model).__name__}")
        elif model not in ALLOWED_MODELS:
            errors.append(
                f"{path.name}: model {model!r} is not allowed; use one of {sorted(ALLOWED_MODELS)} "
                f"(haiku is banned by standing policy)"
            )

    if EM_DASH in text:
        errors.append(f"{path.name}: contains an em dash, which the house rule bans")

    return errors


def agent_names(agents_dir: Path) -> set[str]:
    return {p.stem for p in sorted(agents_dir.glob("*.md"))}
