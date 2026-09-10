#!/usr/bin/env bash
# Check every skills/**/SKILL.md for the frontmatter this plugin depends on.
#
# Fails when a SKILL.md
#   - has no YAML frontmatter block, or
#   - has no `name`, or an empty one, or
#   - has no `description`, or an empty one, or
#   - has a `name` that differs from the name of the directory holding the file.
#
# The last one matters because Claude Code takes a skill's invocation name from
# the frontmatter `name` and falls back to the directory basename; when the two
# disagree, a routing row that names one of them resolves to nothing.
#
# `claude plugin validate` does NOT do any of this. It checks the manifest's
# JSON shape and that each skills[] path exists; it never opens a SKILL.md.
# Reviewer reproduced that: a SKILL.md with no name and no description passes
# validate, including --strict. This script is the real check.
#
# Usage: scripts/check-skill-frontmatter.sh [root]     (default: the repo root)
# Exit 0 when every SKILL.md passes, 1 on any failure, 2 when no SKILL.md exists.
set -uo pipefail

ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}"

python3 - "$ROOT" <<'PY'
import os, re, sys

root = sys.argv[1]
skills_dir = os.path.join(root, "skills")

TOP_KEY = re.compile(r"^([A-Za-z0-9_.-]+):(.*)$")
BLOCK = re.compile(r"^[>|][0-9+-]*$")


def frontmatter(path):
    """Top-level keys of the leading --- block. None when there is no block."""
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
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        i += 1
        if rest == "" or BLOCK.match(rest):
            # Folded, literal, or empty scalar: the value is the indented run.
            parts = []
            while i < len(body) and (body[i].startswith((" ", "\t")) or body[i].strip() == ""):
                parts.append(body[i].strip())
                i += 1
            rest = " ".join(p for p in parts if p).strip()
        keys[key] = rest
    return keys


skill_files = []
for dirpath, _dirnames, filenames in os.walk(skills_dir):
    if "SKILL.md" in filenames:
        skill_files.append(os.path.join(dirpath, "SKILL.md"))
skill_files.sort()

if not skill_files:
    print(f"check-skill-frontmatter: no SKILL.md found under {skills_dir}")
    sys.exit(2)

failures = []
for path in skill_files:
    rel = os.path.relpath(path, root)
    fm = frontmatter(path)
    if fm is None:
        failures.append(f"{rel}: no YAML frontmatter block")
        continue
    name = fm.get("name", "")
    desc = fm.get("description", "")
    dirname = os.path.basename(os.path.dirname(path))
    if not name:
        failures.append(f"{rel}: frontmatter has no non-empty `name`")
    elif name != dirname:
        failures.append(f"{rel}: frontmatter `name: {name}` differs from directory name `{dirname}`")
    if not desc:
        failures.append(f"{rel}: frontmatter has no non-empty `description`")

for f in failures:
    print(f"FAIL {f}")

print(
    f"check-skill-frontmatter: {len(skill_files)} SKILL.md checked, {len(failures)} failure(s)"
)
sys.exit(1 if failures else 0)
PY
