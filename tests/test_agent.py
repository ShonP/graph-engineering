from pathlib import Path
from graphlint.agent import validate_agent, agent_names

VALID = """---
name: reviewer
description: Reads a diff once and reports findings.
tools: [Read, Grep, Glob, Bash]
model: opus
---

You are a read-only reviewer.
"""

INVALID_LIST_FRONTMATTER = """---
- a
- b
---

Body text.
"""

FALSY_FRONTMATTER = """---
false
---

Body text.
"""


def write_agent(tmp_path: Path, filename: str, body: str) -> Path:
    path = tmp_path / filename
    path.write_text(body)
    return path


def test_valid_agent_has_no_errors(tmp_path):
    assert validate_agent(write_agent(tmp_path, "reviewer.md", VALID)) == []


def test_name_must_match_filename(tmp_path):
    path = write_agent(tmp_path, "code-reviewer.md", VALID)
    assert any("filename" in e for e in validate_agent(path))


def test_haiku_model_is_rejected(tmp_path):
    body = VALID.replace("model: opus", "model: haiku")
    path = write_agent(tmp_path, "reviewer.md", body)
    assert any("haiku" in e for e in validate_agent(path))


def test_missing_description_is_an_error(tmp_path):
    body = VALID.replace("description: Reads a diff once and reports findings.\n", "")
    path = write_agent(tmp_path, "reviewer.md", body)
    assert any("description" in e for e in validate_agent(path))


def test_em_dash_in_body_is_rejected(tmp_path):
    body = VALID + "\nThis line has an em dash — which the house rule bans.\n"
    path = write_agent(tmp_path, "reviewer.md", body)
    assert any("em dash" in e for e in validate_agent(path))


def test_agent_names_collects_stems(tmp_path):
    write_agent(tmp_path, "reviewer.md", VALID)
    write_agent(tmp_path, "implementer.md", VALID.replace("name: reviewer", "name: implementer").replace("model: opus", "model: sonnet"))
    assert agent_names(tmp_path) == {"reviewer", "implementer"}


# --- Ruling 1: malformed input must be reported, never raised ---


def test_frontmatter_that_is_a_yaml_list_is_rejected(tmp_path):
    path = write_agent(tmp_path, "reviewer.md", INVALID_LIST_FRONTMATTER)
    errors = validate_agent(path)
    assert any("mapping" in e for e in errors)


def test_tools_not_a_list_is_an_error(tmp_path):
    body = VALID.replace("tools: [Read, Grep, Glob, Bash]", "tools: 5")
    path = write_agent(tmp_path, "reviewer.md", body)
    errors = validate_agent(path)
    assert any("tools" in e and "must be a list" in e for e in errors)


def test_model_not_a_string_is_an_error(tmp_path):
    body = VALID.replace("model: opus", "model: 5")
    path = write_agent(tmp_path, "reviewer.md", body)
    errors = validate_agent(path)
    assert any("model" in e and "must be a string" in e for e in errors)


def test_name_not_a_string_is_an_error(tmp_path):
    body = VALID.replace("name: reviewer", "name: 5")
    path = write_agent(tmp_path, "reviewer.md", body)
    errors = validate_agent(path)
    assert any("name" in e and "must be a string" in e for e in errors)


# --- Task 5 fix round 1 ---


def test_non_utf8_file_is_rejected(tmp_path):
    path = tmp_path / "reviewer.md"
    path.write_bytes(b"---\nname: \xff\xfe\n---\n")
    errors = validate_agent(path)
    assert any("UTF-8" in e for e in errors)


def test_malformed_yaml_is_rejected(tmp_path):
    body = VALID.replace("name: reviewer", "name: [unclosed")
    path = write_agent(tmp_path, "reviewer.md", body)
    errors = validate_agent(path)
    assert any("not valid YAML" in e for e in errors)


def test_falsy_frontmatter_is_rejected(tmp_path):
    path = write_agent(tmp_path, "reviewer.md", FALSY_FRONTMATTER)
    errors = validate_agent(path)
    assert any("mapping" in e for e in errors)


def test_em_dash_in_frontmatter_description_is_rejected(tmp_path):
    body = VALID.replace(
        "description: Reads a diff once and reports findings.",
        "description: Reads a diff — reports findings.",
    )
    path = write_agent(tmp_path, "reviewer.md", body)
    errors = validate_agent(path)
    assert any("em dash" in e for e in errors)


def test_missing_frontmatter_marker_is_rejected(tmp_path):
    path = write_agent(tmp_path, "reviewer.md", "no frontmatter here\n")
    errors = validate_agent(path)
    assert any("start" in e for e in errors)


def test_unclosed_frontmatter_block_is_rejected(tmp_path):
    path = write_agent(tmp_path, "reviewer.md", "---\nname: reviewer\ndescription: d\n")
    errors = validate_agent(path)
    assert any("closed" in e for e in errors)


def test_description_not_a_string_is_an_error(tmp_path):
    body = VALID.replace("description: Reads a diff once and reports findings.", "description: [a, b]")
    path = write_agent(tmp_path, "reviewer.md", body)
    errors = validate_agent(path)
    assert any("description" in e and "must be a string" in e for e in errors)


def test_missing_file_is_reported_not_raised(tmp_path):
    path = tmp_path / "reviewer.md"
    errors = validate_agent(path)
    assert any("missing" in e for e in errors)


def test_directory_path_is_reported_not_raised(tmp_path):
    path = tmp_path / "reviewer.md"
    path.mkdir()
    errors = validate_agent(path)
    assert any("directory" in e for e in errors)
