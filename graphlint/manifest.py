"""Validate the plugin's two manifest files."""

from __future__ import annotations

import json
import re
from pathlib import Path

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PLUGIN_NAME = "graph-engineering"


def _load(path: Path, errors: list[str]) -> dict | None:
    if not path.exists():
        errors.append(f"{path.name} is missing at {path}")
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name} is not valid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path.name} must be a JSON object, got {type(data).__name__}")
        return None
    return data


def validate_manifest(repo_root: Path) -> list[str]:
    errors: list[str] = []
    base = repo_root / ".claude-plugin"

    plugin = _load(base / "plugin.json", errors)
    if plugin is not None:
        for field in ("name", "description", "version"):
            if not plugin.get(field):
                errors.append(f"plugin.json is missing required field '{field}'")
        if plugin.get("name") != PLUGIN_NAME:
            errors.append(f"plugin.json name must be '{PLUGIN_NAME}', got {plugin.get('name')!r}")
        version = plugin.get("version", "")
        if version and not (isinstance(version, str) and SEMVER.match(version)):
            errors.append(f"plugin.json version must be semver x.y.z, got {version!r}")

    market = _load(base / "marketplace.json", errors)
    if market is not None:
        plugins = market.get("plugins", [])
        if isinstance(plugins, list):
            names = [p.get("name") if isinstance(p, dict) else None for p in plugins]
        else:
            names = []
        if PLUGIN_NAME not in names:
            errors.append(f"marketplace.json must list a plugin named '{PLUGIN_NAME}', found {names}")
        owner = market.get("owner")
        owner_name = owner.get("name") if isinstance(owner, dict) else None
        if not owner_name:
            errors.append("marketplace.json is missing owner.name")

    return errors
