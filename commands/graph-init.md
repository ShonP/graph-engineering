---
description: Scan this repo and write a graph-engineering profile - the stack map, skill routing table, rule paths, gates and local-agent overrides that every playbook run reads.
argument-hint: "[--force]"
disable-model-invocation: true
---

# /graph-init - write this repo's graph profile

Produces `.claude/graph-profile.yaml` from `templates/graph-profile.yaml`.

## Steps

1. **Refuse to clobber.** If `.claude/graph-profile.yaml` exists and `--force` was not passed, print its current stack list and stop. Silently overwriting a hand-edited profile is the one unrecoverable thing this command could do.

2. **Detect stacks.** Look for `package.json` (read `dependencies` for react, next, nest), `pyproject.toml` / `uv.lock`, `go.mod`, `*.xcodeproj` / `Package.swift`, `build.gradle.kts`, and `supabase/` or `migrations/`. Map each hit to the glob that actually contains it. In a monorepo that is `apps/*/web/**`, not `**`.

3. **Detect existing agents.** List `.claude/agents/*.md`. Where a local agent plainly covers a plugin role for a stack, propose it as a `localAgents` override. This is the additive contract: the engine defers to what the repo already has and supplies only the legs it lacks.

4. **Detect rule packs.** Glob `.claude/rules/*.md` and any nested `CLAUDE.md`. Record them under `rules`.

5. **Detect the docs convention.** If the repo has no `docs/` but has another specs directory, set `docsPath` to it rather than assuming.

6. **Build the routing table,** keeping only rows whose extensions actually occur in this repo. A row for a stack the repo does not contain is a lie about what is here, and it will route an agent to a competency that cannot help it.

7. **Show the proposed profile and stop for approval.** Write only after the owner approves. Then tell them to run `/graph-ship`.
