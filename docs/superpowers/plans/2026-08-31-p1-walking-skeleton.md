# Graph Engineering P1 - Walking Skeleton (markdown only)

**Goal:** An installable plugin that runs one real koach task end to end through a reduced `feature` playbook: goal -> plan -> owner gate -> implementer -> reviewer -> merge gate.

**Architecture:** Markdown only. Agents, playbooks and commands are files Claude reads; there is no code and no build step. Correctness is established by running the graph on real work, not by a test suite.

**Spec:** `docs/superpowers/specs/2026-08-31-graph-engineering-plugin-design.md`

**Supersedes:** the P0+P1 plan of the same date, whose Tasks 4-8 built a Python
validator (`graphlint`). That was cut on 2026-08-31 as disproportionate: five of
twelve tasks and every review round spent on a linter that ships in a plugin
Claude Code never executes. The three P0 spikes it contained are answered and
recorded in `docs/superpowers/spikes/`.

## Global Constraints

- Everything is markdown or YAML. No Python, no build step, no test runner.
- Agent `name:` frontmatter equals the filename stem. Agents live flat in `agents/`; they do not nest-discover.
- Models: `opus` for `reviewer` and `pm-planner`, `sonnet` for `implementer`. `haiku` never.
- No em dashes in any authored file.
- The spine names each agent's required skills in the dispatch prompt. An agent never chooses its own conditional skills.
- Unconditional competencies go in `skills:` frontmatter; conditional ones are spine-named. (Spike 2026-08-31: preloading works, bare names suffice.)
- Run state lives in the CONSUMER repo at `.graph/<run-id>/`, never here.
- The profile belongs to the consumer repo; a plugin update never rewrites it.
- Dev loop and the first koach run both use `claude --plugin-dir ~/projects/graph-engineering`. No install step. (Spike 2026-08-31.)

## Verification

There is no test suite, so verification is explicit and manual:

1. Each authored file is read back and checked against the properties listed in its task.
2. The plugin loads via `--plugin-dir` and `/graph-ship` appears.
3. **Task 5 is the real gate:** one genuine koach task runs through the graph, and the run is inspected against named criteria. A skeleton that does not carry real work is not done.

---

### Task 1: The three agents

**Files:** create `agents/pm-planner.md`, `agents/implementer.md`, `agents/reviewer.md`

Each carries frontmatter (`name`, `description`, `tools`, `model`, and `skills` only where a competency is unconditional) and a body stating its contract.

