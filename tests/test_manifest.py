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


def write_raw(root: Path, plugin_text: str | None, marketplace_text: str | None) -> Path:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    if plugin_text is not None:
        (root / ".claude-plugin/plugin.json").write_text(plugin_text)
    if marketplace_text is not None:
        (root / ".claude-plugin/marketplace.json").write_text(marketplace_text)
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


# --- Finding 1: malformed input must be reported, never raised ---


def test_plugin_json_top_level_list_is_an_error(tmp_path):
    write_raw(tmp_path, json.dumps(["not", "a", "dict"]), json.dumps(VALID_MARKET))
    errors = validate_manifest(tmp_path)
    assert any("plugin.json" in e for e in errors)


def test_plugin_version_as_number_is_an_error(tmp_path):
    write(tmp_path, {**VALID_PLUGIN, "version": 1}, VALID_MARKET)
    errors = validate_manifest(tmp_path)
    assert any("version" in e for e in errors)


def test_marketplace_plugins_as_strings_is_an_error(tmp_path):
    bad = {**VALID_MARKET, "plugins": ["graph-engineering"]}
    write(tmp_path, VALID_PLUGIN, bad)
    errors = validate_manifest(tmp_path)
    assert any("graph-engineering" in e for e in errors)


def test_marketplace_plugins_not_a_list_is_an_error(tmp_path):
    bad = {**VALID_MARKET, "plugins": "x"}
    write(tmp_path, VALID_PLUGIN, bad)
    errors = validate_manifest(tmp_path)
    assert any("graph-engineering" in e for e in errors)


def test_marketplace_owner_as_string_is_an_error(tmp_path):
    bad = {**VALID_MARKET, "owner": "Shon"}
    write(tmp_path, VALID_PLUGIN, bad)
    errors = validate_manifest(tmp_path)
    assert any("owner" in e for e in errors)


def test_marketplace_json_top_level_list_is_an_error(tmp_path):
    write_raw(tmp_path, json.dumps(VALID_PLUGIN), json.dumps(["not", "a", "dict"]))
    errors = validate_manifest(tmp_path)
    assert any("marketplace.json" in e for e in errors)


# --- Finding 2: checks neutered by mutation testing must have direct coverage ---


def test_plugin_name_wrong_is_an_error(tmp_path):
    bad = {**VALID_PLUGIN, "name": "wrong-name"}
    write(tmp_path, bad, VALID_MARKET)
    errors = validate_manifest(tmp_path)
    assert any("name must be" in e for e in errors)


def test_plugin_missing_description_is_an_error(tmp_path):
    bad = {"name": "graph-engineering", "version": "0.1.0"}
    write(tmp_path, bad, VALID_MARKET)
    errors = validate_manifest(tmp_path)
    assert any("description" in e for e in errors)


def test_missing_marketplace_json_is_an_error(tmp_path):
    write(tmp_path, VALID_PLUGIN, None)
    errors = validate_manifest(tmp_path)
    assert any("marketplace.json" in e and "missing" in e for e in errors)


def test_marketplace_owner_missing_name_is_an_error(tmp_path):
    bad = {**VALID_MARKET, "owner": {}}
    write(tmp_path, VALID_PLUGIN, bad)
    errors = validate_manifest(tmp_path)
    assert any("owner.name" in e for e in errors)


def test_plugin_json_malformed_json_is_an_error(tmp_path):
    write_raw(tmp_path, "{not valid json", json.dumps(VALID_MARKET))
    errors = validate_manifest(tmp_path)
    assert any("not valid JSON" in e for e in errors)
