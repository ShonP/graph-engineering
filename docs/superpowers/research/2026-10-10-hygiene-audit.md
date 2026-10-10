# Hygiene audit: what to improve, shrink or remove

Run `01a125bc` (research lane, standard preset, three read-only leaves: usage, friction, weight).
Plugin 0.17.2 (`origin/master` e475071), audited 2026-10-10. The usage leaf parsed 3,708 local
transcripts (2026-09-10 to 2026-10-10, names and counts only); the friction leaf read 43 runs
across the repos on this machine. Follows up the 2026-10-05 noise audit.

**Nothing in this report has been applied.** Each row waits for the owner's approve / decline.

## Recommendation

Almost nothing that ships is dead: all 11 agents, all 5 playbooks, every `graph-control`
subcommand and 66 of 72 skills ran in the last 30 days, and no file added since 0.15.1 is an
orphan. Deleting files buys little. The cost is in three places, in this order:

1. **The review/fix loop** (63% of reviewed tasks needed a CHANGES round on 2026-10-09; 46% of
   important or blocking findings were untested guards). The levers for it shipped in 0.16.3 and
   0.17.0 and are measured on 2026-10-20; the cheapest next step is the retro proposals that
   recurred and were never applied (I1-I4).
2. **Per-dispatch prompt weight** in the roles dispatched most (implementer 828, reviewer 873
   dispatches in 30 days): `definition-of-done` preloaded into 5 roles, `implementer-simple` at
   85% of `implementer`'s load, `qa-verification` long lines (S1-S4).
3. **The profile template**, now 702 lines with 428 of comments (S5, the 2026-10-05 C7, grown).

No removal is recommended on local evidence. Zero-use items are listed for owner confirmation
across machines (R1-R3), per the rule that this machine's transcripts are not all usage.

## Candidates

### Improve (behaviour)

| # | Item | Evidence | Action | Saves | Risk |
|---|---|---|---|---|---|
| I1 | `classes.md` is never written by a script | Engine docs (`docs/engine/run.md` step 7) say the engine appends it; no writer in `scripts/`; 3 later retros in another repo report it absent; present in only 6 of 15 runs in a second repo | `graph-control` writes one row per findings round (deterministic, from `findings.*.json`) | retro re-derivation tokens every non-fast-path retro | low |
| I2 | Skills-observation receipt (retro G6) | Proposed in two separate retros, no commit found | apply the retro diff | one engine hand-repair per run | low |
| I3 | qa validates its own findings file before returning (retro K4 / C4) | Recurred in two runs, no commit found | `qa` and `qa-lead` run `graph-control findings <file>` before their report line | one re-dispatch per occurrence | low |
| I4 | Guard-poll-loop hook denies only implementer subagents (retro K2) | `hooks/README.md:14`; proposal unapplied | widen to every Bash-capable subagent with the pinned bypass forms | idle polling turns in qa and reviewer | false denies; needs its test fixtures |
| I5 | `SKILLS_MISSING` on repo-local skill names | 4 runs, 3 of them repo-local names (a Flutter baseline, i18n); one left not re-dispatched | `skills-check` (or the router) treats names the profile marks repo-local as bare and checks them as such | one wasted re-dispatch per occurrence | low |
| I6 | Dispatches naming skills that do not ship | `graph-engineering:accessibility-review` (4 loads, 1 REQUIRED) and `graph-engineering:playwright-e2e-testing` (1); traced to a plan in another repo that invented the name | `validate-briefs` rejects a REQUIRED `graph-engineering:<name>` that is not in the plugin's skill list | a turn per bad dispatch | none |
| I7 | Older unapplied retro diffs: G1 depth-after-verdict, G4 dangling-pointer lint, G5 count cap, C3 report-missing, C5 `agents/**` as instruction path | Listed as unapplied in a 2026-10-0x retro; grep finds no commit | triage after 2026-10-20: lint-shaped ones first (retro lint-tier share median ~55% says guards beat prose) | per item | each needs its spike first |

### Shrink (prompt weight)

