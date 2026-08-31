# Graph Engineering Plugin - P0 Spikes + P1 Walking Skeleton

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an installable `graph-engineering` plugin that runs one real koach task end-to-end through a reduced `feature` playbook: goal -> plan -> owner gate -> implementer -> reviewer -> merge gate.

**Architecture:** A markdown-defined plugin (agents, playbooks, commands) guarded by a small Python validator. The validator is the only executable code and therefore the only thing with unit tests; everything else is markdown whose correctness the validator asserts. Three spikes run first because each can invalidate a design decision in the spec.

**Tech Stack:** Markdown + YAML frontmatter (plugin surface), Python 3.12 + `uv` + pytest (validator), `gh` CLI (later phases).

**Spec:** `docs/superpowers/specs/2026-08-31-graph-engineering-plugin-design.md`

## Global Constraints

- Plugin name: `graph-engineering`. Marketplace name: `graph-engineering`.
- Agent models: `opus` for `reviewer` and `pm-planner`, `sonnet` for every other agent. **`haiku` is never valid** (standing policy).
- Agent `name:` frontmatter MUST equal the filename stem.
- Agents live flat in `agents/` - agents do not nest-discover.
- No em dashes in any authored file (house rule; koach blocks them at pre-push).
  Two deliberate exemptions, both load-bearing: the `EM_DASH` constant in
  `graphlint/agent.py` and the fixture string in `tests/test_agent.py` that
  proves the check fires. Do not "fix" either.
- Skills are named in the dispatch prompt by the spine. An agent never chooses its own skills.
- Competency precedence on conflict: house (koach-harvested) > vault-generated > community (adopted).
- Run state lives in the CONSUMER repo at `.graph/<run-id>/`, never in the plugin repo.
- Every open question is either spiked or recorded in `plan.md` as an explicit assumption. Never silently guessed.
- Python: `uv` for dependency management, `pytest` for tests, files under 250 LOC.

---

## File Structure

| File | Responsibility |
|---|---|
| `.claude-plugin/plugin.json` | plugin identity + version |
| `.claude-plugin/marketplace.json` | makes the repo installable as a marketplace |
| `graphlint/__init__.py` | package marker |
| `graphlint/manifest.py` | validate plugin.json + marketplace.json |
| `graphlint/agent.py` | validate agent frontmatter |
| `graphlint/playbook.py` | validate playbook node schema + graph reachability |
| `graphlint/profile.py` | validate a consumer repo's graph-profile.yaml |
| `graphlint/__main__.py` | CLI: walk a repo, print errors, exit nonzero |
| `tests/test_*.py` | one test module per validator |
| `agents/{pm-planner,implementer,reviewer}.md` | P1 roster |
| `graphs/feature.md` | reduced feature playbook |
| `commands/{graph-init,graph-ship}.md` | init + spine |
| `templates/graph-profile.yaml` | commented profile template |
| `README.md` | install, update, dev loop |

---

## PHASE 0 - SPIKES

Spikes produce **answers, not code**. Any code written is throwaway and is deleted or explicitly labelled before the task commits. Each spike ends with a written recommendation and, where the answer contradicts the spec, an amendment commit to the spec.

### Task 1: Spike - can a plugin agent preload plugin-local skills?

**Question:** Does `skills:` frontmatter in a plugin-provided agent resolve a plugin-provided skill, and under what name (`react-patterns` vs `graph-engineering:react-patterns`)?

**Why it blocks:** If yes, hot-path agents could preload their most common competency and skip a dispatch hop. If no, the spine's "name the skills in the dispatch prompt" mechanism is the ONLY mechanism, and the spec's fallback becomes the design.

**Files:**
- Create: `docs/superpowers/spikes/2026-08-31-plugin-agent-skill-preload.md`
- Throwaway: a scratch plugin under the scratchpad directory, deleted at the end

- [ ] **Step 1: Build a minimal throwaway plugin**

In the scratchpad directory (NOT in this repo):

```bash
SP="$(mktemp -d)/spike-plugin"
mkdir -p "$SP"/{.claude-plugin,agents,skills/spike-canary}
cat > "$SP/.claude-plugin/plugin.json" <<'EOF'
{ "name": "spike-plugin", "description": "throwaway spike", "version": "0.0.1" }
EOF
cat > "$SP/.claude-plugin/marketplace.json" <<'EOF'
{ "name": "spike-plugin", "owner": { "name": "spike" },
  "plugins": [ { "name": "spike-plugin", "source": "./", "description": "throwaway spike" } ] }
EOF
cat > "$SP/skills/spike-canary/SKILL.md" <<'EOF'
---
name: spike-canary
description: Canary skill used only to detect whether an agent preloaded it.
---
The canary phrase is PRELOAD-CONFIRMED-7731. If you can read this, you have this skill in context.
EOF
cat > "$SP/agents/spike-agent.md" <<'EOF'
---
name: spike-agent
description: Throwaway spike agent that reports whether the canary skill was preloaded.
tools: [Read]
model: sonnet
skills:
  - spike-canary
---
Report ONLY one line: the canary phrase if it is already in your context, otherwise the exact text NO-CANARY. Do not use any tool. Do not invoke any skill.
EOF
echo "$SP"
```

