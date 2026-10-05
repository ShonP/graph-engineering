# Noise audit: what to delete or shrink

Run `01a10d6b` (research lane, standard preset, three read-only leaves: dead-files, prose-noise
and usage). Plugin 0.15.1 (`f29babd`), audited 2026-10-05. The usage leaf read 1,716 local
transcripts from the last 30 days.

## Recommendation

The code is clean. Every `scripts/graph_control` module, command, hook script and hook fixture
has a live caller or a pinning test, and no content/social code remains. The noise is in three
places:

1. About 3,300 lines of dated history under `docs/superpowers/` and `docs/research/`, which git
   already keeps.
2. Dated "spiked on version X" narration inside prompts that agents load.

Delete the history once its four live links are repointed. Cut the narration down to the rules
it supports. Expect about 3,300 fewer tracked lines and about 1,000 fewer
tokens in prompts, with no change in behavior.

## Candidates, ranked by savings × confidence

| # | Item | Evidence | Action | Saves | Risk |
|---|---|---|---|---|---|
| C1 | `docs/superpowers/plans/**` (four plans plus two findings JSON), `runs/**` (two), `spikes/**` (three) | Shipped or superseded. The only inbound links are `README.md:343`, `hooks/README.md:337` and `skills/observability/loki/SOURCE.md`; no test pins them. `p1-walking-skeleton` and two spikes have zero inbound links. | Delete. Repoint the three links to the CHANGELOG entry or the git tag. | ~2,300 lines | low |
| C2 | `docs/research/2026-09-{10,23,24}-*-sourcing.md` | Each vendored skill's `SOURCE.md` already records its provenance. Links: `README.md:344-347`, `CHANGELOG.md:37,701` (history, leave as is). | Delete. Point the README at `skills/*/SOURCE.md`. | 363 lines | low |
| C3 | `docs/efficiency-implementation.md` | 22-line status note. Only `CHANGELOG.md:298` and the 0.15 plan link to it. | Delete. | 22 lines | none |
| C4 | `docs/superpowers/specs/2026-08-31-graph-engineering-plugin-design.md` | The original design. `README.md:421` and `skills/python/pydantic-house-rules/SKILL.md:51` cite "spec 4.5" from it. | **Owner pick.** Either delete it and inline the one cited rule (house > vault > community precedence, already stated in `agents/implementer.md`), or keep it as the single design record. | ~620 lines | low |
| C5 | Dated spike narration in loaded prompts | `commands/graph-init.md:73,116` (pnpm 10.33.3, npm 11.12.1, yarn 1.22.22, bun 1.3.6, about 280 tokens). `skills/process/infra-verification/SKILL.md:15-17,73-87` (helm/kubeconform versions and two spike logs, about 330 tokens). Single dated asides in `qa-verification/references/harness-contract.md:115`, `post-deploy-verification/SKILL.md:87` and `impact-map/SKILL.md:75`. No test pins them. | Keep the rule and the flag that matters. Move the evidence to CHANGELOG or delete it. | ~700 tokens per load | low |
| C6 | `Harvested from the owner's global rule packs on 2026-09-10` (line 7 of five `skills/rules/*/SKILL.md`) | Provenance only. Not pinned. | Delete the line. | ~5 lines, loaded every dispatch that reads a pack | none |
| C7 | `templates/graph-profile.yaml` comments: `runtime.up` (lines 43-112, 70 lines) and `deploy` (lines 127-160) | Loaded only by `/graph-init`, which already restates the compose-isolation rules in step 4. `test_profile_template.py:93-104` parses the `derived:` block, which stays. | Shrink each comment to about 15 lines and point to `qa-verification`. | ~900 tokens per init | low; check `test_profile_template` and `test_profile_parallel` for pinned comment text |
| C9 | Research-leaf rules (budget, firewall, claims-to-disk) stated in both `agents/researcher.md:23-26` and `graphs/research.md:25-40` | Restated in two files. The blocklist wording in `research.md` is pinned by `test_engine_loop.py:152`. | Keep the leaf rules in the agent and the coordinator duties plus the pinned blocklist in the playbook. | ~150 tokens | low |
| C10 | `.worktrees/` is untracked and not ignored | `git check-ignore` returns nothing. | Add one `.gitignore` line. | hygiene | none |
| C11 | `docs/research/2026-10-05-run-throughput-analysis.md` (this session, untracked) | It sits outside `docsPath` (`docs/superpowers`). | Move it to `docs/superpowers/research/` when run `01a10d5a` lands. | 0 | none |

## Kept on purpose (claims refuted or not worth it)

- **Shared report paragraph in the 10 agent prompts.** The prose leaf priced it at about 400
  tokens per dispatch. That is refuted: a dispatch loads only its own agent file, so repeating
  the paragraph across files costs maintenance, not tokens. `test_roster_policy.py:39-46` pins it
  byte for byte so every role gets the same contract. Merging it into a shared skill would add a
  skill load to every dispatch.
- **Unreferenced vendored reference files.** Eight files under `skills/android/compose-*/references`
  (about 80 KB) are kept. Trimming upstream payloads breaks the refresh-from-`SOURCE.md` contract,
  so the next refresh would bring them back.
- **`skills/ux/ui-ux-pro-max`** (1.9 MB): `search.py` reads `data/` at runtime.
  **`skills/temporal`**: every reference is linked.
- **Zero-load but routed skills:** `sqlalchemy`, `loguru`, `schemathesis`, `infra-verification`,
  `post-deploy-verification`, `building-pydantic-ai-agents`, `microsoft-agent-framework`,
  `push-notifications`, `photokit`, `widgetkit` and `activitykit` serve repos that route them.
- **`skills/python/pydantic-ai-harness`** (was C8): zero loads on this machine, but the owner
  confirmed (2026-10-05) that it is used on another machine. Usage data here covers this
  machine's transcripts only, so a zero-load result alone never justifies deleting a skill.
- **`qa-lead`** (no dispatch yet): it is the scale path for multi-lane qa.
- **`validate-attempts`, `fingerprint`, `record-receipt`, `verify`** (no Bash invocation seen):
  `docs/engine/run.md` steps 4 and 7 require them.
- **`doctor.py:77-78` stale-key detection for content/social:** it is the upgrade path, pinned by
  `test_doctor.py:116-117`. Revisit at 0.17.
- **`docs/ux/changes/**`:** the house rule requires ux-evidence, and `test_digest.py` builds
  synthetic `docs/ux/changes` paths in a temp dir, so the real files are not needed by tests.
  They stay because they are the evidence of shipped UI changes.

## Evidence against

- `guard-destructive` produced no recorded output in 30 days. That is consistent with "silent
  unless it blocks", but it could also mean it never fires. This was not checked here; it is a
  scratch-repo spike if it matters.
- Skill load counts double count (tool use plus name markers), so treat them as a ranking.
  Zero-load claims hold: zero is still zero.
- Pins inside `skills/**/tests` were not exhaustively checked for C5. The cleanup run's
  `run-all-tests` will catch any.

## Unverified

- **Usage outside this machine.** The usage leaf read only local transcripts. Any zero-use
  claim needs the owner's confirmation for other machines.

## Outside this repo (owner's call, noted only)

- `~/.claude/CLAUDE.md` still lists `content-writer` and `media-producer` as roster agents. They
  ran twice each in 30 days, from user-level agents, but the plugin dropped content on
  2026-09-23.
- Sessions asked for skills that do not exist: `short-form-posts`, `accessibility-review` and
  `playwright-e2e-testing` (1-4 requests each).
