#!/usr/bin/env bash
# Check that every skill name the routing table and the roster reference
# actually resolves to one skill directory.
#
# Two sources of names:
#   - templates/graph-profile.yaml: the `routing:` section, which this script
#     assumes holds only inline `impl: [...]`, `review: [...]`, `qa: [...]`
#     and `design: [...]` lists (no YAML block-list dashes, no anchors), each
#     either inside a quoted-pattern row (own line or `{ impl: [...] }` on the
#     pattern's line) or inside the bare `always:` row. The section runs from
#     the `routing:` line to the next column-0 key.
#   - agents/*.md: the frontmatter `skills:` block, a plain `- name` list
#     between the file's first two `---` lines, name optionally prefixed
#     `graph-engineering:`.
#
# A name resolves when exactly one `skills/*/<name>/SKILL.md` exists (the
# same layout `check-skill-frontmatter.sh` walks). Zero or more than one is a
# failure.
#
# Usage: scripts/check-routing-resolves.sh [root]     (default: the repo root)
# Exit 0 when every name resolves, 1 on any failure.
set -uo pipefail

ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}"

python3 - "$ROOT" <<'PY'
import os, re, sys

root = sys.argv[1]
template_path = os.path.join(root, "templates", "graph-profile.yaml")
agents_dir = os.path.join(root, "agents")
skills_dir = os.path.join(root, "skills")

LIST_KEY = re.compile(r"(?:impl|review|qa|design):\s*\[([^\]]*)\]")
TOP_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:")
ROUTING_START = re.compile(r"^routing:\s*$")


def routing_names(path):
    """Names in every impl/review/qa/design list under the routing section."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    names = set()
    in_routing = False
    for line in lines:
        if ROUTING_START.match(line):
            in_routing = True
            continue
        if in_routing and TOP_KEY.match(line):
            break
        if not in_routing:
            continue
        for m in LIST_KEY.finditer(line):
            for raw in m.group(1).split(","):
                name = raw.strip()
                if name:
                    names.add(name)
    return names


def agent_skill_names(path):
    """Bare or `graph-engineering:`-prefixed names in the frontmatter `skills:` list."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    if not lines or lines[0].strip() != "---":
        return []
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return []

    names = []
    in_skills = False
    for line in lines[1:end]:
        if re.match(r"^skills:\s*$", line):
            in_skills = True
            continue
        if not in_skills:
            continue
        m = re.match(r"^\s*-\s*(\S+)\s*$", line)
        if m:
            names.append(m.group(1))
        elif line.strip() != "":
            in_skills = False
    return [n.split(":", 1)[1] if n.startswith("graph-engineering:") else n for n in names]


refs = {}  # name -> set of referencing files, relative to root

for name in routing_names(template_path):
    refs.setdefault(name, set()).add(os.path.relpath(template_path, root))

if os.path.isdir(agents_dir):
    for fname in sorted(os.listdir(agents_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(agents_dir, fname)
        for name in agent_skill_names(path):
            refs.setdefault(name, set()).add(os.path.relpath(path, root))

skill_dirs = {}
for dirpath, _dirnames, filenames in os.walk(skills_dir):
    if "SKILL.md" in filenames:
        base = os.path.basename(dirpath)
        skill_dirs.setdefault(base, []).append(os.path.join(dirpath, "SKILL.md"))

failures = []
for name in sorted(refs):
    matches = skill_dirs.get(name, [])
    files = ", ".join(sorted(refs[name]))
    if len(matches) == 0:
        failures.append(f"FAIL {name}: no skills/*/{name}/SKILL.md (referenced by {files})")
    elif len(matches) > 1:
        rels = ", ".join(sorted(os.path.relpath(m, root) for m in matches))
        failures.append(
            f"FAIL {name}: {len(matches)} matches ({rels}) (referenced by {files})"
        )

for f in failures:
    print(f)

print(f"check-routing-resolves: {len(refs)} names checked, {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
PY