- [ ] **Step 2: Install it and dispatch the agent**

Install the throwaway marketplace, then dispatch `spike-agent` with the prompt: `Report the canary phrase.`

- [ ] **Step 3: Record the result**

Expected outcomes and what each means:
- Returns `PRELOAD-CONFIRMED-7731` -> bare-name preloading works.
- Returns `NO-CANARY` -> retry once with `skills: [spike-plugin:spike-canary]`. If that returns the phrase, qualified naming is required. If it also returns `NO-CANARY`, plugin-local preloading does not work.

- [ ] **Step 4: Write the spike answer**

Write `docs/superpowers/spikes/2026-08-31-plugin-agent-skill-preload.md` containing: the question, the exact steps run, the raw agent output for each variant tried, the answer (works-bare / works-qualified / does-not-work), and the recommendation for the spec.

- [ ] **Step 5: Amend the spec if the answer contradicts it**

If preloading does not work, edit spec section 2.2 to state that spine-named dispatch is the only mechanism and delete the preload fallback language.

- [ ] **Step 6: Delete the throwaway plugin and commit**

```bash
rm -rf "$SP"
git add docs/superpowers/spikes/2026-08-31-plugin-agent-skill-preload.md docs/superpowers/specs/
git commit -m "spike: plugin agent skill preloading - answer recorded"
```

### Task 2: Spike - does a local-directory marketplace source work?

**Question:** Does `/plugin marketplace add <local absolute path>` work on this Claude Code version, or are only GitHub-sourced marketplaces supported?

**Why it blocks:** It decides the dev loop. Local source = edit and re-test immediately. GitHub only = every test costs a commit and push.

**Files:**
- Create: `docs/superpowers/spikes/2026-08-31-local-marketplace-source.md`

- [ ] **Step 1: Record the current registry state**

```bash
python3 -c "import json;print(list(json.load(open('/Users/shonpazarker/.claude/plugins/known_marketplaces.json')).keys()))"
```

Expected: the five existing marketplaces, all GitHub-sourced.

- [ ] **Step 2: Attempt a local add**

Run `/plugin marketplace add /Users/shonpazarker/projects/graph-engineering` (the repo already has a `.claude-plugin/marketplace.json` after P1 Task 4; if running this spike first, create a minimal one in the scratchpad instead and add that path).

- [ ] **Step 3: Verify what landed in the registry**

```bash
python3 -c "import json;d=json.load(open('/Users/shonpazarker/.claude/plugins/known_marketplaces.json'));print(json.dumps({k:v['source'] for k,v in d.items()},indent=2))"
```

Expected on success: a new entry whose `source.source` is not `github`.

- [ ] **Step 4: Write the spike answer**

Record: works or not; the exact `source` object shape a local marketplace produces; and whether edits to the source directory appear without a re-add (test by editing the plugin's README and re-listing). If it does not work, the recommendation is a private GitHub repo with push-then-`/plugin update`, and P1 Task 12 changes accordingly.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/spikes/2026-08-31-local-marketplace-source.md
git commit -m "spike: local-directory marketplace source - answer recorded"
```

### Task 3: Spike - can plugin.json declare dependencies on other plugins?

**Question:** Does the plugin manifest support declaring required plugins/marketplaces, so `graph-engineering` can pull in the adopted community skills automatically?

**Why it blocks:** The spec chose "depend, don't vendor". If declaration is unsupported, `/graph-doctor` plus README instructions carry the whole dependency contract, and the enablement gate becomes the only enforcement.

**Files:**
- Create: `docs/superpowers/spikes/2026-08-31-plugin-dependencies.md`

- [ ] **Step 1: Inspect every installed manifest for a dependency field**

```bash
find /Users/shonpazarker/.claude/plugins/cache -name plugin.json -maxdepth 4 -exec sh -c 'echo "== $1"; cat "$1"' _ {} \;
```

Expected: none of them declare dependencies (this establishes the baseline, it does not prove absence).

- [ ] **Step 2: Check the published schema**

Fetch `https://code.claude.com/schemas/plugin.json` (the marketplace files reference a sibling schema URL) and check for a `dependencies`, `requires`, or `plugins` field.

- [ ] **Step 3: Write the spike answer**

Record: supported or not, the exact field name and shape if supported, and the fallback design if not (a `dependencies:` list in `templates/graph-profile.yaml` that `/graph-doctor` reads and checks against `installed_plugins.json`).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/spikes/2026-08-31-plugin-dependencies.md
git commit -m "spike: plugin dependency declaration - answer recorded"
```

---

## PHASE 1 - WALKING SKELETON

### Task 4: Repo scaffolding and manifest validator

**Files:**
- Create: `pyproject.toml`, `graphlint/__init__.py`, `graphlint/manifest.py`, `tests/test_manifest.py`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Produces: `graphlint.manifest.validate_manifest(repo_root: Path) -> list[str]` - returns a list of human-readable error strings; empty list means valid.

- [ ] **Step 1: Write the failing test**

`tests/test_manifest.py`:

```python
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
```

- [ ] **Step 2: Run it and verify it fails**

```bash
cd ~/projects/graph-engineering && uv run pytest tests/test_manifest.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graphlint'`.

- [ ] **Step 3: Create the project and the implementation**

`pyproject.toml`:

```toml
[project]
name = "graphlint"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pyyaml>=6.0"]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`graphlint/__init__.py`: empty file.

`graphlint/manifest.py`:

```python
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
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name} is not valid JSON: {exc}")
        return None


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
        if version and not SEMVER.match(version):
            errors.append(f"plugin.json version must be semver x.y.z, got {version!r}")

    market = _load(base / "marketplace.json", errors)
    if market is not None:
        names = [p.get("name") for p in market.get("plugins", [])]
        if PLUGIN_NAME not in names:
            errors.append(f"marketplace.json must list a plugin named '{PLUGIN_NAME}', found {names}")
        if not market.get("owner", {}).get("name"):
            errors.append("marketplace.json is missing owner.name")

    return errors