| # | Item | Evidence | Action | Saves | Risk |
|---|---|---|---|---|---|
| S1 | `definition-of-done` preloaded in 5 roles | 8.6k chars, injected ~1,848 times in 30 days; largest repeated cost | tighten to a table plus pointers; note the open edge-case run (`01a125a9`) adds a section here, so do this after it merges and size both together | ~0.5-1k tokens x every planner, implementer and reviewer dispatch | medium: reviewer rows read it; pins in `skills/process/definition-of-done/tests/` |
| S2 | `implementer-simple` load is 85% of `implementer` | 6.3k vs 7.4k tokens; preloads `impact-map` that the planner already stamped into the brief | drop the `impact-map` preload from `implementer-simple` (brief carries the rows) | ~1.5k tokens per simple dispatch (218 in 30 days) | medium: mid-task triage text lives in impact-map; keep a one-line pointer |
| S3 | `qa-verification/SKILL.md:55` | one ~1.8k-char line with "(spiked)" narration; loaded by every qa and qa-lead | split into a rule list, drop narration (2026-10-05 C5 remainder) | ~100 tokens, readability | low |
| S4 | `turborepo/SKILL.md:45` "Measured (npm 11.12.1)" | dated aside | trim to the rule | ~30 tokens | none |
| S5 | `templates/graph-profile.yaml` comments (2026-10-05 C7, grown) | 702 lines, 428 comments | shrink each block comment to ~5 lines plus a pointer to the owning skill | ~3-5k tokens per `/graph-init` and doctor read | low: `test_profile_template`, `test_profile_parallel` pin the `derived:` block |
| S6 | Research-leaf rules in two files (2026-10-05 C9) | `agents/researcher.md:23-25` and `graphs/research.md:28-34` | keep leaf rules in the agent, coordinator duties and the pinned blocklist in the playbook | ~150 tokens | low: `test_engine_loop.py:152` |

### Remove: owner confirm across machines (no local evidence is enough)

| # | Item | Evidence on this machine | Ask |
|---|---|---|---|
| R1 | `nats` | 1 load + 2 self-loads in 30 days; no active routing (commented out in one profile) | used on another machine? |
| R2 | `sdd-ready-queue` skill + workflow + doc | 1 invocation in 30 days; no playbook uses it; single caller chain with a test | still wanted beside the engine's own ready queue? |
| R3 | `pydantic-ai-harness` | 0 loads, routed by no local profile | **keep**: owner confirmed use on another machine (2026-10-05, again 2026-10-10) |

### Keep (checked, not worth changing)

- Every agent, playbook and `graph-control` subcommand: used. Lowest: `reviewer-lead` 4 and
  `qa-lead` 9 dispatches (the scale paths), `qa-lanes` 1 call (new in 0.17).
- Zero-load but routed skills: `activitykit`, `building-pydantic-ai-agents`, `loguru`,
  `microsoft-agent-framework`, `sqlalchemy`; the infra/observability skills that show zero only in
  the 5-day window. They serve repos that route them.
- `/graph-doctor` slash command: 0 slash invocations, but its logic runs 50 times through
  `graph-control doctor` and the SessionStart hook.
- Reviewer depth: the 10-09 retro says the cost is fix rounds, not reviews (5-9 min).
- Simulator lifecycle code (~1.1k lines + ~900 test lines): every file has a caller and tests;
  review it for value only if iOS runs stop.
- Shared report paragraph across agents: pinned byte for byte on purpose.

## Evidence per dimension

- **Usage** (leaf 1, ANSWERED; local transcripts, rung: primary data): counts of Skill tool
  calls, `<command-name>` injections, Agent `subagent_type`, Bash `graph-control <sub>`. Ledgers by
  playbook: feature 29, research 7, quick 6, bug 2, infra 1.
- **Friction** (leaf 2, PARTIAL; run ledgers and retros, rung: primary data, keyword greps over
  free-form ledgers, medium confidence): `run-report.md` and `classes.md` bodies not read.
- **Weight** (leaf 3, ANSWERED; `origin/master` tree, rung: primary): chars/4 token estimates,
  SKILL.md bodies only, `references/` excluded. 2026-10-05 audit: C1, C2, C3, C4, C6, C10, C11
  done; C5 partly; C7 and C9 open.

## Evidence against

- **"Over-loading" of `prior-art` (1,015 loads vs 259 REQUIRED) and `ux-evidence` (818 vs 340) is
  probably not waste.** The owner's global CLAUDE.md tells the main thread to run prior-art on
  every ask, and main-thread loads were counted with subagent loads. Not split by thread, so no
  action is proposed; see Unverified.
- Counts overstate use: preload injections and repeated loads in one dispatch both count.
- "Unapplied" retro items rest on grep of `origin/master` for each proposal; a diff applied under
  another name would be missed.
- Retro proposals from 2026-10-09 were applied in bulk (0.16.3, 0.17.0), which argues the backlog
  is older items, not a habit of ignoring retros.

## Unverified

| Claim | Smallest experiment |
|---|---|
| `prior-art` / `ux-evidence` extra loads are main-thread, not subagents picking their own skills | re-run the usage parser split by main vs subagent transcript |
| Hook usage per plugin | one-line counter in each hook script for a week |
| G1-G6, K-, C- items truly unapplied | `git grep` each retro diff's proposed test name |
| S1/S2 savings hold without quality loss | the edge-case run's eval set (planner and reviewer cases) re-run after the shrink |
| Shell-guard rule restated in three files | diff `qa-verification:55`, `hooks/scripts/plugin_shell.py` messages, `hooks/README.md` |
| 0.16.3 / 0.17.0 levers reduced fix rounds | signals read due 2026-10-20 |

Leaf reports: `.graph/01a125bc-e1fa-797c-88cd-46d70f95756f/research/{1,2,3}.md` (git-ignored).
