# graph-engineering

An AI-native software organization as a Claude Code plugin: a roster of agents, a
library of competencies, and playbooks that put them to work. Installed once,
updated from one repo, reused across every project.

## What it is

Four layers, each replaceable without touching the others:

```
COMPETENCIES (skills)   routed per task by the profile's routing table
        |
ROSTER (agents)         reused by every playbook
        |
PLAYBOOKS (graphs)      feature | bug | launch | content
        |
ENGINE (/graph-ship)    playbook-agnostic: run nodes, honor gates, keep a ledger
```

The engine does not know what a feature is. It reads a playbook and runs the
nodes it finds, which is why a bug workflow and a content workflow are new
markdown files rather than new branches in the engine.

## Install

```
/plugin marketplace add ShonP/graph-engineering
/plugin install graph-engineering@graph-engineering
```

User scope. Updates arrive with `/plugin update`.

## Develop

```
claude --plugin-dir ~/projects/graph-engineering
```

Loads the working copy for that session with no install step, additively
alongside your installed plugins, and takes precedence over an installed plugin
of the same name. Edit, restart, test. No commit needed.

## Use

```
/graph-init            # once per repo: writes .claude/graph-profile.yaml
/graph-ship "<goal>"   # run the feature playbook
```

`/graph-ship --resume <run-id>` picks a run back up from its ledger.
`/graph-ship --auto-merge` relaxes only the merge gate, only for that run.

## Roster

Shipped today:

| Agent | Model | Job |
|---|---|---|
| `planner` | fable | spec, then task-decomposed plan with per-task sizing; never writes code |
| `implementer` | opus | one non-trivial task, test-first, with spine-named skills |
| `implementer-simple` | sonnet | one SMALL task (mechanical, 1-2 files); escalates instead of pushing through |
| `reviewer` | opus | reads the diff once through every lens it needs |

The engine picks the implementer by the task's `size` in the plan: `small` goes
to `implementer-simple`, everything else to `implementer`.

Planned (later phases):

| Agent | Phase | Job |
|---|---|---|
| `researcher` | P2 | spikes and open-question answers with strict turn budgets |
| `ux-designer` | P2 | flows, states and copy before implementation |
| `qa` | P3 | end-to-end verification (Playwright, API checks) after review passes |
| `media-producer` | P4 | demo videos and images (Playwright recordings, Remotion) |
| `content-writer` | P4 | short-attention posts for X/LinkedIn from shipped work |

## The profile is yours

`.claude/graph-profile.yaml` lives in your repo. A plugin update replaces agents,
skills and playbooks and never rewrites it. `localAgents` in that file makes the
engine defer to agents your repo already owns, so this plugin is additive rather
than a migration.

## Design

`docs/superpowers/specs/2026-08-31-graph-engineering-plugin-design.md` records
the decisions and, more usefully, what was rejected and why.