```

- [ ] **Step 4: Create the real manifests**

`.claude-plugin/plugin.json`:

```json
{
  "name": "graph-engineering",
  "description": "An AI-native software organization: agents, competencies, and playbooks for map-reduce multi-agent delivery.",
  "version": "0.1.0",
  "author": { "name": "Shon Pazarker" },
  "keywords": ["agents", "skills", "workflow", "multi-agent", "review"]
}
```

`.claude-plugin/marketplace.json`:

```json
{
  "$schema": "https://code.claude.com/schemas/marketplace.json",
  "name": "graph-engineering",
  "owner": { "name": "Shon Pazarker" },
  "plugins": [
    {
      "name": "graph-engineering",
      "source": "./",
      "description": "An AI-native software organization: agents, competencies, and playbooks for map-reduce multi-agent delivery."
    }
  ]
}
```

- [ ] **Step 5: Run the tests and verify they pass**

```bash
uv run pytest tests/test_manifest.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml graphlint tests .claude-plugin
git commit -m "feat: plugin manifests and manifest validator"
```

### Task 5: Agent frontmatter validator

**Files:**
- Create: `graphlint/agent.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `graphlint.agent.validate_agent(path: Path) -> list[str]` and `graphlint.agent.agent_names(agents_dir: Path) -> set[str]`.

- [ ] **Step 1: Write the failing test**

`tests/test_agent.py`:

```python
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
```

- [ ] **Step 2: Run it and verify it fails**

```bash
uv run pytest tests/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graphlint.agent'`.

- [ ] **Step 3: Write the implementation**

`graphlint/agent.py`:

```python
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
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        return None, body, f"frontmatter is not valid YAML: {exc}"
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
    if name and name != path.stem:
        errors.append(f"{path.name}: name {name!r} must match the filename stem {path.stem!r}")

    model = front.get("model")
    if model and model not in ALLOWED_MODELS:
        errors.append(
            f"{path.name}: model {model!r} is not allowed; use one of {sorted(ALLOWED_MODELS)} "
            f"(haiku is banned by standing policy)"
        )

    if EM_DASH in text:
        errors.append(f"{path.name}: contains an em dash, which the house rule bans")

    return errors


def agent_names(agents_dir: Path) -> set[str]:
    return {p.stem for p in sorted(agents_dir.glob("*.md"))}
```

- [ ] **Step 4: Run the tests and verify they pass**

```bash
uv run pytest tests/test_agent.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add graphlint/agent.py tests/test_agent.py
git commit -m "feat: agent frontmatter validator"
```

### Task 6: Playbook node validator

**Files:**
- Create: `graphlint/playbook.py`, `tests/test_playbook.py`

**Interfaces:**
- Consumes: `graphlint.agent.agent_names`.
- Produces: `graphlint.playbook.parse_playbook(path: Path) -> tuple[list[dict], list[str]]` returning (nodes, errors), and `graphlint.playbook.validate_playbook(path: Path, known_agents: set[str]) -> list[str]`. Each node is a dict with keys `id`, `agent`, `in`, `out`, `gate`, `next`, plus optional `mode`, `skills`, `compose`.

- [ ] **Step 1: Write the failing test**

`tests/test_playbook.py`:

```python
from pathlib import Path
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
```

- [ ] **Step 2: Run it and verify it fails**

```bash
uv run pytest tests/test_playbook.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graphlint.playbook'`.

- [ ] **Step 3: Write the implementation**

`graphlint/playbook.py`:

