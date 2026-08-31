import os
from pathlib import Path

import pytest

from graphlint.playbook import parse_playbook, validate_playbook

AGENTS = {"pm-planner", "implementer", "reviewer"}

VALID = """# Feature playbook

## node: goal
agent: pm-planner
in: the owner's stated goal
out: .graph/<run>/goal.md
gate: no
next: plan

## node: plan
agent: pm-planner
in: .graph/<run>/goal.md
out: .graph/<run>/plan.md
gate: yes
next: implement

## node: implement
agent: implementer
in: .graph/<run>/plan.md
out: worktree commits
gate: no
next: review

## node: review
agent: reviewer
in: the diff
out: .graph/<run>/findings.json
gate: no
next: END
"""


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "feature.md"
    path.write_text(body)
    return path


def test_valid_playbook_has_no_errors(tmp_path):
    assert validate_playbook(write(tmp_path, VALID), AGENTS) == []


def test_parses_every_node_in_order(tmp_path):
    nodes, errors = parse_playbook(write(tmp_path, VALID))
    assert errors == []
    assert [n["id"] for n in nodes] == ["goal", "plan", "implement", "review"]
    assert nodes[1]["gate"] is True


def test_unknown_agent_is_an_error(tmp_path):
    body = VALID.replace("agent: implementer", "agent: ghost-agent")
    assert any("ghost-agent" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_dangling_next_is_an_error(tmp_path):
    body = VALID.replace("next: implement", "next: nowhere")
    assert any("nowhere" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_unreachable_node_is_an_error(tmp_path):
    body = VALID + """
## node: orphan
agent: reviewer
in: nothing
out: nothing
gate: no
next: END
"""
    assert any("orphan" in e and "unreachable" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_missing_required_key_is_an_error(tmp_path):
    body = VALID.replace("out: .graph/<run>/goal.md\n", "")
    assert any("out" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_parallel_next_targets_are_split(tmp_path):
    body = VALID.replace("next: review", "next: review, qa") + """
## node: qa
agent: reviewer
in: the built artifact
out: .graph/<run>/qa.md
gate: no
next: END
"""
    nodes, errors = parse_playbook(write(tmp_path, body))
    assert errors == []
    implement = next(n for n in nodes if n["id"] == "implement")
    assert implement["next"] == ["review", "qa"]


# --- Ruling 4: file-system and decoding errors are reported, never raised ---


def test_missing_file_is_reported_not_raised(tmp_path):
    errors = validate_playbook(tmp_path / "gone.md", AGENTS)
    assert any("file is missing at" in e for e in errors)
    assert not any("no nodes" in e for e in errors)


def test_directory_path_is_reported_not_raised(tmp_path):
    path = tmp_path / "feature.md"
    path.mkdir()
    errors = validate_playbook(path, AGENTS)
    assert any("expected a file but found a directory" in e for e in errors)


def test_non_utf8_file_is_reported_not_raised(tmp_path):
    path = tmp_path / "feature.md"
    path.write_bytes(b"## node: goal\nagent: \xff\xfe\n")
    assert any("UTF-8" in e for e in validate_playbook(path, AGENTS))


def test_unreadable_file_is_reported_not_raised(tmp_path):
    path = write(tmp_path, VALID)
    os.chmod(path, 0o000)
    try:
        if os.access(path, os.R_OK):
            pytest.skip("cannot make a file unreadable in this environment")
        errors = validate_playbook(path, AGENTS)
    finally:
        os.chmod(path, 0o644)
    assert any("could not be read" in e for e in errors)


def test_parse_playbook_reports_a_missing_file_without_raising(tmp_path):
    nodes, errors = parse_playbook(tmp_path / "gone.md")
    assert nodes == []
    assert any("file is missing at" in e for e in errors)


# --- Ruling 1 and 3: malformed input is reported, never silently accepted ---


def test_empty_file_is_an_error(tmp_path):
    assert any("no nodes" in e for e in validate_playbook(write(tmp_path, ""), AGENTS))


def test_file_with_only_prose_is_an_error(tmp_path):
    body = "# Feature playbook\n\nSome prose, no nodes at all.\n"
    assert any("no nodes" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_malformed_node_heading_is_rejected(tmp_path):
    body = VALID + """
## node:
agent: reviewer
in: nothing
out: nothing
gate: no
next: END
"""
    assert any("malformed node heading" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_node_heading_with_a_spaced_id_is_rejected(tmp_path):
    body = VALID.replace("## node: review", "## node: review the diff")
    assert any("malformed node heading" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_malformed_key_line_is_rejected(tmp_path):
    body = VALID.replace("agent: reviewer\nin: the diff", "agent: reviewer\nmode : spike\nin: the diff")
    errors = validate_playbook(write(tmp_path, body), AGENTS)
    assert any("malformed key line" in e for e in errors)
    assert not any("missing required key" in e for e in errors)


def test_id_key_line_cannot_override_the_heading_id(tmp_path):
    body = VALID.replace("## node: goal\nagent:", "## node: goal\nid: hacked\nagent:")
    path = write(tmp_path, body)
    nodes, errors = parse_playbook(path)
    assert nodes[0]["id"] == "goal"
    assert any("not a settable key" in e for e in errors)
    assert any("not a settable key" in e for e in validate_playbook(path, AGENTS))


def test_duplicate_key_in_one_node_is_rejected(tmp_path):
    body = VALID.replace("gate: no\nnext: END", "gate: no\nnext: END\nnext: END")
    errors = validate_playbook(write(tmp_path, body), AGENTS)
    assert any("duplicate key 'next'" in e for e in errors)


def test_non_boolean_gate_value_is_rejected(tmp_path):
    body = VALID.replace("gate: yes", "gate: maybe")
    errors = validate_playbook(write(tmp_path, body), AGENTS)
    assert any("gate must be one of" in e for e in errors)


def test_empty_agent_value_is_rejected(tmp_path):
    body = VALID.replace("agent: implementer", "agent:")
    errors = validate_playbook(write(tmp_path, body), AGENTS)
    assert any("empty required key 'agent'" in e for e in errors)


def test_empty_next_value_is_rejected(tmp_path):
    body = VALID.replace("next: END", "next:")
    errors = validate_playbook(write(tmp_path, body), AGENTS)
    assert any("empty required key 'next'" in e for e in errors)


# --- Graph shape decisions ---


def test_node_id_END_is_reserved(tmp_path):
    body = VALID + """
## node: END
agent: reviewer
in: nothing
out: nothing
gate: no
next: END
"""
    assert any("reserved" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_duplicate_node_id_is_rejected(tmp_path):
    body = VALID + """
## node: plan
agent: reviewer
in: nothing
out: nothing
gate: no
next: END
"""
    assert any("duplicate node id 'plan'" in e for e in validate_playbook(write(tmp_path, body), AGENTS))


def test_self_loop_is_legal(tmp_path):
    body = VALID.replace("next: review", "next: review, implement")
    assert validate_playbook(write(tmp_path, body), AGENTS) == []


def test_cycle_terminates_and_is_legal(tmp_path):
    body = """## node: a
agent: implementer
in: the plan
out: commits
gate: no
next: b

## node: b
agent: reviewer
in: the diff
out: findings
gate: no
next: a
"""
    assert validate_playbook(write(tmp_path, body), AGENTS) == []


def test_fix_loop_cycle_with_an_exit_is_legal(tmp_path):
    body = VALID.replace("next: END", "next: fix") + """
## node: fix
agent: implementer
in: .graph/<run>/findings.json
out: worktree commits
gate: no
next: review, END
"""
    assert validate_playbook(write(tmp_path, body), AGENTS) == []