- [ ] **`pm-planner`** (opus; Read, Grep, Glob, Bash, Write, Skill). Produces specs and plans; never writes implementation code. Two phases: `goal.md` (intent, audience, value, success metrics, non-goals, Open Questions) and `plan.md` (composing `superpowers:writing-plans`, not reimplementing it). Every open question ends spiked or written down as an explicit assumption - never silently resolved. Each task records files, stack (matched to the profile's `stacks` globs), acceptance criteria, and its parallel set. A task with no stack match is a planning error, because the spine derives skill routing from that match.
- [ ] **`implementer`** (sonnet; Read, Grep, Glob, Bash, Write, Edit, Skill). Implements ONE task. Before writing code: invoke `Skill` for every REQUIRED skill named in the dispatch, then Read the rule packs the profile names (path-scoped packs do not auto-load into a subagent). Then `superpowers:test-driven-development`. Precedence on conflict: house > vault-generated > community. Reports DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT / NEEDS_SETUP, and returns `NEEDS_SETUP` rather than improvising a competency it was not given.
- [ ] **`reviewer`** (opus; Read, Grep, Glob, Bash, Skill). Read-only. Preloads `review-protocol`, `security-review`, `privacy-review` in `skills:` frontmatter, since the profile's `always` lenses fire on every diff. Stack lenses arrive spine-named. Reads the diff ONCE applying every loaded lens in one pass - re-reading per lens is the cost this design exists to avoid. Refutes before surfacing: drops findings that do not reproduce, are pre-existing, hit a skip-rule, or sit below confidence 0.8. Reports `severity | file:line | failure scenario | rule reference | confidence`, ordered blocking, important, nit. Verdict PASS or CHANGES-REQUESTED. Returns `NEEDS_SETUP` instead of a verdict if a REQUIRED lens could not load, because a review missing a lens reads as coverage that did not happen.

**Check:** three files; names match stems; models correct; only `reviewer` and `pm-planner` carry `skills:`; no em dashes.

### Task 2: The reduced feature playbook

**Files:** create `graphs/feature.md`

Six nodes, each `## node: <id>` followed by `agent`, `in`, `out`, `gate`, `next`:

`goal` (pm-planner, gate no) -> `plan` (pm-planner, **gate yes**) -> `implement` (implementer) -> `review` (reviewer) -> `fix` (implementer) -> `merge` (pm-planner, **gate yes**) -> END.

Open with a short note saying this is the reduced form and which nodes the full graph adds later (research, UX, qa, launch), so a reader is not left wondering what happened to the spec's diagram.

**Check:** every `agent` value is one of the three files from Task 1; every `next` names a node in the file or `END`; every node is reachable from `goal`; a path reaches `END`.

### Task 3: The profile and /graph-init

**Files:** create `templates/graph-profile.yaml`, `commands/graph-init.md`

- [ ] **Template** carrying `stacks`, `rules`, `docsPath`, `routing` (with an `always` entry), `localAgents`, `gates` (plan, design, merge, publication) and `board`. Comment it: this file belongs to the repo and survives plugin updates.
- [ ] **`/graph-init`** (`disable-model-invocation: true`). Refuses to clobber an existing profile without `--force`, because silently overwriting a hand-edited profile is the one unrecoverable thing it could do. Detects stacks from lockfiles and project files; maps each to the glob that actually contains it, not `**`. Detects existing `.claude/agents/*.md` and proposes them as `localAgents` overrides - this is the additive contract. Detects rule packs and the repo's docs convention. Keeps only routing rows whose extensions actually occur. Shows the proposed profile and stops for approval before writing.

### Task 4: /graph-ship and the README

**Files:** create `commands/graph-ship.md`, `README.md`

- [ ] **`/graph-ship`** - the engine, playbook-agnostic: it reads `graphs/<name>.md` and runs the nodes it finds. It does not know what a feature is. Steps: load profile (absent -> tell the owner to run `/graph-init` and stop) and playbook; open `.graph/<run-id>/` with a UUIDv7 id, copy the playbook in, start `ledger.md` with every node `pending`; execute nodes in order, dispatching nodes that share a `next` target in parallel in one message; resolve each agent through `localAgents` first then the plugin roster; derive REQUIRED skills from the profile's `routing` matched against the task's files plus `always`, and name them in the dispatch as non-optional; stop at every `gate: yes` node for the owner; on `NEEDS_SETUP`, stop that leg and name the missing skill rather than let the agent improvise; fix loop of at most 3 rounds, nits never blocking; update the ledger after every node; report run id, per-node status, and the gate verdict. `--auto-merge` relaxes only the merge gate, only for that run, only with zero blocking or important findings. `--resume <run-id>` reads the ledger and skips `done` nodes.
- [ ] **README** - what the plugin is, install via marketplace, the `--plugin-dir` dev loop, `/graph-init` then `/graph-ship`, the roster and playbook tables, and the profile-versus-engine ownership split.

### Task 5: First real koach run - the actual gate

**Files:** create `docs/superpowers/runs/2026-08-31-first-koach-run.md`

- [ ] Start a session with `claude --plugin-dir ~/projects/graph-engineering` in `~/projects/fitness`.
- [ ] Run `/graph-init`, review the proposed profile, approve it.
- [ ] Run `/graph-ship "<a small real task>"`.
- [ ] Verify by inspection, not assumption: the plan gate actually stopped and waited; `.graph/<run-id>/ledger.md` records every node; the implementer's report names the skills it loaded and they match the profile's routing rows for the files it touched; the reviewer returned a verdict in the documented format; koach's own `/ship`, agents and rules are untouched.
- [ ] Write the run up, including every place the engine needed a nudge. Each nudge is a P2 requirement, and this file is the evidence P2 is planned from.