```python
"""Parse and validate playbook files."""

from __future__ import annotations

import re
from pathlib import Path

NODE_HEADING = re.compile(r"^## node:\s*(\S+)\s*$")
KEY_LINE = re.compile(r"^(\w+):\s*(.*)$")
REQUIRED_KEYS = ("agent", "in", "out", "gate", "next")
END = "END"


def _coerce(key: str, value: str) -> object:
    if key == "gate":
        return value.strip().lower() in {"yes", "true"}
    if key == "next":
        return [part.strip() for part in value.split(",") if part.strip()]
    if key == "skills":
        return [p.strip() for p in value.strip().strip("[]").split(",") if p.strip()]
    return value.strip()


def parse_playbook(path: Path) -> tuple[list[dict], list[str]]:
    nodes: list[dict] = []
    errors: list[str] = []
    current: dict | None = None

    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        heading = NODE_HEADING.match(line)
        if heading:
            current = {"id": heading.group(1)}
            nodes.append(current)
            continue
        if current is None or not line.strip():
            continue
        if line.startswith("#"):
            current = None
            continue
        match = KEY_LINE.match(line)
        if match:
            key, value = match.group(1), match.group(2)
            current[key] = _coerce(key, value)

    for node in nodes:
        for key in REQUIRED_KEYS:
            if key not in node:
                errors.append(f"{path.name}: node '{node['id']}' is missing required key '{key}'")

    return nodes, errors


def validate_playbook(path: Path, known_agents: set[str]) -> list[str]:
    nodes, errors = parse_playbook(path)
    if not nodes:
        return errors + [f"{path.name}: contains no nodes"]

    ids = {node["id"] for node in nodes}

    for node in nodes:
        agent = node.get("agent")
        if agent and agent not in known_agents:
            errors.append(f"{path.name}: node '{node['id']}' references unknown agent '{agent}'")
        for target in node.get("next", []):
            if target != END and target not in ids:
                errors.append(f"{path.name}: node '{node['id']}' points to unknown node '{target}'")

    entry = nodes[0]["id"]
    reachable = {entry}
    frontier = [entry]
    by_id = {node["id"]: node for node in nodes}
    while frontier:
        node = by_id[frontier.pop()]
        for target in node.get("next", []):
            if target != END and target in by_id and target not in reachable:
                reachable.add(target)
                frontier.append(target)

    for node_id in sorted(ids - reachable):
        errors.append(f"{path.name}: node '{node_id}' is unreachable from the entry node '{entry}'")

    return errors
```

- [ ] **Step 4: Run the tests and verify they pass**

```bash
uv run pytest tests/test_playbook.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add graphlint/playbook.py tests/test_playbook.py
git commit -m "feat: playbook node validator with reachability check"
```

### Task 7: Profile validator and template

**Files:**
- Create: `graphlint/profile.py`, `tests/test_profile.py`, `templates/graph-profile.yaml`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `graphlint.profile.validate_profile(path: Path, known_agents: set[str]) -> list[str]`.

- [ ] **Step 1: Write the failing test**

`tests/test_profile.py`:

```python
from pathlib import Path
import yaml
from graphlint.profile import validate_profile

AGENTS = {"pm-planner", "implementer", "reviewer"}

VALID = {
    "stacks": {"web": {"paths": ["apps/*/web/**"]}},
    "rules": [".claude/rules/*.md"],
    "routing": {
        "**/*.tsx": {"impl": ["react-patterns"], "review": ["react-lens"], "qa": []},
        "always": {"review": ["review-protocol", "security-review"]},
    },
    "localAgents": {"implementer": "web-implementer"},
    "gates": {"plan": "owner", "design": "owner", "merge": "owner", "publication": "owner"},
    "board": {"platform": "github", "project": "Koach Graph Runs"},
}


def write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "graph-profile.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def test_valid_profile_has_no_errors(tmp_path):
    assert validate_profile(write(tmp_path, VALID), AGENTS) == []


def test_routing_must_define_always(tmp_path):
    data = {**VALID, "routing": {"**/*.tsx": {"impl": [], "review": [], "qa": []}}}
    assert any("always" in e for e in validate_profile(write(tmp_path, data), AGENTS))


def test_gates_must_be_owner_or_auto(tmp_path):
    data = {**VALID, "gates": {**VALID["gates"], "merge": "sometimes"}}
    assert any("merge" in e for e in validate_profile(write(tmp_path, data), AGENTS))


def test_local_agent_override_key_must_be_a_known_agent(tmp_path):
    data = {**VALID, "localAgents": {"ghost": "web-implementer"}}
    assert any("ghost" in e for e in validate_profile(write(tmp_path, data), AGENTS))


def test_missing_stacks_is_an_error(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "stacks"}
    assert any("stacks" in e for e in validate_profile(write(tmp_path, data), AGENTS))
```

- [ ] **Step 2: Run it and verify it fails**

```bash
uv run pytest tests/test_profile.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graphlint.profile'`.

- [ ] **Step 3: Write the implementation**

`graphlint/profile.py`:

```python
"""Validate a consumer repo's graph-profile.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

REQUIRED_TOP_LEVEL = ("stacks", "routing", "gates")
GATE_VALUES = {"owner", "auto"}
GATE_KEYS = ("plan", "design", "merge", "publication")


def validate_profile(path: Path, known_agents: set[str]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"graph-profile.yaml is missing at {path}"]
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        return [f"graph-profile.yaml is not valid YAML: {exc}"]

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append(f"graph-profile.yaml is missing required key '{key}'")

    routing = data.get("routing", {})
    if routing and "always" not in routing:
        errors.append("graph-profile.yaml routing must define an 'always' entry for cross-cutting review lenses")

    gates = data.get("gates", {})
    for key in GATE_KEYS:
        value = gates.get(key)
        if value is not None and value not in GATE_VALUES:
            errors.append(f"graph-profile.yaml gate '{key}' must be one of {sorted(GATE_VALUES)}, got {value!r}")

    for role in data.get("localAgents", {}):
        if role not in known_agents:
            errors.append(f"graph-profile.yaml localAgents key '{role}' is not a known plugin agent")

    return errors
```

- [ ] **Step 4: Create the template**

`templates/graph-profile.yaml`:

```yaml
# graph-engineering project profile.
# Owned by THIS repo, never overwritten by a plugin update.
# Generated by /graph-init; edit freely.

stacks:
  web: { paths: ["apps/*/web/**"] }

# Rule packs agents Read before working. Path-scoped packs do NOT auto-load
# into a subagent, so they are named here and Read explicitly.
rules: [".claude/rules/*.md"]

# Where specs and plans are written. Override when the repo does not use docs/.
docsPath: "docs/superpowers"

# The spine reads this to name each agent's required skills in its dispatch
# prompt. Agents never choose their own skills.
routing:
  "**/*.{ts,tsx}":
    impl: [react-patterns, tanstack-query, tanstack-router]
    review: [react-lens, a11y-i18n]
    qa: [playwright-e2e]
  always:
    review: [review-protocol, security-review, privacy-review]

# Defer to an agent this repo already owns. Empty means use the plugin roster.
localAgents: {}

gates:
  plan: owner
  design: owner
  merge: owner
  publication: owner

board:
  platform: github
  project: "Graph Runs"
```

- [ ] **Step 5: Run the tests and verify they pass**

```bash
uv run pytest tests/test_profile.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add graphlint/profile.py tests/test_profile.py templates/graph-profile.yaml
git commit -m "feat: profile validator and template"
```

### Task 8: graphlint CLI

**Files:**
- Create: `graphlint/__main__.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `validate_manifest`, `validate_agent`, `agent_names`, `validate_playbook`.
- Produces: `graphlint.__main__.main(argv: list[str]) -> int` - exit code 0 when clean, 1 when any error is found.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
import json
from pathlib import Path
from graphlint.__main__ import main

AGENT = """---
name: reviewer
description: Reads a diff once and reports findings.
tools: [Read, Grep, Glob, Bash]
model: opus
---
body
"""

PLAYBOOK = """## node: review
agent: reviewer
in: the diff
out: .graph/<run>/findings.json
gate: no
next: END
"""


def scaffold(root: Path) -> None:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": "graph-engineering", "description": "d", "version": "0.1.0"})
    )
    (root / ".claude-plugin/marketplace.json").write_text(
        json.dumps({
            "name": "graph-engineering",
            "owner": {"name": "Shon Pazarker"},
            "plugins": [{"name": "graph-engineering", "source": "./", "description": "d"}],
        })
    )
    (root / "agents").mkdir()
    (root / "agents/reviewer.md").write_text(AGENT)
    (root / "graphs").mkdir()
    (root / "graphs/feature.md").write_text(PLAYBOOK)


def test_clean_repo_exits_zero(tmp_path, capsys):
    scaffold(tmp_path)
    assert main([str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_bad_agent_exits_one_and_names_the_file(tmp_path, capsys):
    scaffold(tmp_path)
    (tmp_path / "agents/reviewer.md").write_text(AGENT.replace("model: opus", "model: haiku"))
    assert main([str(tmp_path)]) == 1
    assert "haiku" in capsys.readouterr().out
```

- [ ] **Step 2: Run it and verify it fails**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graphlint.__main__'`.

- [ ] **Step 3: Write the implementation**

`graphlint/__main__.py`:

```python
"""CLI: validate the whole plugin repo."""

from __future__ import annotations

import sys
from pathlib import Path

from graphlint.agent import agent_names, validate_agent
from graphlint.manifest import validate_manifest
from graphlint.playbook import validate_playbook


def main(argv: list[str]) -> int:
    root = Path(argv[0] if argv else ".").resolve()
    errors = list(validate_manifest(root))

    agents_dir = root / "agents"
    known = agent_names(agents_dir) if agents_dir.is_dir() else set()
    for path in sorted(agents_dir.glob("*.md")) if agents_dir.is_dir() else []:
        errors.extend(validate_agent(path))

    graphs_dir = root / "graphs"
    for path in sorted(graphs_dir.glob("*.md")) if graphs_dir.is_dir() else []:
        errors.extend(validate_playbook(path, known))

    if errors:
        for error in errors:
            print(f"error: {error}")
        print(f"\n{len(errors)} problem(s) found")
        return 1

    print(f"OK: {len(known)} agent(s), manifests and playbooks valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the whole suite and verify it passes**

```bash
uv run pytest -v && uv run python -m graphlint .
```

Expected: all tests pass; the CLI reports errors for this repo because `agents/` and `graphs/` do not exist yet. That is correct - Tasks 9 and 10 create them.

- [ ] **Step 5: Commit**

```bash
git add graphlint/__main__.py tests/test_cli.py
git commit -m "feat: graphlint CLI"
```

### Task 9: The three P1 agents

**Files:**
- Create: `agents/pm-planner.md`, `agents/implementer.md`, `agents/reviewer.md`

**Interfaces:**
- Consumes: the agent schema enforced by `graphlint.agent`.
- Produces: agent names `pm-planner`, `implementer`, `reviewer`, referenced by `graphs/feature.md` in Task 10.

- [ ] **Step 1: Write `agents/pm-planner.md`**

```markdown
---
name: pm-planner
description: Turns a stated goal into a product spec (intent, value, success metrics, non-goals) and then into a task-decomposed plan with owners and sequencing. Use for the goal and plan nodes of any playbook. Never writes implementation code.
tools: [Read, Grep, Glob, Bash, Write, Skill]
model: opus
---

You produce specs and plans. You never write implementation code.

**Inputs.** Your dispatch prompt names the run directory, the profile path, and the skills you must load. Read the profile first: it tells you where docs belong (`docsPath`) and which rule packs apply.

**Goal node.** Write `goal.md` covering: the intent in one sentence, who it is for, the value, success metrics, explicit non-goals, and an Open Questions list. Every question in that list must end one of two ways before the plan gate: spiked, or written into `plan.md` as an explicit stated assumption. Never resolve one by guessing.

