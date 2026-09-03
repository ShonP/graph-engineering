# Graph Engineering Plugin - Design

Date: 2026-08-31
Status: approved for planning
Owner: Shon Pazarker

## 1. Purpose

A single, versioned Claude Code plugin that carries an AI-native software
organization - a roster of agents, a library of competencies (skills), and a
set of playbooks (graphs) that put them to work. Installed once per machine,
updated from one repo, reused across every project.

Today this capability exists only inside `~/projects/fitness/.claude` (koach):
a proven `/ship` loop, 13 agents, 14 commands, 13 rule packs, 60 skills. It is
not portable, and it covers one workflow (ship a feature) out of the several
that matter.

### Goals

1. One repo to change. A fix to a reviewer or a skill lands in every project
   on the next `/plugin update`.
2. Many workflows, one roster. Feature, bug, launch and content work all draw
   on the same agents and skills.
3. Lean agent context. An agent holds only the competencies its current task
   needs - this is what makes parallel fan-out affordable.
4. Additive. Koach's existing `.claude/` keeps working untouched; the plugin
   supplies the nodes koach lacks and defers to koach's agents where they exist.
5. Nothing silently guessed. Every open question is either spiked or recorded
   as an explicit assumption before the plan gate.

### Non-goals

- Replacing koach's `.claude/` (explicitly rejected; additive was chosen).
- Deploy automation. Production verification is a checklist, not a deployer.
- A general workflow engine. Playbooks are markdown with a strict node schema,
  executed by a skill - not a new runtime.
- `product-intent` playbook (recursive, spawns child feature runs). v2.

## 2. Architecture

Four layers, each replaceable without touching the others.

```
COMPETENCIES (skills)   ~35, routed per task by the profile's routing table
        |
ROSTER (agents)         8 definitions, reused by every playbook
        |
PLAYBOOKS (graphs)      feature | bug | launch | content
        |
ENGINE (/graph-ship)    playbook-agnostic: execute nodes, honor gates,
                        write the ledger, sync the board, resume
```

The engine is deliberately playbook-agnostic. Bolting branches onto a feature
loop was rejected: `content` involves no code at all, and `launch` involves no
implementation, so a feature-shaped spine cannot express them.

### 2.1 Orchestration

Hybrid. A skill drives the spine so approval gates stay interactive; parallel
subagent dispatch carries the fan-out legs; run state lives on disk so a run
survives compaction and resumes after a crash.

Rejected alternatives:

- Pure markdown loop (koach's `/ship` today): no resume, and fan-out fidelity
  depends on the model remembering to batch dispatches.
- The Workflow tool: strongest map-reduce guarantees, but it runs in the
  background, so the plan and design approval gates could not be interactive.
  Those gates are the point.

### 2.2 The spine routes; agents do not

The engine computes each agent's skill load list from the profile's routing
table and the task's file paths, then names those skills in the dispatch prompt
as non-optional:

```
Task 3: add HealthKit sync toggle. Files: apps/koach/ios/Settings/**
REQUIRED: invoke Skill for swiftui-pro, swift-concurrency, healthkit
before writing any code. Do not write code before these load.
```

This is why one `implementer` definition can serve every stack. An agent that
chooses its own skills can skip loading and write from priors - the exact
failure koach's preloaded `skills:` frontmatter was defending against. Moving
the decision to the spine removes both the routing tax and the discipline risk.
Adding Go later is one routing row plus its skills: no new agent, no engine
change.

### 2.3 Unconditional competencies preload; conditional ones route

Preloading a plugin-local skill into a plugin agent works (spike, 2026-08-31),
so the routing rule in 2.2 gains an exception that costs nothing:

> **A competency an agent loads on every dispatch is declared in its `skills:`
> frontmatter. A competency that depends on the task is named by the spine.**

| Agent | Preloaded | Spine-routed |
|---|---|---|
| `reviewer` | `review-protocol`, `security-review`, `privacy-review` | stack lenses, by file extension |
| `planner` | `product-spec` | - |
| `qa` | `test-strategy` | playwright / api-contract / mobile-ui |
| `content-writer` | `content-strategy`, house voice | platform skill, by target |
| `implementer` | nothing - no competency is unconditional across stacks | everything |
| `researcher` | nothing - one skill per mode, and the mode is the dispatch | everything |
| `ux-designer` | `design-rubric` | mockup and visual skills |
| `media-producer` | nothing - medium decides | everything |

This does not weaken 2.2. Conditional skills are still named by the spine, so
an agent can never skip a load and write from priors; the exception only
removes a pointless hop for competencies that were never in question. The
reviewer is the hot path and gains the most: three fewer `Skill` invocations on
every review.

## 3. Roster

Eight agents. `releaser` was considered and dissolved: documentation, release
notes and social posts are one competency (writing), demo video is another
(media), and production verification belongs to qa.

| Agent | Model | Modes / routing | Writes? |
|---|---|---|---|
| `planner` | fable | product intent, spec, roadmap, task decomposition | specs only |
| `researcher` | sonnet | `ux` \| `tech` \| `competitor` \| `spike` | reports only |
| `ux-designer` | sonnet | mockups, design rubric | mockups only |
| `implementer` | opus | stack skills routed from task paths | yes |
| `implementer-simple` | sonnet | same routing; small bounded tasks only, escalates otherwise | yes |
| `reviewer` | opus | lens skills routed from diff extensions | no (read-only) |
| `qa` | sonnet | playwright / api-contract / mobile-ui / prod-verify | tests only |
| `media-producer` | sonnet | short-attention media: demo video, social cuts, screenshots, generated images | assets only |
| `content-writer` | sonnet | LinkedIn, X, blog, docs, release notes | copy only |

Models follow the standing policy (2026-08-31): fable plans, opus implements non-trivial tasks and reviews, sonnet implements small bounded tasks (`implementer-simple`), haiku never. The planner marks each task `small` or `standard`; the engine routes accordingly.

### 3.1 Skill floor and the enablement gate

An agent with no real competency is a prompt in a costume. Therefore:

> **Agent enablement gate.** An agent is enabled in a playbook only when its
> skill floor is met. Below floor it returns `NEEDS_SETUP` and does not
> improvise. `/graph-doctor` reports every agent's floor status.

Audited status at design time:

| Agent | Competencies available now | Verdict |
|---|---|---|
| `implementer` | tanstack-query-rules, tanstack-router, supabase, supabase-postgres-best-practices, swiftui-pro, 25x compose-*, frontend-rules, backend-rules, architecture-resilience-rules, swift-ios-skills x3, cloudflare | strong |
| `reviewer` | review-testing-rules, koach REVIEW.md + 13 rule packs, swift-concurrency-pro, Trail of Bits x22 (adopt) | strong |
| `qa` | `qa-verification` (authored 2026-08-31, evidence-per-criterion protocol), stack qa routing, superpowers TDD + verification | strong |
| `ux-designer` | `ux-journey` (harvested 2026-08-31 from koach /ux-research), explore mode in the agent body; house design system via profile rules | strong |
| `media-producer` | `short-attention-media` (authored 2026-08-31: 1.3s hook, length caps, captions, media-as-code, frame verification - distilled from koach creating-demo-videos + short-form research) | strong |
| `planner` | superpowers:brainstorming, superpowers:writing-plans | partial; owns none |
| `content-writer` | `short-form-posts` (harvested 2026-08-31 from koach writing-short-form-posts, voice doc scrubbed to `profile.content.voiceDoc`) + x-mechanics reference | good; gap: docs/release-notes |
| `researcher` | mode protocols in the agent body (authored 2026-08-31), `ux-journey` for ux mode, spike protocol §6.1 | strong |

Full roster shipped 2026-08-31; remaining gaps get their skills authored in the
phase that first needs them - never deferred past the phase that enables the leg:

- `docs-writer`, `release-notes` -> P5 (launch)
- `content-strategy` (generated from the Hormozi vault) -> P5 (launch/content)

`ui-ux-pro-max` (1.8MB data+scripts) was deliberately NOT vendored: the plugin
is markdown-only, and its UX-judgment value was distilled into `ux-journey` +
the explore mode. A repo that has it keeps using it through its own rules.

`task-decomposition` is explicitly NOT authored: `superpowers:writing-plans`
already is that skill.

## 4. Competencies (skills)

### 4.1 Sourcing policy

Each phase opens with a sourcing pass for the skills that phase needs: search
the indexes, then adopt / adapt / write - never author what a better version
already exists for. Indexes:

- VoltAgent/awesome-agent-skills (1000+; official packs from Anthropic, Vercel,
  Stripe, Cloudflare, Netlify, Sentry, Figma, Expo; Trail of Bits x22 security)
- anthropics/skills (official)
- QA: neonwatty/qa-skills, voidmatcha/e2e-skills, agentmantis/test-skills,
  TestDino playwright-skill
- Board: wscffaa/claude-gh-skills (Issues, PRs, Projects v2, Kanban sync)

### 4.2 Dependency model

Adopted skills are **depended on**, not vendored. `plugin.json` supports this
natively (spike, 2026-08-31):

```json
{ "dependencies": ["qa-skills", { "name": "linkedin-skills", "version": "~1.2.0" }] }
```

Entries are a bare plugin name, or an object with `name` and a semver `version`
constraint. Version constraints answer most of the risk this section originally
accepted without a mitigation.

Residual consequence: within a version constraint, an external maintainer can
still change agent behavior, and a fresh machine needs every dependency
installed before the graph works. Mitigations:

1. `/graph-doctor` verifies required plugins are installed and names which
   graph legs degrade if one is missing.
2. The profile records which upstream skill each routing row expects.
3. A leg whose skill is absent reports `NEEDS_SETUP` rather than silently
   reviewing with no lens. This is the enablement gate applied to dependencies.
4. Pin every dependency with a semver constraint, never a bare name, so an
   upstream major cannot land unreviewed.

Note recorded from the upstream index itself: these lists are curated, not
audited.

### 4.3 Harvesting from koach

Skills already proven in koach move into the plugin and are scrubbed of
koach-isms - `@equival/theme`, he+en i18n, `packages/koach/data` become profile
lookups (`profile.rules`, `profile.stacks.*.paths`). The scrub pass is the main
risk in harvesting and is a named task, not an assumption.

Harvest list: tanstack-query-rules, tanstack-router, supabase,
supabase-postgres-best-practices, swiftui-pro, compose-* (subset),
ui-ux-pro-max, design-rubric, creating-demo-videos, writing-short-form-posts,
plus the five global rule packs (frontend, backend, architecture-resilience,
agent-workflow, review-testing), which are already generic.

### 4.4 Content competency stack

`content-writer` and `media-producer` draw on three layers that are
complementary, not competing:

| Layer | Source | Job |
|---|---|---|
| Strategy | Hormozi vault via `vault-skill-factory` -> `content-strategy` | hook / retain / reward, what earns attention, opening discipline |
| Platform mechanics | sergebulaev/linkedin-skills, sergebulaev/x-skills (MIT, adopt) | the fold, 280 vs thread refit, cadence, AI-tell humanizer |
| House voice | koach `writing-short-form-posts` (harvest) | the voice these posts are actually written in |
| Video hook | viral-short-form-video-master (adopt) -> `media-producer` | 1.3s hook rule, per-platform algorithm notes; applies to feature demos too |

Source pages for the generated strategy skill:
`frameworks/hook-retain-reward-framework`, `frameworks/multimedia-content-method`,
`claims/copywriting-the-opening-of-promotional-content-deserves-disproportionate`,
`topics/retention`, and the short-vs-long-form conversion claims.

Routing: `content-strategy` and the house voice skill are always on for
`content-writer` (cheap, universally applicable); the platform skill loads by
target only - a LinkedIn post never pulls x-skills.

Note: x-skills' 2026 AI-tell list leads with em dashes, which koach already
blocks at pre-push. The rules agree; the house rule remains authoritative.

### 4.5 Competency precedence

Where two skills conflict:

> **house (koach-harvested) > vault-generated > community (adopted).**

A community skill never overrides the house voice, the house rules, or a gate.
The engine states the precedence in every dispatch prompt that loads more than
one overlapping competency.

## 5. Playbooks

One markdown file per playbook, strict node schema, executed by the engine.

```
graphs/bug.md

## node: reproduce
agent: qa
skills: [test-strategy]
in:  bug report
out: .graph/<run>/repro.md
gate: no
next: diagnose

## node: diagnose
agent: implementer
compose: superpowers:systematic-debugging
next: fix
```

Every node declares: `agent`, `mode` (optional), `skills` or `compose`, `in`,
`out`, `gate`, `next`. Nodes with the same `next` target run in parallel.

### 5.1 feature

```
planner: goal.md
  -> [ux-research | tech-research | competitor-research]   MAP, 3 parallel
  -> planner: plan.md
  -> GATE 1: owner approves the plan
  -> need UX? -> ux-designer -> GATE 2: owner approves the design
  -> worktree (superpowers:using-git-worktrees)
  -> [implementer x N]                                     MAP, 1 per task
  -> [reviewer | qa]                                       REDUCE, 2 parallel
  -> refute + dedup + rank -> findings.json
  -> blocking/important? -> fix loop (same implementer, <= 3 rounds)
  -> verify (superpowers:verification-before-completion)
  -> merge gate: owner decides (or --auto-merge if flagged)
  -> invoke launch
```

### 5.2 bug

```
reproduce (qa) -> diagnose (implementer, compose systematic-debugging)
  -> fix (implementer) -> reviewer -> verify -> merge gate
```

No PM node, no research, no UX. Same agents, shorter node list - the payoff of
a playbook-agnostic engine.

### 5.3 launch

Invoked by `feature`'s tail, or standalone against a merged change.

```
[media-producer: demo video + screenshots | content-writer: release notes]
  -> content-writer: social post (LinkedIn, X)
  -> qa: prod-verification checklist
  -> GATE: owner approves publication
  -> board update
```

### 5.4 content

No code involved.

```
topic -> researcher (tech | competitor)
  -> content-writer: draft
  -> media-producer: images (image-gen) / video (remotion or playwright capture)
  -> GATE: owner approves
  -> publish
```

### 5.5 Composition

`feature` invokes `launch` at its tail. In v2, `product-intent` spawns N
`feature` runs as children under one parent run-id. Composition is what makes
this an organization rather than a pipeline, and it is why the engine executes
a named playbook rather than a hardcoded spine.

## 6. Engine and run state

`.graph/<run-id>/` in the consumer repo, gitignored:

```
playbook.md          copy of the playbook this run executes
goal.md
research/{ux,tech,competitor}.md
questions.md         open questions register
spikes/<n>.md        spike answers
plan.md
tasks/<n>.md         per-task brief handed to each implementer
findings.json        {severity, file, line, scenario, rule, confidence, round}
assets/              demo video, screenshots, generated images
ledger.md            node -> status -> artifact path
```

The ledger makes `/graph-resume` work: a re-entered run reads it, skips
completed nodes, and resumes at the first `pending`. Compaction mid-run costs
nothing.

### 6.1 Spike protocol

Any node may raise an open question; the spike node is reentrant.

```
node hits an unknown
  -> logged to questions.md
  -> spike node: researcher --mode spike
       strict budget: one agent, capped
       output is an ANSWER, not code; any code written is labeled THROWAWAY
       and is never merged
  -> spikes/<n>.md: answer + recommendation
  -> folds into plan.md; the blocked node resumes
```

Rule: every open question ends one of two ways before the plan gate - spiked,
or recorded in `plan.md` as an explicit stated assumption. Never silently
guessed.

## 7. Project profile

`/graph-init` scans the repo (lockfiles, `*.xcodeproj`, `go.mod`, an existing
`.claude/`), proposes a profile, and the owner edits it. Agents read it every
run. A plugin update replaces agents and skills but never the profile: the
engine belongs to the plugin, the profile belongs to the repo. That split is
what makes updates safe.

```yaml
# .claude/graph-profile.yaml
stacks:
  web:  { paths: ["apps/*/web/**"] }
  ios:  { paths: ["apps/*/ios/**"] }
rules: [".claude/rules/*.md"]
docsPath: "openwiki/products/{product}/design"   # koach override, not docs/
routing:
  "**/*.{ts,tsx}": { impl:   [react-patterns, tanstack-query, tanstack-router]
                     review: [react-lens, a11y-i18n]
                     qa:     [playwright-e2e] }
  "**/*.swift":    { impl: [swiftui-pro, swift-concurrency]
                     review: [swift-lens], qa: [mobile-ui-test] }
  "**/*.kt":       { impl: [compose-state, compose-performance]
                     review: [compose-lens], qa: [mobile-ui-test] }
  "**/*.py":       { impl: [fastapi-patterns, uv-python]
                     review: [backend-lens], qa: [api-contract] }
  "**/*.sql":      { impl: [db-migrations], review: [db-rls-lens], qa: [] }
  always:          { review: [review-protocol, security-review, privacy-review] }
localAgents:            # additive contract
  implementer: web-implementer     # defer to koach's
  reviewer:    react-reviewer
gates: { plan: owner, design: owner, merge: owner }
board: { platform: github, project: "Koach Graph Runs" }
```

`localAgents` is how "additive" is enforced. Where koach already has an agent
for a leg, the engine dispatches koach's; it supplies its own only for the legs
koach lacks (planner, researcher, ux-designer, qa, media-producer,
content-writer). A fresh repo leaves `localAgents` empty and gets the full
plugin roster.

## 8. Gates

| Gate | Default | Notes |
|---|---|---|
| Plan approval | owner | after research, before any code |
| Design approval | owner | only when the UX branch fires |
| Merge | owner | `--auto-merge` opts a single run into unattended merge |
| Publication | owner | launch and content, before anything goes public |

Merge is owner-gated by default; `/graph-ship --auto-merge` is the deliberate
escape hatch for changes the owner already trusts.

## 9. Board sync

GitHub Projects v2, driven by `gh`, adopting wscffaa/claude-gh-skills. The
board tracks graph runs only - constructing the plugin itself is tracked in its
own plan file.

`.graph/<run-id>/` stays the machine-readable truth; the board is the human
view. The engine writes board state at every node transition: task created ->
Planned, implementer dispatched -> In Progress, review passed -> Done, spike
raised -> its own card in Blocked.

Columns: Backlog | Planned | In Progress | Review | Blocked (spike) | Done.
Fields: run-id, node, agent, stack, playbook.

## 10. Distribution

```
graph-engineering/
  .claude-plugin/{plugin.json, marketplace.json}
  agents/        8 defs, flat (agents do not nest-discover)
  skills/        harvested + authored
  graphs/        feature.md, bug.md, launch.md, content.md
  commands/      graph-init, graph-ship, graph-review, graph-resume, graph-doctor
  templates/     graph-profile.yaml
  README.md
```

Install: `/plugin marketplace add shonpazarker/graph-engineering` then
`/plugin install graph-engineering@graph-engineering`, user scope. Updates
arrive via `/plugin update`, tracked by `gitCommitSha` like every other
marketplace already installed on this machine.

Development loop (spike, 2026-08-31): a local directory is not a valid
marketplace source, but it does not need to be. Start a session with

```bash
claude --plugin-dir ~/projects/graph-engineering
```

which loads the working copy for that session with no install step, additively
alongside the installed plugins, and takes precedence over an installed plugin
of the same name. Edit, restart, test - no commit required.

## 11. Open questions - P0 spikes

Answers recorded in `docs/superpowers/spikes/`.

1. **Answered - yes, under either name form.** A canary plugin with two agents
   differing only in how they name the same plugin-local skill (`spike-canary`
   versus `spike-plugin:spike-canary`) had both return the canary phrase. Bare
   names suffice within a plugin. See section 2.3.
2. **Answered - no, and the answer is better.** A local directory is not a
   marketplace source; `claude --plugin-dir <path>` loads the working copy for
   a session, additively, taking precedence over an installed plugin of the
   same name. See section 10.
3. **Answered - yes.** `plugin.json` has a `dependencies` array with optional
   semver constraints. See section 4.2.

### 11.1 Capabilities the spikes surfaced

The plugins reference documents agent frontmatter fields the design had not
assumed, two of which it should now use:

- **`maxTurns`** - a hard per-agent turn cap. This is the enforcement for the
  spike protocol's "strict budget" in section 6.1, which was prose with no
  mechanism behind it.
- **`isolation: "worktree"`** - an agent can run in its own git worktree,
  possibly cheaper than the spine creating one. To evaluate in P1.
- Also available: `effort`, `disallowedTools`, `background`, `memory`.
- Not available to plugin-shipped agents, for security reasons: `hooks`,
  `mcpServers`, `permissionMode`.

`plugin.json` likewise supports `userConfig` (values prompted at enable time),
which suits the board project name - a per-install value, not a per-repo one.

## 12. Delivery phases

**P0 - Spikes.** The three questions in section 11.

**P1 - Walking skeleton.** Repo, `plugin.json`, `marketplace.json`,
`/graph-init` and the profile schema, and `/graph-ship` executing a reduced
`feature` playbook: goal -> plan -> GATE -> implementer -> reviewer -> merge
gate. Three agents, existing skills only. Ends by shipping one real koach task
through it.

**P2 - Map legs.** researcher x3 modes, spike node and `questions.md`,
ux-designer and the design gate. Authors `competitor-research`, `product-spec`.

**P3 - Reduce legs.** qa agent, qa routing rows, fix loop (<= 3 rounds),
`findings.json`, refute + dedup + rank.

**P4 - Board.** GitHub Projects v2 sync at every node transition,
`/graph-doctor`.

**P5 - Playbooks + release competencies.** `bug`, `launch`, `content`.
media-producer and content-writer enabled. Authors `docs-writer`,
`release-notes`, `remotion-video`; generates `content-strategy` from the
Hormozi vault via `vault-skill-factory`; adopts linkedin-skills, x-skills and
viral-short-form-video-master.

Every phase opens with a skill-sourcing pass and ends with a real task run
through the graph in koach - additive, so koach's own loop is never at risk.

## 13. Verification

- `claude plugin eval` suite asserting the engine's invariants: gates actually
  stop execution; routing loads the right skills and only those; the ledger
  resumes a killed run; an agent below its skill floor returns `NEEDS_SETUP`.
- Per-phase dogfooding in koach on a real task.
- `/graph-doctor` green: every dependency installed, every agent at floor.

## Amendments

### 2026-09-03 - UX evidence house rule

Every change a user can see ships before/after evidence (screenshot pairs, or
≤30s recording pairs for flows), captured as code, committed under the profile's
`uxEvidence.path` and embedded in the PR body. Authored `ux-evidence`
(process); routed on every UI-bearing extension for impl, review and qa; added
as an implementer non-negotiable, a review-protocol always-on lens (missing =
Blocking), a qa row source, and a merge-gate exhibit.

Rejected: a dedicated capture node in the `feature` graph. "Before" only exists
before the code moves, so the capture belongs to whoever is about to move it -
the implementer - not to a node that runs afterwards. `media-producer` still
owns polished launch demos and builds them from the same capture scripts.

### 2026-09-03 - Prior-art house rule; research MAP enters the feature graph

No ask starts from priors. Authored `prior-art` (process): fires at the start
of every task and at mid-task forks; reuse candidates checked before anything
else; a source ladder (ran it > docs with version > maintainer intent > named,
dated, cited author > anonymous); a per-claim skepticism checklist; spikes for
load-bearing claims with VALIDATED / PARTIAL / INVALIDATED verdicts; a
prior-art note in every plan or PR, or a written skip. Preloaded in planner,
`always.impl` in the profile, an always-on review lens, and the researcher's
tech mode now opens with reuse candidates. The §5.1 research MAP (ux | tech |
competitor, parallel) moved from "later phase" into `graphs/feature.md`.

Prior art for the rule itself: Hermes Agent's spike skill (adopted its skip
rule and verdict vocabulary; not a Claude Code skill, so not vendored);
VoltAgent's competitive-analyst subagent (rejected - marketing SWOT, minimal
source skepticism); the plugin's own `researcher` agent (reused - the skill is
a protocol over it, not a second researcher). Rejected: a hard turn budget in
the skill; budgets stay in the dispatch, scaled to the ask.
