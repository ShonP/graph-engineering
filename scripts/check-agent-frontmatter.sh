#!/usr/bin/env bash
# Check every agents/*.md for the frontmatter plugin agents may carry, and
# every graphs/*.md node for an agent that exists.
#
# Fails when an agent file
#   - has no YAML frontmatter block, or no non-empty `name` / `description`,
#   - has a `name` that differs from the file stem,
#   - carries a key outside the allowed set. `permissionMode`, `hooks`,
#     `mcpServers` and `initialPrompt` are named as ignored for plugin agents
#     (Claude Code drops them when the agent ships in a plugin); `isolation` is
#     named as not adopted (spike d, 2026-09-30),
#   - has a `model` other than opus or sonnet (owner policy: never haiku or
#     fable), or no `model`,
#   - has no `tools` list, a `maxTurns` that is not a positive integer, or an
#     `omitClaudeMd` that is not a boolean,
#   - lists a skill that is not `graph-engineering:<name>`, or whose name does
#     not resolve to exactly one skills/*/<name>/SKILL.md.
# Fails when a graphs/*.md node's `agent:` is neither `engine` nor an existing
# agents/<value>.md.
#
# `claude plugin validate --strict` checks none of this: spiked 2026-09-30, an
# agent with model haiku, permissionMode, isolation, maxTurns `ten`, a name
# mismatch and an unknown skill passed it.
#
# Usage: scripts/check-agent-frontmatter.sh [root]     (default: the repo root)
# Exit 0 when every file passes, 1 on any failure.
set -uo pipefail

ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}"

python3 - "$ROOT" <<'PY'
import glob, os, re, sys

root = sys.argv[1]
PREFIX = "graph-engineering:"
ALLOWED = {"name", "description", "model", "effort", "maxTurns", "tools",
           "disallowedTools", "skills", "memory", "background", "omitClaudeMd",
           "color"}
REJECTED = {
    "permissionMode": "ignored for plugin agents",
    "hooks": "ignored for plugin agents",
    "mcpServers": "ignored for plugin agents",
    "initialPrompt": "ignored for plugin agents",
    "isolation": "not adopted: frontmatter isolation branches from the default "
                 "branch, not the run branch (spike d, 2026-09-30)",
}
MODELS = ("opus", "sonnet")
BOOLS = {"true", "false", "True", "False", "TRUE", "FALSE"}

TOP_KEY = re.compile(r"^([A-Za-z0-9_.-]+):(.*)$")
BLOCK = re.compile(r"^[>|][0-9+-]*$")
NODE = re.compile(r"^## node:\s*(\S+)")
AGENT = re.compile(r"agent:\s*(.+)")


def scalar(text):
    text = re.sub(r"\s+#.*$", "", text).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text


def frontmatter(path):
    """Top-level keys of the leading --- block; list values stay lists."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    body = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        body.append(line)
    else:
        return None

    keys, i = {}, 0
    while i < len(body):
        m = TOP_KEY.match(body[i])
        i += 1
        if not m:
            continue
        key, rest = m.group(1), re.sub(r"\s+#.*$", "", m.group(2)).strip()
        if rest.startswith("[") and rest.endswith("]"):
            keys[key] = [scalar(x) for x in rest[1:-1].split(",") if x.strip()]
            continue
        if rest and not BLOCK.match(rest):
            keys[key] = scalar(rest)
            continue
        # Block list, folded/literal scalar, or empty: the indented run below.
        items, parts = [], []
        while i < len(body) and (body[i][:1] in (" ", "\t", "#", "-")
                                 or body[i].strip() == ""):
            text = body[i].strip()
            i += 1
            if not text or text.startswith("#"):
                continue
            if text == "-" or text.startswith("- "):
                items.append(scalar(text[1:]))
            else:
                parts.append(text)
        keys[key] = items if items else " ".join(parts)
    return keys


def check_agent(path, fail):
    rel = os.path.relpath(path, root)
    stem = os.path.splitext(os.path.basename(path))[0]
    fm = frontmatter(path)
    if fm is None:
        fail(rel, "no YAML frontmatter block")
        return
    name = fm.get("name", "")
    if not isinstance(name, str) or not name:
        fail(rel, "frontmatter has no non-empty `name`")
    elif name != stem:
        fail(rel, f"frontmatter `name: {name}` differs from file stem `{stem}`")
    if not fm.get("description"):
        fail(rel, "frontmatter has no non-empty `description`")
    for key in fm:
        if key in REJECTED:
            fail(rel, f"`{key}` is rejected: {REJECTED[key]}")
        elif key not in ALLOWED:
            fail(rel, f"unknown key `{key}` (allowed: {', '.join(sorted(ALLOWED))})")

    model = fm.get("model")
    if model is None:
        fail(rel, "no `model`; set opus or sonnet (owner policy)")
    elif model not in MODELS:
        fail(rel, f"model `{model}` is not opus or sonnet "
                  "(owner policy: never haiku or fable)")

    tools = fm.get("tools")
    if tools is None:
        fail(rel, "no `tools`; list the agent's tools explicitly")
    elif not isinstance(tools, list) or not tools:
        fail(rel, "`tools` must be a non-empty YAML list")

    turns = fm.get("maxTurns")
    if turns is not None and not (isinstance(turns, str)
                                  and re.fullmatch(r"[1-9][0-9]*", turns)):
        fail(rel, f"`maxTurns: {turns}` is not a positive integer")

    omit = fm.get("omitClaudeMd")
    if omit is not None and omit not in BOOLS:
        fail(rel, f"`omitClaudeMd: {omit}` is not a boolean")

    skills = fm.get("skills")
    if skills is None:
        return
    if not isinstance(skills, list):
        fail(rel, "`skills` must be a YAML list")
        return
    for entry in skills:
        if not entry.startswith(PREFIX):
            fail(rel, f"skill `{entry}` must be qualified as `{PREFIX}{entry}`")
            continue
        bare = entry[len(PREFIX):]
        hits = glob.glob(os.path.join(root, "skills", "*", bare, "SKILL.md"))
        if len(hits) != 1:
            fail(rel, f"skill `{entry}` resolves to {len(hits)} "
                      f"skills/*/{bare}/SKILL.md (need exactly 1)")


def check_graph(path, agents_dir, fail):
    rel = os.path.relpath(path, root)
    node = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            m = NODE.match(line)
            if m:
                node = m.group(1)
                continue
            m = AGENT.fullmatch(line.strip()) if node else None
            if not m:
                continue
            agent = m.group(1).strip()
            if agent != "engine" and not os.path.isfile(
                    os.path.join(agents_dir, f"{agent}.md")):
                fail(rel, f"line {n}: node `{node}` agent `{agent}` is neither "
                          f"`engine` nor agents/{agent}.md")


failures = []


def fail(rel, message):
    failures.append(f"{rel}: {message}")


agents_dir = os.path.join(root, "agents")
agent_files = sorted(glob.glob(os.path.join(agents_dir, "*.md")))
graph_files = sorted(glob.glob(os.path.join(root, "graphs", "*.md")))
if not agent_files:
    fail("agents", f"no agents/*.md found under {root}")
for path in agent_files:
    check_agent(path, fail)
for path in graph_files:
    check_graph(path, agents_dir, fail)

for line in failures:
    print(f"FAIL {line}")
print(f"check-agent-frontmatter: {len(agent_files)} agent(s), "
      f"{len(graph_files)} graph(s) checked, {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
PY