**Plan node.** Compose `superpowers:writing-plans` rather than reimplementing it. Decompose into tasks that each carry their own test cycle. For every task record: the files it touches, the stack it belongs to (matched against the profile's `stacks` globs), its acceptance criteria, and which tasks it can run in parallel with. The spine uses the stack match to decide which skills each implementer dispatch must load, so a task with no stack match is a planning error - fix it rather than leaving it unmatched.

**Report** back: the artifact paths you wrote, the open questions and how each was resolved, and the parallelizable task set.
```

- [ ] **Step 2: Write `agents/implementer.md`**

```markdown
---
name: implementer
description: Implements one planned task in an isolated worktree, test-first, using exactly the skills named in its dispatch prompt. Serves every stack; the spine decides which competencies to load. Use for implementation and fix-loop nodes.
tools: [Read, Grep, Glob, Bash, Write, Edit, Skill]
model: sonnet
---

You implement ONE task. The spine has already decided which competencies you need.

**Before writing any code:**

1. Invoke `Skill` for every skill named as REQUIRED in your dispatch prompt. Do not write code before they are loaded, and do not substitute your own judgement for the list - if a skill you expected is absent from the list, say so in your report rather than loading it anyway.
2. Read the rule packs the profile names in `rules`. Path-scoped rule packs do NOT auto-load into a subagent, so this Read is not optional.
3. Read the nested `CLAUDE.md` for the app you are working in, if one exists.

**Then:** follow `superpowers:test-driven-development`. Write the failing test, watch it fail, write the minimal code to pass, watch it pass, refactor, commit. Commit small, with an imperative subject, in the worktree you were given.

**Precedence when guidance conflicts:** house rules (the repo's own rule packs) beat vault-generated skills, which beat adopted community skills. When two loaded skills disagree, follow the house rule and note the conflict in your report.

**Report** back: status (DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT / NEEDS_SETUP), files changed, the exact test command and its output, and any concerns. Return `NEEDS_SETUP` if a REQUIRED skill could not be loaded - never improvise a competency you were not given.
```

- [ ] **Step 3: Write `agents/reviewer.md`**

```markdown
---
name: reviewer
description: Reads a diff once and reports ranked findings across every lens the changed files call for - correctness, security, privacy, duplication, and the stack idioms named in its dispatch prompt. Read-only. Use for the review node of any playbook.
tools: [Read, Grep, Glob, Bash, Skill]
model: opus
---

You are read-only. You never edit. You report findings.

**Before reviewing:** invoke `Skill` for every skill named as REQUIRED in your dispatch prompt. The spine derived that list from the extensions present in this diff plus the profile's `always` lenses, so it already covers every lens this change needs. Read the rule packs the profile names.

**Review the diff once**, applying every loaded lens in the same pass. Reading the diff repeatedly per lens is the cost this design exists to avoid.

**Refute before surfacing.** Drop any finding that: does not reproduce, is pre-existing rather than newly introduced by this diff, hits a documented skip-rule or intentional-duplication allowlist, or sits below confidence 0.8. Deduplicate findings that two lenses both raised.

**Report** each surviving finding as: `severity | file:line | failure scenario | rule reference | confidence`. Order blocking, then important, then nit. End with a verdict: **PASS** (no blocking or important findings survive) or **CHANGES-REQUESTED**.

Return `NEEDS_SETUP` instead of a verdict if a REQUIRED lens skill could not be loaded. A review missing a lens is worse than no review, because it reads as coverage that did not happen.
```

- [ ] **Step 4: Validate the agents**

```bash
uv run python -m graphlint .
```

Expected: errors about `graphs/` only (created in Task 10), no agent errors.

- [ ] **Step 5: Commit**

```bash
git add agents
git commit -m "feat: pm-planner, implementer and reviewer agents"
```

### Task 10: The reduced feature playbook

**Files:**
- Create: `graphs/feature.md`

**Interfaces:**
- Consumes: agent names from Task 9; the node schema from Task 6.
- Produces: the playbook `graph-ship` executes in Task 12.

- [ ] **Step 1: Write `graphs/feature.md`**

```markdown
# feature - P1 reduced playbook

The full feature graph adds research, UX, qa and launch nodes in later phases.
This reduced form is deliberately the smallest graph that still proves the
engine: a gate that stops, a fan-out that parallelises, and a reduce that ranks.

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
in: .graph/<run>/tasks/<n>.md
out: worktree commits
gate: no
next: review

## node: review
agent: reviewer
in: the worktree diff
out: .graph/<run>/findings.json
gate: no
next: fix

## node: fix
agent: implementer
in: .graph/<run>/findings.json
out: worktree commits
gate: no
next: merge

## node: merge
agent: pm-planner
in: the reviewed diff and the gate verdict
out: .graph/<run>/ledger.md
gate: yes
next: END
```

- [ ] **Step 2: Validate**

```bash
uv run python -m graphlint .
```

Expected: `OK: 3 agent(s), manifests and playbooks valid`, exit 0.

- [ ] **Step 3: Commit**

```bash
git add graphs/feature.md
git commit -m "feat: reduced feature playbook"
```

### Task 11: /graph-init

**Files:**
- Create: `commands/graph-init.md`

**Interfaces:**
- Consumes: `templates/graph-profile.yaml` from Task 7.
- Produces: `.claude/graph-profile.yaml` in the consumer repo.

- [ ] **Step 1: Write `commands/graph-init.md`**

```markdown
---
description: Scan this repo and write a graph-engineering profile - the stack map, skill routing table, rule paths, gates and local-agent overrides that every playbook run reads.
argument-hint: "[--force]"
disable-model-invocation: true
---

# /graph-init - write this repo's graph profile

Produces `.claude/graph-profile.yaml`. The profile belongs to the repo and is never touched by a plugin update; the engine belongs to the plugin. That split is what makes updates safe.

## Steps

1. **Refuse to clobber.** If `.claude/graph-profile.yaml` exists and `--force` was not passed, print the existing profile's stack list and stop. Overwriting a hand-edited profile silently is the one unrecoverable thing this command could do.
2. **Detect stacks.** Look for `package.json` (inspect `dependencies` for react, next, nest), `pyproject.toml` / `uv.lock`, `go.mod`, `*.xcodeproj` / `Package.swift`, `build.gradle.kts`, and `supabase/` or `migrations/`. Map each hit to a stack entry with the glob that actually contains it - in a monorepo that is `apps/*/web/**`, not `**`.
3. **Detect existing agents.** List `.claude/agents/*.md`. For each plugin role (`implementer`, `reviewer`, `pm-planner`), if a local agent plainly covers that role for a stack, propose it as a `localAgents` override. This is the additive contract: where the repo already has an agent, the engine defers to it.
4. **Detect rule packs.** Glob `.claude/rules/*.md` and any nested `CLAUDE.md`; record them under `rules`.
5. **Detect the docs convention.** If the repo has no `docs/` but does have another specs directory, set `docsPath` to it rather than assuming `docs/`.
6. **Build the routing table** from `templates/graph-profile.yaml`, keeping only the rows whose extensions actually occur in this repo. An unused row is a lie about what the repo contains.
7. **Show the owner the proposed profile and stop for approval.** Write it only after they approve.
8. **Validate** the written file with `python -m graphlint` and report the result.
```

- [ ] **Step 2: Commit**

```bash
git add commands/graph-init.md
git commit -m "feat: /graph-init command"
```

### Task 12: /graph-ship and the first real run

**Files:**
- Create: `commands/graph-ship.md`, `README.md`

**Interfaces:**
- Consumes: `graphs/feature.md`, the three agents, `.claude/graph-profile.yaml`.
- Produces: a completed run under `.graph/<run-id>/` in a consumer repo.

- [ ] **Step 1: Write `commands/graph-ship.md`**

```markdown
---
description: Run a named playbook end to end - execute its nodes, honor its gates, dispatch each agent with the skills its task requires, and keep a resumable ledger.
argument-hint: "<goal> [--graph feature] [--auto-merge] [--resume <run-id>]"
---

# /graph-ship - the engine

Execute a playbook. The engine is playbook-agnostic: it reads `graphs/<name>.md` and runs whatever nodes it finds. It does not know what a feature is.

## Steps

1. **Load context.** Read `.claude/graph-profile.yaml` (if absent, tell the owner to run `/graph-init` and stop) and `graphs/<name>.md`, defaulting to `feature`.
2. **Open the run.** Create `.graph/<run-id>/` with a UUIDv7 run id, copy the playbook into it, and start `ledger.md` with every node marked `pending`. On `--resume`, read the existing ledger instead and skip nodes marked `done`.
3. **Execute nodes in order.** Nodes sharing a `next` target are dispatched in parallel - one message, several Task calls.
4. **Dispatch discipline.** For each node, resolve the agent through `localAgents` first, then the plugin roster. Derive the REQUIRED skill list from the profile's `routing` table matched against that task's files, plus the `always` entries, and name them in the dispatch prompt as non-optional. The agent never chooses; that decision lives here. Also pass: the run directory, the profile path, the node's `in` artifacts, and the acceptance criteria for the task.
5. **Honor gates.** A node with `gate: yes` stops and presents its artifact for the owner's approval before anything downstream runs. `--auto-merge` relaxes only the merge gate, only for this run, and only when zero blocking or important findings survive.
6. **Handle NEEDS_SETUP.** If an agent reports it, stop that leg and tell the owner which skill or dependency is missing. Do not re-dispatch without it and do not let the agent improvise the competency.
7. **Fix loop.** Re-dispatch the implementer for each blocking and important finding, then re-run the review node scoped to the same diff. At most 3 rounds; surface anything that survives as a labelled list. Nits never block.
8. **Update the ledger** after every node: status, artifact path, timestamp. This is what makes a run survive compaction and what `--resume` reads.
9. **Report** the run id, each node's status, and the gate verdict.
```

- [ ] **Step 2: Write `README.md`**

Cover: what the plugin is (one paragraph), install (`/plugin marketplace add shonpazarker/graph-engineering` then `/plugin install graph-engineering@graph-engineering`, user scope), the dev loop as decided by the Task 2 spike, `/graph-init` then `/graph-ship`, and the roster and playbook tables from the spec. State plainly that the profile belongs to the consumer repo and survives plugin updates.

- [ ] **Step 3: Validate and install**

```bash
uv run pytest && uv run python -m graphlint .
```

Then install the plugin by whichever method the Task 2 spike established.

- [ ] **Step 4: Run one real koach task through the graph**

In `~/projects/fitness`: run `/graph-init`, approve the profile, then `/graph-ship "<a small real task>"`.

Verify by inspection, not by assumption:
- the plan gate actually stopped and waited;
- `.graph/<run-id>/ledger.md` records every node;
- the implementer's report names the skills it loaded, and they match the profile's routing rows for the files it touched;
- the reviewer returned a verdict with findings in the documented format;
- koach's own `/ship`, agents and rules are untouched.

- [ ] **Step 5: Record the run and commit**

Write `docs/superpowers/spikes/2026-08-31-first-koach-run.md` with the run id, what worked, and every place the engine needed a nudge - each nudge is a P2 requirement.

```bash
git add commands/graph-ship.md README.md docs/superpowers/spikes/
git commit -m "feat: /graph-ship engine and first koach run"
```

---

## Self-Review

**Spec coverage.** Sections covered by this plan: 2.2 spine routing (Tasks 9, 12), 3 roster subset (Task 9), 3.1 enablement gate and NEEDS_SETUP (Tasks 9, 12), 5 playbook schema (Tasks 6, 10), 6 run state and ledger (Task 12), 6.1 spike protocol (Task 9 pm-planner, Phase 0), 7 profile (Tasks 7, 11), 8 gates (Tasks 10, 12), 10 distribution (Tasks 4, 12), 11 open questions (Tasks 1-3), 13 verification (Task 12 step 4).

Deferred by design, each to its named phase: sections 4.1-4.5 skill sourcing and the content stack (P2, P5), 5.2-5.4 the bug, launch and content playbooks (P5), 9 board sync (P4), the researcher, ux-designer, qa, media-producer and content-writer agents (P2, P3, P5).

**Placeholders.** None. Every code step carries the code; every command step carries the command. The one prose-only step is Task 12 Step 2 (README), whose content is enumerated rather than shown because it restates tables already in the spec.

**Type consistency.** `validate_manifest(repo_root)`, `validate_agent(path)`, `agent_names(agents_dir)`, `parse_playbook(path) -> (nodes, errors)`, `validate_playbook(path, known_agents)`, `validate_profile(path, known_agents)`, `main(argv) -> int`. The CLI in Task 8 calls exactly these signatures. Node dict keys (`id`, `agent`, `in`, `out`, `gate`, `next`) are identical in Task 6's parser, Task 6's tests and Task 10's playbook.
