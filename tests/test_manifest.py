from pathlib import Path
import json
import pytest
from graphlint.manifest import validate_manifest


def write(root: Path, plugin: dict | None, marketplace: dict | None) -> Path:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    if plugin is not None:
        (root / ".claude-plugin/plugin.json").write_text(json.dumps(plugin))
    if marketplace is not None:
        (root / ".claude-plugin/marketplace.json").write_text(json.dumps(marketplace))
    return root


VALID_PLUGIN = {"name": "graph-engineering", "description": "d", "version": "0.1.0"}
VALID_MARKET = {
    "name": "graph-engineering",
    "owner": {"name": "Shon Pazarker"},
    "plugins": [{"name": "graph-engineering", "source": "./", "description": "d"}],
}


def test_valid_manifest_has_no_errors(tmp_path):
    write(tmp_path, VALID_PLUGIN, VALID_MARKET)
    assert validate_manifest(tmp_path) == []


def test_missing_plugin_json_is_an_error(tmp_path):
    write(tmp_path, None, VALID_MARKET)
    errors = validate_manifest(tmp_path)
    assert any("plugin.json" in e and "missing" in e for e in errors)


def test_version_must_be_semver(tmp_path):
    write(tmp_path, {**VALID_PLUGIN, "version": "v1"}, VALID_MARKET)
    assert any("version" in e for e in validate_manifest(tmp_path))


def test_marketplace_must_list_the_plugin_by_name(tmp_path):
    bad = {**VALID_MARKET, "plugins": [{"name": "other", "source": "./", "description": "d"}]}
    write(tmp_path, VALID_PLUGIN, bad)
    assert any("graph-engineering" in e for e in validate_manifest(tmp_path))
