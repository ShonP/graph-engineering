# Changelog

Notable changes to the graph-engineering plugin. Skills vendored from upstream
keep their own `CHANGELOG.md` beside them; this file covers the plugin.

Releasing is the owner's: bump `version` in `.claude-plugin/plugin.json` and move
the entries below under that number. An entry sitting in Unreleased has not
shipped to any install yet — `claude plugin update` compares versions, not
commits.

## [Unreleased]

## [0.16.0] - 2026-10-06

Throughput. Implementation runs as a ready queue instead of waves, every task
carries a budget, implementers stop at a time-box with their green work, and the
inner loop is fast: focused tests while iterating, the full suite once.

**Upgrading.** `preflight` requires a run's `plugin_version` to equal the
installed plugin's, so a run opened on 0.15.1 fails it after the upgrade with
`run plugin version differs from executing helper`. Finish in-flight runs before
upgrading. To continue one on 0.16.0 anyway, set `plugin_version` in its
`run.json` by hand, then re-run every recorded check with `graph-control
record-receipt`: the edit changes the run fingerprint, so earlier receipts fail
with `receipt belongs to a different run contract`. A plan that uses the new
task budget keys needs 0.16.0: 0.15.1 rejects unknown task keys.

### Added

- **Ready queue.** `graph-control ready <plan.json> --done <ids> [--running
  <ids>] [--max-width N] [--hold <ids>]` prints the tasks that may start now,
  longest remaining chain first, capped at the width minus the running count.
  `--hold` lists started tasks that hold no writer slot (in review, merged
  awaiting their gate, parked): never offered again, not counted against the
  width, and not releasing their dependents. `validate-plan` prints
  `critical_path` beside `tasks` and `cases`. The engine (`docs/engine/run.md`
  step 3) keeps at most 4 writers in flight, dispatches implementers with
  `run_in_background: true` and refills a slot on every completion. A
  task-state table names the flag each state is passed under; a writer that
  returns BLOCKED, NEEDS_CONTEXT or NEEDS_SETUP is `parked`. Each task gets its
  own worktree, review leg and fix loop, merges in completion order behind a
  repo gate per merge batch, and releases its dependents only after that gate
  passes. qa runs once per merge unit. Review rounds and `classes.md` rows are
  per task: `findings.<task>.json` and `findings.<task>.r<N>.json`, named in the
  playbooks and the `retro` skill. `waves` stays as a display aid; status NEXT
  shows the ready set.
- **Task budget.** Plans at `schema_version` 2 take optional task keys
  `estimate_min` (1-45),
  `path_cap_reason` (required once an estimated task names more than 8
  `writable_paths`) and `proof` (`focused`, `full_device` or `cluster`; a
  proving task builds nothing). The planner sizes every task, splits one that
  cannot fit, keeps the critical path short and shows its depth at the plan
  gate. `docs/graph-controls.md` documents the keys and `ready`.
- **Implementer time-box and `PARTIAL`.** Implementers work inside 45 minutes
  from their first tool call. At the limit they commit green work and return
  `PARTIAL` with `green_commit`, `done_cases`, `remaining_cases`,
  `remaining_scope` and `elapsed_min`; the engine turns the rest into a
  remainder task `<id>b` wired into the original's dependents. Nothing green
  reports the dispatch base SHA as `green_commit`. `implementer-simple` follows
  the same rules and keeps `ESCALATE`.
- **Fast inner loop.** Implementers run focused tests while iterating and the
  full suite once at the end; full device, cluster and integration proof moves
  to qa or the merge gate unless the plan marks `proof`. `wait-run.sh --full`
  counts full-suite starts per `GRAPH_RUN_ID` in
  `${GRAPH_WAIT_RUN_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/graph-engineering/wait-run}/<GRAPH_RUN_ID>.full`:
  two are free, a third needs `--reason "<why>"`. A new PreToolUse hook,
  `guard-poll-loop.sh`, denies an implementer subagent's shell loop that runs
  `sleep` and points it at `wait-run.sh`; it fails open and never blocks the
  main thread. Kill switch: `GRAPH_POLL_GUARD=off` under `env` in Claude Code
  settings.
- **Lane slots and per-task namespaces.** A lane's slots count independent
  instances; a task that can have its own namespace (from `GRAPH_RUN_ID`, as
  `<run>-t<n>`) uses one instead of a lane, and whole-cluster work is a qa
  proving task or the merge gate. `/graph-init` proposes slots from evidence,
  and `host-check` runs before each implementer dispatch.
- **`/graph-engineering:sdd-ready-queue`**, a plugin workflow that runs a
  hand-written plan on a ready queue: one worktree per task from the run branch
  head, at most 4 writers, review with up to 3 fix rounds, serialized merges,
  `PARTIAL` remainders, and an agent-free dry run. See `docs/sdd-workflows.md`.
- **`scripts/throughput.py`**, the success-signal adapter for this release:
  `implementer-p90-active`, `implementer-over-90` and `workflow-concurrency`
  over local subagent transcripts, one aggregate per call.

### Changed

- The `host-check` load warning says to lower the ready-queue width
  (`--max-width`) instead of narrowing a wave.
- Repository noise removed: dated plans, runs, spikes, sourcing notes and the
  original design spec (git keeps them); dated spike narration cut from loaded
  prompts; the rule-pack provenance line dropped; the profile template's
  runtime and deploy comments shortened.

## [0.15.1] - 2026-10-03

The destructive-command guard no longer interrupts bypass-mode runs.

### Changed

- **The destructive-command guard is silent in `bypassPermissions` mode.** A
  hook's `ask` forced a prompt even under bypass and stopped unattended runs.
  The guard now reads `permission_mode` from the PreToolUse input and stands
  down there; every other mode still asks.

## [0.15.0] - 2026-09-30

Efficiency, a front door, parallelism and the full loop. `/graph-ship` routes
every ask into a lane sized to it and loads only its router; the Stop and lint
hooks are opt-in and run at most once per prompt; waves and nested leads run in
parallel; research, success signals and a guard-first retro close the loop.
Opus replaces fable everywhere: the profile's `policy:` block is the one source
of model tiers, and haiku, fable and `general-purpose` are blocked.

### Added

- **Three frontend competencies in `skills/react/`**, written from pinned vendor
  docs plus rung-1 measurements on the exact versions (sourcing pass:
  `docs/research/2026-09-24-frontend-skills-sourcing.md`; every upstream
  candidate rejected with the lack named).
  - `tailwind` - Tailwind 4.3.3: the `@theme` token preset with the palette
    reset, light and dark values that flip without `dark:`, why `@theme inline`
    breaks that, `@source` for workspace packages, the no-literal-colour check
    (shipped as `scripts/check-no-literal-colours.sh`, tokens read from the
    preset, fixture-tested by `check-skill-scripts.sh`),
    and `cn()` configured so tailwind-merge 3.7.0 stops dropping a colour next to
    a custom `text-*` size.
  - `forms-i18n` - react-hook-form 7.88 + zod 4 + `@hookform/resolvers` 5.9
    (the resolver path never moved; zod's did), the accessible `Field`,
    validation messages as keys with a zod `customError` fallback, i18next 26 +
    react-i18next 17 init, typed keys, and the DOM-walk test for hard-coded copy.
  - `turborepo` - turbo 2.11.3 + pnpm 12.6.0: pipelines, `outputs`, remote cache
    off by config, `--frozen-lockfile`, filters, and the rule that every package
    declares `lint` and `typecheck` (otherwise the PostToolUse hook runs
    `turbo run lint <file>` at the root and fails).
- Template routing: `**/*.css` -> `tailwind`; `**/{i18n,locales}/**` and
  `**/*.{form,forms}.tsx` -> `forms-i18n`; `**/turbo.json`,
  `pnpm-workspace.yaml`, `**/package.json` -> `turborepo`; the
  `**/*.{ts,tsx}` row's `impl` and `review` gain `tailwind` and `forms-i18n`.
- `frontend-rules` defers colour and dark mode to `tailwind` (tokens in the
  `@theme` preset flip themselves; `dark:` only for non-colour) and catalogue
  paths to `forms-i18n` (`i18n/<ns>.<lng>.json`).
- Destructive-command guard (`hooks/scripts/guard-destructive.sh`): asks the
  owner to confirm, showing evidence, before a git remote removal, a force push
  without a lease, a Docker volume delete, or a recursive rm on /, $HOME, a repo
  root, a .git path or Docker data. Any other command passes a bash-only check
  (about 4 ms, no python).
- graph-control: new subcommands are plug-in modules under
  `scripts/graph_control/commands/`, so `cli.py` no longer needs editing. New
  `guard-agent` PreToolUse(Agent|Task) policy hook: blocks `general-purpose` and
  never-listed models, sets role model tiers through `updatedInput`, logs
  `policy-override:` lines to `.graph/ledger.md`, does nothing without a profile
  `policy:` block, and fails open on errors.
- `scripts/check-agent-frontmatter.sh` checks agent frontmatter keys, the model
  tier (opus or sonnet only), tools, maxTurns, omitClaudeMd, qualified skill
  names and graph node agents. `scripts/run-all-tests.sh` is one test runner
  that finds new suites on its own and is now the only step in CI. A suite's
  own `requirements.txt` adds its pins (wcmatch for `tests/graph_control`), and
  any skipped test makes the run read `partial` instead of `complete`.
- `retro` roster agent (sonnet, `maxTurns: 40`, preloads only
  `graph-engineering:retro`) for the retro node when something leaked.
- `/graph-doctor` and `graph-control doctor --root <repo> [--quick]`: read-only
  findings, each with a fix, for the profile's schema_version, removed keys,
  runtime, `graph-checks.json`, policy tiers, gate risk ids, routing skills, the
  `.graph` ignore line, and a plugin version that differs from the installed
  one. A new SessionStart hook (`doctor-on-start.sh`, `startup` only, cached
  per project in the git common dir, fail-open, timeout 5 s) prints at most 3
  finding lines, or a `/graph-init` hint in a git repo that has a stack marker
  and no profile.
- `graph-control depth --root --base --profile` picks the review depth (`lint`,
  `single` or `panel`) from `git diff` against the base, the profile's `risk:`
  rows, `instructionPaths`, `review.panel_lines` and `review.seams`, and reports
  the matched `risk_rows` the merge gate reads. The new `risk` module is the
  one reader of the risk table: a row matches on a path glob, or on a keyword
  spelled exactly (case-sensitive) in an added line of a non-prose file, or a
  `re:` keyword's Python regex; a row with no paths and no keywords is a
  placeholder that matches nothing. `wcmatch==11.0.1`
  is now pinned in the entry point. `--plan <run>/plan.json` evaluates the
  `outside-the-run` row (a changed path in no task's `writable_paths`), which
  the merge gate's condition (a) now passes. `lint` is prose by file type only
  (`*.md`, `*.markdown`, `*.rst`, `*.adoc`, and named files such as README or
  LICENSE): `docs/**` and other `*.txt` files, such as `requirements.txt`,
  `CMakeLists.txt` or a Sphinx `docs/conf.py`, get a review.
- `graph-control findings <path>... [--counts]` validates `findings.json` and
  `qa-findings.json` (schema v1: a route on every finding) and totals the open
  findings; a missing file is BLOCKED (exit 1), never zero.
- `graph-control status` and `python3 -m graph_control.status --line`: a status
  line that costs no tokens and lists live subagents (type, model, idle age
  with `!` past 10 min, grouped by `<run8>:<node>`), plus NEEDS YOU decision
  cards and cost by agent type, cached for 5 s and parsed incrementally.
  The session is `--session <id>`, else the status-line stdin JSON
  (`transcript_path`, `session_id`), else the newest one, so concurrent
  sessions in one checkout each show their own agents.
  `session_usage.py` gains `--session`, `--role`, `--run` and per-role
  `--medians`.
- `graphs/quick.md`: the small-ask playbook for the router's `quick` lane.
- qa harness contract (`qa-verification/references/harness-contract.md`) and
  the tested `templates/qa-harness.sh` for a consumer's `runtime.command`. It
  guards the run id and worktree root, keeps evidence per case, tears down on
  every exit, writes a JSON report, and runs an axe audit through
  playwright-cli. The plugin ships only this generic contract. Login and
  throwaway-user helpers live in the consumer repo.
- `graph-control waves <plan.json> [--max-width N]` splits a plan into
  dispatch waves by dependency level, keeps plan order inside each level and
  splits a level wider than N (default 4) into consecutive sub-waves. The level
  loop is now `Plan.levels()`, which plan validation reuses, so its error
  messages are unchanged.
- Host lanes: `scripts/lane-run.sh <lane> [--slots N] [--wait-seconds S] --
  <argv>` serializes work that competes for one host resource (a build, a
  shared database, a cluster) with fcntl slot locks held by the command itself,
  so a killed job never leaves a stale lock; a busy lane exits 75.
  `scripts/worktree-gc.sh [--apply --prefix <p>] [--base <ref>]` removes
  merged, clean linked worktrees and never forces. `--apply` needs `--prefix`
  (the engine passes `--base <run branch> --prefix <run-id>-`, the full run
  id, as runs opened in the same minute share a UUIDv7's first 8 characters),
  so it never removes another session's worktrees; a worktree at the base tip has no
  commits of its own and is always kept. `graph-control host-check --root <repo>
  [--min-free-gb 20] [--profile <profile>]` reports low disk (BLOCKED), high
  load, a bare repo, a default branch behind its upstream (local refs only)
  and a docker it cannot reach.
- `hooks/scripts/wait-run.sh --log <absolute path> [--max-block S] [--
  <argv>]`, a bounded blocking wait for suites longer than one tool call. It
  starts argv detached, blocks up to 270 s per call (clamped to 590 s) and
  prints one line, `wait-run: exit=<n>|running state=complete|partial ...`,
  plus the log tail on failure. Exit 75 means still running; call again
  without argv to attach. The job survives the caller being killed.
- `qa-lead` agent (sonnet, `maxTurns: 150`): when a merge unit's criteria span
  2 lanes, 2+ platforms, or ~8+ criteria across 3+ lanes, it stands the runtime up
  once, runs up to 4 `qa` leaves in parallel (one message, foreground), merges
  their file reports into `qa.md` and `qa-findings.json`, and runs `down`
  last. `qa` gains a leaf mode and `qa-verification` documents the trigger.
- `reviewer-lead` agent (opus, `maxTurns: 120`) for panel review of large
  diffs: it splits the diff into at most 4 slices, dispatches one opus
  reviewer leaf per slice in one message, then merges, dedupes (same file,
  lines within 3, same rule) and reproduces each blocker into one
  `findings.json`. `reviewer` gains a leaf mode and `review-protocol` a Panel
  section: the lead runs above ~2,000 changed lines or ~120k diff tokens;
  below that one reviewer gets an explicit lens list and must reproduce every
  blocker.
- `researcher-spike` agent (sonnet, `maxTurns: 25`, `omitClaudeMd: true`) for
  the researcher's spike mode: a dispatch contract that carries everything
  since CLAUDE.md is omitted, VALIDATED/PARTIAL/INVALIDATED verdicts naming the
  edge case tried, and a never-bypass-owner-guards rule. No token saving is
  claimed until measured.
- plan.json schema v2: optional `success_signals` (goal, source
  `prometheus|sentry|sql-readonly|command`, argv `command`, a
  `value <op> <number>` or `value <op> baseline * <number> [+ <number>]`
  condition, `window_days` 1-90), or `[]` with a `success_signals_reason`.
  Signal goals are unique, since measures are keyed by goal. New
  `graph-control validate-briefs <run-dir>` blocks a missing or blank brief, a
  brief over 300 lines or one over 35% fenced code. run.json, receipts and
  state stay at schema 1.
- Success measures after merge: `scripts/measure_signals.py` checks a run's
  `success_signals` once their window has passed. Commands run as argv with a
  60 s timeout, and only a single number (or `{"value": n}`) is accepted, so
  row-level output is never stored. Results go to `measure.md` and the ledger,
  once per signal; `--remeasure` replaces a signal's row on purpose.
  `--baseline --now <deployedAt>` records `post-deploy/baseline.json`, and
  `--due <repo>` lists the runs whose measures are due without running
  anything. The SessionStart handoff hook prints that due line, and never starts
  Python in a repo with no `.graph/*/plan.json`. `post-deploy-verification`
  checks take `source: prometheus | sentry | sql-readonly | command`, and bug
  runs re-probe the reproduce request when `vet_smoke.py` passes it.
- `graph-control digest --root --base [--plan] [--profile]`: a read-only,
  git-only change digest of at most 60 lines of markdown. A small diff gets a
  stat grouped by plan task; a large one gets LOC without `digest.exclude`, new
  public surfaces, top-5 churn x LOC hotspots and ux evidence. The full
  `graph-control status` now shows DONE since last look and NEXT, read from
  plan.json, run.json and receipts.json.
- **`graph-control render`** generates `docs/playbooks.md` from `graphs/*.md`:
  one Mermaid `flowchart LR` per playbook, with gate nodes as hexagons and
  `when:` labels on conditional edges. `render --check` returns BLOCKED on
  drift, and the test suite runs it. `docs/img/playbook.png` is removed.
- Mutation witnesses now go through
  `skills/process/review-protocol/scripts/mutate-witness.sh`. It tests one
  mutant in a throwaway `git worktree add --detach` of HEAD, never the working
  tree. It refuses a dirty tree, requires the test to pass on HEAD first, caps
  each run and kills the test's whole process group, and writes a JSON receipt.
  Implementers list a receipt for each new guard or validation. Reviewers treat
  a surviving mutant, or a new guard with no receipt, as Important.
- `scripts/lint-no-plan-numbers.sh [--base <ref>] [paths...]` bans plan, task,
  wave and ADR numbers in code comments across stacks (comments found by file
  extension; string literals and prose skipped).
- **Skill receipt.** Every roster agent with the Skill tool returns one line,
  `skills_loaded: <fully qualified names>`, and after each dispatch that named
  REQUIRED skills the engine runs `graph-control skills-check --required ...
  --loaded ...` (no model, no file read). A miss marks the node
  `SKILLS_MISSING: <names>` and re-dispatches once (exit 1); a malformed line is
  BLOCKED (exit 2) and re-dispatched once asking for the exact format; a second
  failure goes to the owner. A qualified `plugin:skill` is proven only by the
  identical name, a bare one only by the identical bare name; the parser drops
  backticks and `(annotations)`. So routing names plugin skills qualified:
  the template does, and `check-routing-resolves.sh` and doctor's
  `routing-bare` flag a bare one, since it can resolve to a host built-in. Why: in 30 days of
  sessions, 15 of 102 subagents that edited `.tsx` never loaded a React or
  TanStack skill, and dispatches that REQUIRED `bruno` loaded it 1 of 3 times.

### Changed

- **`/graph-ship` routes each ask by size and risk** into five lanes: `answer`,
  `direct`, `quick`, `full` and `spike`. Any `risk:` row match forces at least
  `quick`. It adds decision cards and merge gates by risk class:
  `gates.auto_classes` auto-merges on full green only after the owner opts in,
  and the template default `[]` keeps every merge with the owner. A `direct`
  change lands without asking only when `graph-control depth` reports no risk
  row and `auto_classes` holds `none`; an owner's `--lane direct` over a risk
  row still waits for the owner. The profile's
  `integration: pr | push-main` picks how approved work lands. Replies follow a
  5-line contract, and the full report is written to
  `.graph/<run>/run-report.md`, so it no longer overwrites the bug playbook's
  `report.md`.
- The SessionStart handoff hook prints the reply contract when a profile
  exists, warns when `docs/HANDOFF.md` is over 150 lines, and stays silent on
  resume, fork and `--agent` sessions.
- **Profile schema v2**: the template adds `schema_version: 2` and one generic
  `risk:` table of 10 rows (path globs plus literal keywords), shared by the
  router, review depth and gates. `spend` keywords are provider call spellings
  (`stripe.`, `Stripe(`), so `table-striped` or `recharge` never gate a merge. It also adds `gates.owner_classes` and
  `gates.auto_classes`, `integration`, `localLanes`, `instructionPaths`,
  `review`, `ownerAccess` and `ci.parity`. `content` and `gates.publication` are
  removed. `/graph-init --upgrade` edits an existing profile as text and writes
  only after the owner approves the diff. Routing is derived from every
  manifest through the template's dependency table. /graph-init also proposes
  `.claude/graph-checks.json` (test rows for pytest via uv or poetry, `swift
  test`, `./gradlew test`, `./mvnw test` and `mvn test` beside npm, task, make,
  go and cargo), env pins and deny rules for `settings.json`, and a `.gitignore`
  line.
- The Stop hook reuses the test verdict when the tree has not changed. The
  verdict is keyed on the git state (commit, uncommitted and untracked files),
  the test argv and the bytes of `graph-checks.json`, and stored in
  `<git common dir>/graph-engineering/checks-state.json`. A pass, fail or
  timeout on the same tree is replayed without running the suite.
  `graph-control check <root> --reuse` returns the stored verdict without
  running anything. Any nonempty `GRAPH_CHECKS_NO_MEMO` turns the memo off.
- Review findings are a validated `findings.json`, and qa writes
  `qa-findings.json` in the same shape. `review-protocol` defines the routes
  (`patch`, `bad_plan`, `intent_gap`, `defer`; nits are always `defer`), the
  re-review input (the open findings plus the diff of the fix commits), the
  round-3 escalation, and review depth set by `instructionPaths`. The reviewer
  writes the file with Write.
- qa verdicts are honest. Rows end `VERIFIED`, `FAILED` or `BLOCKED`, and any
  other status reads as `BLOCKED`. The verdict is `PASS`, `FAIL INCOMPLETE` or
  `INCOMPLETE`, and qa runs once per merge unit or wave. `definition-of-done`
  gains Refactor, Outbound messaging and Host blast radius rows, plus
  env-parity, clean-checkout and background-cost cells. `impact-map`'s
  Contracts section covers outbound effects and predicate producers and
  consumers. `prior-art` treats memory files as rung 5 claims.

- **Breaking: Stop and PostToolUse hooks are opt-in** through
  `.claude/graph-checks.json` (`test`, `precheck`, `lint` with `{file}` and
  `extensions`; template at `templates/graph-checks.json`). The Stop check runs
  at most once per prompt and waits while background tasks run. Timeouts report
  "not verified" instead of blocking. Both hooks find the file from the edited
  file or the session cwd upward, so workspace repos and linked worktrees use
  their own, and a repo without one starts no Python. Script autodetection
  (`pyproject.toml`, `package.json`, `Taskfile.yml`) and the whole-project
  typecheck on every edit are removed.
- hooks: `hooks.json` registers async lint, the three-handler destructive-command
  guard (`Bash(git *)`, so `git -C <dir> push -f` is reached), the Agent|Task
  policy guard, an `asyncRewake` Stop gate, and SessionStart limited to
  `startup|clear|compact`. `hooks/README.md` documents
  the opt-in `.claude/graph-checks.json` contract and states that 0.15 breaks
  0.14 autodetect.
- Roster runs on opus/sonnet only (planner moves from fable to opus), with
  qualified `graph-engineering:` preloads, `maxTurns` caps, a shared return
  contract, a reviewer preload check and `findings=` verdict line, and qa
  `INCOMPLETE:` verdicts.
- Profile template is generic for any stack: `stacks` ships empty, a new
  `policy:` block is the single source of model tiers (opus for planning,
  design, implementation and review; sonnet for simple implementation,
  research, qa and retro; haiku and fable never allowed; general-purpose agents
  blocked), and framework skills are routed from dependency-derived rows that
  /graph-init applies per manifest instead of from file extensions.
- Engine dispatch: the profile's `policy.roles` is the only model-tier source;
  REQUIRED skills use full `graph-engineering:` names; dispatches have five
  parts and a `<run8>:<node>` label; fix rounds are fresh dispatches and round 3
  moves up one tier; children return at most 1,500 tokens; the engine writes the
  merge exhibit itself (`agent: engine`) and a one-line retro when no findings
  leaked, otherwise it dispatches the `retro` agent.
- `docs/efficiency-implementation.md` item 3 (reduce repeated context and
  unconditional research) marked resolved.
- **`/graph-ship` runs plan tasks in waves**: `graph-control waves` with at
  most 4 concurrent opus writers, `host-check` before each wave, every task of a
  wave dispatched in one message in the foreground, one repo gate per wave
  (`check --reuse`, else the suite through `wait-run.sh`), and commands on a
  declared lane wrapped by `lane-run.sh`. A wave with 2+ writers gives each
  task its own worktree, branched from the run branch head SHA and bootstrapped
  from the profile; branches merge back with `--no-ff` in plan order and
  `worktree-gc.sh --apply --base <run branch> --prefix <run-id>-` removes that
  run's merged task worktrees after each merge. Spikes dispatch
  `researcher-spike` with a brief that carries the profile, skills, rule packs
  and invariants. Step 4 adds the qa-lead and reviewer-lead triggers
  (leads at depth 1 only), transient-error retries (3 attempts, stop fan-out on
  the first 429), and a token and wall-time estimate at the plan gate with
  actuals at the merge gate.
- Profile template gains `bootstrap: []` (commands run in each new task
  worktree) and `lanes: {}` (serialized host resources). `policy.roles` adds
  `reviewer-lead` (opus), `qa-lead` (sonnet) and `researcher-spike` (sonnet).
  `/graph-init` proposes `bootstrap` from lockfiles (a Yarn 1 `yarn.lock` gets
  `--frozen-lockfile`, since Yarn classic ignores `--immutable`) and `lanes`
  only on evidence: an Xcode project, `infra.cluster`, or a runtime not
  isolated per `GRAPH_RUN_ID`.
- The `guard-agent` fallback tiers and its deny message include the three new
  agents; a test pins them to the template's `policy.roles` and the `agents/`
  directory. `docs/graph-controls.md` notes that `host-check`'s `docker info`
  can reach a remote `DOCKER_HOST`.
- **`/graph-ship` has three new lanes**: investigate (a signals-mode researcher
  writes a one-page pulse digest, the owner ranks items once, and each chosen
  item routes to direct, quick or bug), research (the new `graphs/research.md`,
  with quick/standard/deep presets of 1/3/6 leaves, a firewall, a
  `claims.jsonl` file and an Evidence against section), and a slim product
  preset that ends at a go / kill / clarify gate. The engine also appends
  finding classes to `classes.md` after each round, re-checks `success_signals`
  at post-deploy against `baseline.json`, measures due long-window signals at
  the start of the next run, and puts the change digest in the merge exhibit.
- Researcher: a `signals` mode runs the profile's `pulse.command` exactly as
  written and writes a one-page digest of aggregates and pseudonymised ids.
  Research leaves get a brief-only firewall, per-leaf tool and turn budgets,
  claims appended to `research/claims.jsonl` every 5 items, and Evidence against
  / Unverified sections. Planner: `concept.md` for the product preset,
  `success_signals` (or `[]` plus `success_signals_reason`) in plan.json v2, the
  contract task first, and task briefs capped at 300 lines and 35% fenced code.
  product-spec gains Options, Riskiest assumption, Completeness checklist and a
  Signal line. The profile template adds `pulse.command` and `digest.exclude`.
- Retro is guard-first: engine fast path, `.graph/<run>/classes.md` input,
  recurring classes promoted as a test fixture, semgrep rule or lint config
  before any prose line, prose retired once guarded, and a reported lint-tier
  share.
- **`/graph-ship` loads only the router.** `commands/graph-ship.md` is step 1
  (7.3 KB, a tested 8,000-byte budget, down from 34 KB on every call). Steps
  2-8 and 10 are `docs/engine/run.md`, read once per run by the lanes that open
  a run dir; step 9 is `docs/engine/land.md`, read at a merge gate and when a
  `direct` change lands; the `direct` and `investigate` rules are
  `docs/engine/lanes.md`. Step numbers are unchanged.
- **The `lint` review depth is used.** The engine runs `graph-control depth`
  before each review leg: at `lint` (prose only, no risk row) it runs the
  repo's configured `lint.argv` on the changed files, writes `findings.json`
  and records the review receipt itself, and dispatches no reviewer; `single`
  is one reviewer; `panel` keeps the lead rule.
- **BREAKING: the agent control plane is always owner-gated.** A built-in,
  reserved `agent-control` risk row covers `**/.claude/**`, `**/CLAUDE.md`,
  `**/AGENTS.md`, `**/.mcp.json`, `.github/**` and the profile's
  `instructionPaths`. `graph-control depth` always reports it, so such a diff
  is never class `none` or depth `lint` (a CLAUDE.md edit is now `panel`); it
  never auto-merges, even under `--auto-merge`, and the router forces at least
  `quick`. A profile `risk:` row with that id is rejected.
- **BREAKING: `gates.plan` and `gates.merge` take only `owner`.** The template
  no longer documents `auto`, which nothing honoured; merges open on their own
  only through `gates.auto_classes`. `/graph-doctor` warns on any other value,
  on `agent-control` in `auto_classes` and on a redefined `agent-control` row.
- Research, spike and product deliverables go to
  `<docsPath>/research/<date>-<slug>.md` (with `-concept.md` and
  `spike-<slug>.md`), a durable repo path; `.graph/` keeps only briefs, leaf
  reports and claims, and the report gate names the files for the owner to
  commit.
- `graph-control host-check`'s free-disk floor is the profile's
  `host.min_free_gb` (template 20; `/graph-init` proposes 5 for a
  `runtime.none` library or CLI), `--min-free-gb` overrides it for one call,
  and the BLOCKED fix names the key.

### Fixed

- **One risk table shape.** `risk:` is a list of `{id, paths, keywords}` rows,
  as the template writes it. `graph-control doctor` used to accept a mapping
  keyed by id (and bare ids) that `depth` then rejected with `expected an
  array`; now both read it through `risk.parse_rows`, doctor reports any other
  shape as `risk-shape`, and depth is BLOCKED with the same message.
- **Risk keywords stay case-sensitive, gain a `re:` form and skip prose.**
  Case-insensitive matching caught Tailwind `truncate`, prose "Stripe" and UI
  copy "Delete from favorites", so keywords match as spelled (SQL convention is
  uppercase), and contract C7 now says so. A keyword starting with `re:` is a
  Python regex, compiled once per run; an invalid one is doctor's
  `risk-keyword` and BLOCKS depth with the same message. Keywords never read
  added lines of prose files (the `lint` file types), so README and CHANGELOG
  mentions raise no owner class. The template's `destructive` row covers
  `DROP TABLE|DATABASE|SCHEMA|COLUMN|VIEW|INDEX` and `DELETE FROM`, a
  word-bounded `TRUNCATE` followed by a table (so `SHOULD_TRUNCATE` and
  `TRUNCATE = "x"` do not match), and lowercase-only regexes for `drop`,
  `truncate` and `delete from` statements that open a line or follow a quote,
  paren or `;`, plus `alter table ... drop column`; UI copy such as "Drag and
  drop column headers" and "Delete from favorites" does not match.
- **`re:` keywords cannot hang depth.** They run per added line and skip lines
  over 4,096 characters (`regex_skipped_long_lines` in the depth output); one
  classify has a 5 s budget, enforced between lines and by SIGALRM inside a
  runaway search on the POSIX main thread, and an overrun is BLOCKED naming the
  row. doctor warns `risk-nested` on nested quantifiers such as `(a+)+`.
- `graph-control --help` and `-h` no longer crash: a bare `%` in the
  `validate-briefs` help was read by argparse as a format spec. Tests render the
  top-level help, every subcommand's help and the entry point's `--help`.
- The Stop and lint hooks run a monorepo package's own
  `.claude/graph-checks.json` when `CLAUDE_PROJECT_DIR` is that package (Claude
  Code sets it to the launch directory). The nearest config to the cwd, then
  the project dir (Stop) or to the edited file (lint) wins, never one above the
  bound root, and runs from its own directory; a package directory maps into
  the linked worktree Claude works in. Before, the bash pre-filter found the
  package's file and the Python side read only the git toplevel's, so both
  gates were silently off while doctor reported the file as fine. The memo keys
  a package config by its path too, and `check --reuse` accepts the package
  directory.

## [0.14.0] - 2026-09-29

### Added

- Local run controls for contract dependencies, named acceptance cases, real
  witness declarations, capability preflight and source/runtime-bound receipts.
- Explicit `.claude/graph-checks.json` argv gates, candidate worktree binding,
  supported Python selection and visible setup failures.
- Session usage aggregation without exporting conversation content, and a
  provider-verified coordinator TTL trial protocol.
- Plugin CI covering hook, control, usage and Compose-isolation regressions.

### Changed

- Load role catalogs only for missing routing, deduplicate preloaded skills and
  keep coordinator handoffs compact. Route UX/product research by applicability.
- Preserve full independent review/QA; bind final evidence to actual candidate
  and runtime identity, cap repeated failed hypotheses, and reject empty/skipped
  required checks. Support bounded acceptance harnesses with owned cleanup.
- Strengthen API response/media schemas, pinned consumer contracts and stable
  test-case IDs. Host model mappings take precedence over plugin role tiers.

## [0.13.1] - 2026-09-23

### Added

- **The designer picks how to show the design.** `ux-journey`
  `references/render-media.md` lists six media - live-app injection
  (Playwright into the running app), Storybook, a standalone HTML mock, a
  Claude artifact, Claude Design, a generated sketch - with what each shows,
  when it fits and when it does not. The designer first checks which are
  available here, lists that in the spec, and picks the best-suited
  available one per decision. A committed PNG of each changed screen stays
  the floor: it is what the plan gate embeds and qa compares against;
  interactive media are linked in addition.

### Changed

- `ux-designer` keeps a least-privilege `tools:` allowlist and gains
  `Artifact` by name. It reads untrusted text (web research, app data), so it
  never inherits the owner's signed-in connectors. Claude Design tools cannot
  be granted by server name and their names are not fixed, so the designer
  writes `design/claude-design-brief.md` and the engine - which holds the
  connector - runs it at the plan gate when one is connected.
- Storybook is implementer work: the designer drafts stories in
  `design/stories/`, the UI task moves them next to their component, and the
  states are shown meanwhile as live-app captures or HTML.
- `design/` has one folder per role (`as-is/`, `to-be/`, `stories/`,
  `artifact/`, `explore/`) and the planner commits only the spec, `as-is/`
  and `to-be/` under `docsPath`.

## [0.13.0] - 2026-09-23

Agents building frontend features put new elements wherever the diff was
easiest: the `research-ux` node read how other products solve the moment, but
nothing looked at this app's screens, decided placement, or held the build to
a decision. The spec's design branch was never built; this builds it.

### Added

- **`design` node in the feature playbook** (`agent: ux-designer`, after
  `research-ux` and `research-competitor`, before `plan`). It captures the
  screens the goal touches from the running app, inventories their regions,
  actions and reusable components, checks earlier experience specs for the
  consistency baseline, decides placement per element (screen, region,
  hierarchy, what it displaces, the existing pattern it matches, rejected
  alternatives), renders the decision into the as-is capture, and writes a
  persistent experience spec with a state table and **UI acceptance rows**.
- **`when: <flag>`** node field in the engine, read from `goal.md`
  (`ui: yes|no - <reason>`, written by the planner, `yes` when unsure). A
  missing flag runs the node.
- **Sized, not all-or-nothing:** `ux-journey`'s scale rule is the design
  node's definition of done - a copy change is one acceptance row with no
  stand-up; a new element on an existing screen is capture, placement, one
  render and rows; a new flow gets everything.
- **The spec persists with its images:** the design node writes one folder
  (`.graph/<run>/design/`: `experience.md` + `as-is/` + `to-be/`, relative
  links); the plan's first UI task commits it to `<docsPath>/ux/<date>-<feature>/`,
  so it reaches the PR and the next feature's consistency check.

### Changed

- **Engine dispatches a ready set**: every node whose predecessors are all
  `done` or `skipped` goes out together, so tech and impact research never
  wait on `design`. A `design` `BLOCKED` (a configured runtime that would not
  come up) stops the run and `--resume` re-runs `blocked` nodes; a plan-gate
  rejection of `ui: no` re-queues `design` in the same run.
- **The plan gate is the design gate.** `plan.md` embeds an `## Experience`
  section (placement, alternatives, renders inline, state table) and the gate
  exhibit shows the `ui:` line and the images. UI tasks carry the spec's
  acceptance rows; a UI task that does not say where its elements go is a
  planning error.
- **Held downstream:** implementers build the spec's placement and states
  (deviation = `DONE_WITH_CONCERNS` with a reason); the reviewer opens the spec
  first and a placement or missing-state deviation without a reason is
  Important; the `definition-of-done` UI row's Contract cell is the spec's
  rows; qa verifies them on the running app, empty and error states included.
- `ux-journey` rewritten around grounding in the real UI and the placement
  decision; `ux-designer` moves to opus and preloads `ux-evidence` for capture.

## [0.12.1] - 2026-09-23

Hardening from the final review of 0.12.0. Nothing here changes a playbook's
shape; each fix closes a way a check could pass without checking.

### Fixed

- **Run ids no longer depend on an exported variable.** Every Bash call is a
  fresh shell, so `export GRAPH_RUN_ID` in one call left the next call's
  `docker compose -p ge-` pointing at project `ge-`, which never got torn down
  and whose `down -v` could hit anything else named that. The engine now names
  the id in the dispatch text - `<run-id>` for qa nodes, `<run-id>-t<N>` per
  implementer task so parallel tasks never share a database - agents prefix
  it on every call, and the template's commands use `${GRAPH_RUN_ID:?}` so a
  missing id fails loudly. `down` is its own final call, not a trap.
- **Compose isolation check is a tested script**
  (`qa-verification/compose_isolation.sh`). It also catches host networking,
  `network_mode`/`volumes_from` on another container, host-backed volumes,
  bind mounts from outside the worktree and leaks behind a compose profile,
  and exits 2 (`BLOCKED`) when the config cannot be rendered instead of
  printing nothing.
- **Template `down` uses the same `-f` files as `up`**, so the renamed
  volumes are removed and `-v` never targets the original names.
- **`vet_smoke.py` is an allowlist now**: a smoke request is refused when it,
  or a `folder.bru` / `collection.bru` above it, has any non-empty `script:*`
  or `tests` block (Bruno scripts run arbitrary JavaScript with axios and
  fetch, so no list of forbidden calls is complete), a `vars` block that
  mentions `testTenant`, a second method block or `url` key, or a stray
  carriage return. Blocks end only at a column-0 `}`, as in Bruno's grammar. A missing collection or zero smoke requests
  exits 2 (`BLOCKED`) instead of a silent pass.
- **Post-deploy baseline ends when the rollout started** (`deploy.startedAt`,
  the earliest Argo `status.history[].deployStartedAt` for the merge SHA; fallback the
  merge commit's time), not when `wait` returned - which let a regression
  into its own baseline on resumed runs and rolling updates.
- **Fix loop re-runs every check that produced a qa finding** (Schemathesis
  drift re-runs Schemathesis), qa always writes `qa-findings.json` (`[]` when
  clean), and `--auto-merge` treats an absent file as not-checked.
- **Infra playbook reads one `<app>.diff` per Application**, matching
  `infra-verification`.
- `/graph-init` proposes a `deploy` block or lists it as a gap; post-deploy
  passes one `--env-var` per `deploy.env` name and writes `vetted.txt` to an
  absolute, created path; README catalog lists every process skill.

### Added

- `scripts/check-skill-scripts.sh` and the tests it runs:
  `post-deploy-verification/tests/test_vet_smoke.py` (27 tests; 22 checks, subtests included,
  fail on 0.12.0), cross-checked against Bruno's own parser
  (`@usebruno/lang` 0.39.0: no case vetted RUN that Bruno reads as scripted,
  tenant-rebound or re-targeted) and `qa-verification/tests/test_compose_isolation.sh` (11).

## [0.12.0] - 2026-09-23

### Added

- **`post-deploy` and `retro` nodes at the end of every playbook** (feature,
  bug, infra), after the merge gate.
- **`skills/process/post-deploy-verification`** — wait for the merged commit
  to serve (`deploy.wait`, e.g. `argocd app wait --sync --health`), run the
  `smoke`-tagged Bruno requests and PromQL checks shaped like an Argo Rollouts
  AnalysisTemplate (`interval`, `count`, `successCondition`) against the
  deployed environment, and report PASS / FAIL / BLOCKED / SKIPPED. The
  environment is shared, so everything is read-only: `vet_smoke.py` refuses
  any smoke write not scoped to `{{testTenant}}` in its URL path (or with no
  test tenant configured) before anything runs, and metrics compare against a
  baseline taken when the deploy lands, after an `initialDelay`; a FAIL produces a
  filled-in rollback recommendation for the owner and never an automatic
  rollback, and it is never a fix-loop input.
- **`skills/process/retro`** — a blameless leak table from the run (each
  finding or FAILED row, the node that caught it and the earliest node that
  should have), grouped by class, with one proposed rule change per class as
  an exact diff against a named file. Proposes only; the engine lists the diffs
  in its final report and applies none. Grounded in the Google SRE book's
  postmortem culture chapter.
- **Profile `deploy` block** (`wait`, `bruEnv`, `env`, `testTenant`,
  `checks`, `rollback`), empty by default; an empty `wait` makes post-deploy
  `SKIPPED`.
- **`api-contract`: the `smoke` tag is for requests safe in a shared
  environment** - GETs, or writes into `deploy.testTenant` only.
- **`docs/img/playbook.png` regenerated** for the full feature flow: four
  research nodes, plan gate, build, review ∥ qa, fix, merge gate, deploy
  check, retro.
- **Engine step 9**: post-deploy waits for the owner's merge (`waiting:
  merge`, resumed with `--resume`); step 10 reports the post-deploy verdict and
  the retro diffs.

## [0.11.0] - 2026-09-23

### Added

- **`graphs/bug.md`** — report -> reproduce -> diagnose -> sibling-search ->
  plan gate -> implement -> review ∥ qa -> fix -> merge gate. It keeps the spec's
  §5.2 agents and its `compose: superpowers:systematic-debugging`, and adds a
  reproduction that is a failing automated test written by qa before any code
  moves, a sibling search for the same bug shape elsewhere (Semgrep rule with
  `pattern-not-inside` for the guard; spiked on semgrep 1.174.0: found the
  seeded bug and its one unguarded sibling, skipped the guarded site), and qa
  re-running the reproduction on the live stack.
- **`graphs/infra.md`** — goal -> research tech ∥ impact -> plan gate ->
  implement -> review ∥ verify -> fix -> merge gate, for deployment config.
- **`skills/process/infra-verification`** — render as Argo does (release name,
  `--namespace`, `--include-crds`, its value files; one file per Application),
  validate, policy, rendered diff against base, apply to a throwaway cluster
  (prereq operators, namespaces, CRDs Established, then the rest), smoke,
  rollback render, teardown. The run owns its kubeconfig
  (`.graph/<run>/kubeconfig`), so the developer's current-context is never
  touched and no cluster the run did not create is ever used. With no cluster
  configured it reports `PASS (static-only)`, which the merge gate shows and
  `--auto-merge` refuses. Spiked: kubeconform v0.8.0
  errors on every CRD without a schema and `-ignore-missing-schemas` silently
  skips them, so the recipe adds the datree CRDs-catalog schema location, which
  failed an Argo `Application` missing `destination`/`project` and passed a
  complete one. helm v4.2.4 lint/template and a planted `containerPort` type
  error (caught, exit 1) also spiked. conftest and kube-linter are named but
  were not run.
- **Profile `infra` block** (`cluster.create/delete/context`, `prereqs`,
  `render`, `policy` with `${RENDERED}`), empty by default; `/graph-init` proposes it and lists the existing
  contexts qa will never touch.
- **Engine: triage, `skills:`/`compose:`, worktree.** With no `--graph`, the
  engine classifies the goal as bug, infra or feature and records the pick and
  its reason as the ledger's first line - no question asked; every playbook
  gates at `plan` before product code moves, and the pick heads that gate's
  exhibit. `--resume` never re-triages: it uses the run's playbook copy. Nodes
  receive their `out:` contract, and the implementer has a diagnose role that
  investigates without fixing. A node's `skills:` and `compose:` join its REQUIRED list.
  The run's worktree is created before the first node that writes (qa's
  reproduction test included). The fix loop re-runs every node that feeds
  `fix`, so infra's `verify` is re-run like feature's `qa`.

## [0.10.0] - 2026-09-23

### Added

- **`skills/process/definition-of-done`** — a change-type matrix (API endpoint,
  DB schema, infra/k8s/Helm/Argo, background job, UI, config/flag, dependency
  bump, AI agent/prompt) × the artifacts a PR carries beyond the code (tests,
  contract, data change, rendered diff, observability, docs, rollout/rollback).
  A house synthesis of Google eng-practices, the SRE launch checklist, DORA
  capabilities and Fowler's ParallelChange; it composes `api-contract`,
  `ux-evidence` and `superpowers:verification-before-completion` rather than
  restating them. The planner preloads it and stamps each task's cells into its
  acceptance criteria, implementers ship them, and the reviewer uses it as an
  always-on lens (missing without a reason = Important). Planner, reviewer and
  both implementers preload `definition-of-done` (and the planner and
  implementers `impact-map`) in frontmatter rather than through the profile's
  `always` lists, so profiles written before 0.10.0 get them with no edit.
- **`skills/process/impact-map`** and the researcher's fifth mode, `impact`:
  entry points, callers two hops out, API/event/DB/config contracts, infra,
  tests and gaps, every row with file:line, plus a shared triage for adjacent
  issues - must-fix (a plan task), fix-in-PR (a `small` task under a scout
  budget of 3 or 20% of the plan), follow-up (listed in the PR, not fixed).
  Only the planner spends the budget, at plan time, so the owner sees every
  scout fix at the plan gate; implementers never fix unplanned adjacent code -
  a must-fix is `NEEDS_CONTEXT`, anything else is appended to
  `.graph/<run>/followups.md`, which the merge node carries into the PR body.
  The reviewer flags unplanned adjacent edits as scope creep.
- **`research-impact` joins the feature playbook's research MAP**, in parallel
  with ux, tech and competitor. The plan node now stamps definition-of-done
  rows and turns the map into tasks and a `## Follow-ups` list the merge node
  carries into the PR body.

Prior art: `graphify` was weighed as the recon engine and rejected - a whole-
corpus LLM-extraction graph with no contract-typed edges, the wrong latency for
a per-run map. The `caveman` plugin's `migration` and `verify-and-stop` skills
were read but not composed, because that plugin is not a dependency of this
one; their ideas are cited to primary sources instead (ParallelChange). The
Claude Code `LSP` tool is not in the researcher's tool list, so the map is
built with `rg`. Every cited URL returned 200 on 2026-09-23.

## [0.9.0] - 2026-09-23

### Added

- **Four Python and messaging competencies**, written from what plan 6 measured
  on a live cluster rather than from vendor-docs digests. Each skill's header
  lists its sources, pinned to the version it was written against: a versioned
  docs path such as `docs.sqlalchemy.org/en/20/` or `loguru.readthedocs.io/en/0.7.3/`,
  the source at the release tag, or, for docs.nats.io, which has no versions,
  the `nats.docs` commit. Measured claims cite the ADR section by its
  location, `Equival-io/forge-platform` `docs/adr/`, a private repo, and the
  header says so. Every Verify recipe was run against forge-libs `552a9b9`,
  and each check shown to fail on a real violation. Sourcing pass:
  `docs/research/2026-09-23-python-skills-sourcing.md`.
  - `skills/python/ruff` — rule selection that survives a codebase, banning
    **symbols rather than modules** (a module ban also flags
    `from dataclasses import replace`, so it gets silenced on day one), the
    `extend-exclude` + `force-exclude: false` pair that lets a repo keep a
    deliberate red control, and per-file invocation for the edit hook.
  - `skills/python/sqlalchemy` — async session discipline, the
    `create_savepoint` test recipe with the async caveat the docs omit,
    psycopg3 on libpq keyword DSNs with both refusal texts verbatim, Alembic
    `lock_timeout`, **never `AND id > :last_seen` in a poll**, and
    `SQLAlchemyInstrumentor` on `engine.sync_engine`.
  - `skills/python/loguru` — the one-direction `InterceptHandler`, the frame
    walk a Sentry patch silently breaks, `log_config=None` (without it uvicorn's
    own `dictConfig` removes the interception and every server line arrives
    unparsed), INFO rather than DEBUG, and the `caplog` gap.
  - `skills/messaging/nats` — a new `messaging` group. `Nats-Msg-Id` and
    `duplicate_window`, **`stream=` mandatory on every nats-py subscribe**,
    per-stream `$JS.ACK`, `_INBOX.>` in every allow-list, order-independent
    handlers, and why a denied JetStream call is indistinguishable from a
    timeout.
- **Routing rows** for all four: `ruff` joins `**/*.py`; `sqlalchemy` on
  `**/{models,db,migrations}/**/*.py` and `**/alembic/**`; `nats` on
  `**/{bus,events,messaging}/**`, `**/nats*/**` and `**/nats*.{yaml,yml}` (the
  server config and the Stream/Consumer CRs); `loguru` on `**/logging*.py`.
- **Resolver fixtures** under `hooks/tests/fixtures`: `workspace/`, a uv
  workspace whose root owns the three script names, with one member that
  declares none and one whose `pyproject.toml` does not parse; and `mixed/`,
  a Python root that declares `lint`, with a `web/package.json` that declares
  only `build` and `test`.

- **`skills/process/api-contract`** — a house rule beside `ux-evidence`: every
  change to an API surface ships its Bruno requests in the same PR (happy path
  asserting values, auth, validation, edge, non-leak), qa runs them and then the
  whole collection, and the reviewer treats a missing suite as Blocking. Bruno
  documents no convention for where a collection lives in a repo, so the house
  one is the profile's `api.collection` (default `bruno/`). Routed by the new
  server-side API-surface rows described below. Sourcing: prior-art run 2026-09-23 (docs.usebruno.com,
  docs.docker.com compose `up`, devcontainers spec).
- **Profile `runtime` block** (`up`, `seed`, `port`, `health` {`url` |
  `command`, `expect`, `timeout`}, `baseUrl`, `down`, `env`, `none`) so qa
  stands any repo up itself. `none: "<reason>"` is for a repo with nothing to
  stand up (a library, a CLI, a plugin): qa verifies through its public surface
  instead, so a mandatory qa node does not trap those repos at `BLOCKED`.
  `up` mirrors `docker compose up --wait --wait-timeout`; `health.url` is polled
  with `curl --retry-connrefused --retry-all-errors`; `seed` has no analog in
  compose or devcontainer, so it is ours. devcontainer's lifecycle shape was
  rejected wholesale: it assumes every repo runs in a devcontainer and has no
  seed or health concept. Spiked 2026-09-23: curl 8.7.1 retries a refused
  connection and exits 7; Compose v2.40.3 has `--wait` and `--wait-timeout`.
  `/graph-init` now proposes the block and the API rows from what the repo holds.
- **`skills/qa/schemathesis`** — property-based and stateful API tests
  generated from the served OpenAPI/GraphQL schema, the second layer of
  `api-contract` beside Bruno. Only `not_a_server_error` and
  `response_schema_conformance` gate; the rest of the default set runs
  report-only as spec drift (Important), because an out-of-the-box FastAPI app
  fails it on day one and a gate that is always red gets turned off. Spiked
  2026-09-23 with schemathesis 4.28.0 on a FastAPI app with a planted
  `100 // qty` bug: gate checks found it unaided (exit 1, reproduction curl
  printed), exited 0 once fixed (716/716), while the full set still reported
  drift (exit 1). Hurl was weighed as a Bruno replacement and rejected (no GUI,
  no native JSON Schema assertion, and the tested `bruno` skill already exists);
  Postman was rejected for cloud-workspace collections that cannot ship in a PR.
- **`api-contract` requires a served schema.** Every HTTP API serves OpenAPI
  (GraphQL: SDL), current in the same PR, with error statuses documented;
  profile `api.schema` names where.
- **API-surface rows are server-side only.** `routes/` and `handlers/` route
  `api-contract` only for server languages (py, go, java, kt, rb);
  `routers/`, `controllers/`, `endpoints/` for those plus ts/js (no PHP or
  .NET rows: not in the house stack); NestJS
  `*.controller.ts`, Next.js `app/api/**/route.ts` and `pages/api/**`, and the
  spec files. A bare `**/routes/**` matched TanStack Router, Remix and
  SvelteKit `src/routes/`, Angular `app.routes.ts` and MSW `mocks/handlers/`,
  which would have made a route-component task demand a Bruno suite and a
  schema the SPA cannot serve. Checked with wcmatch on 25 paths, 12 of them
  frontend or unrelated negatives. `/graph-init` adds a row for TS server routes
  it finds by content.
- **qa gets its own compose project.** `runtime.up`/`down` use
  `docker compose -p ge-${GRAPH_RUN_ID}`, and the engine exports
  `GRAPH_RUN_ID` to qa. Spiked: `-p` overrides a top-level `name:` and
  namespaces project-scoped volumes (`ge-<id>_pgdata`), but it does NOT rename
  a volume or network with its own `name:`, a `container_name:`, or anything
  `external: true` - the review reproduced qa's app resolving `db` to the
  developer's database over a shared named network. So a repo using them
  commits a block-style `compose.qa.yaml` that renames each with
  `${GRAPH_RUN_ID}` and drops the externals (`!override`, `!reset null`),
  `/graph-init` proposes it, and qa runs a `compose config | jq` isolation
  check and refuses to start while it prints anything. Spiked: five leaks
  printed on the base file, none with the override, none on a plain file; the
  first draft's flow-style `{name: ge-${GRAPH_RUN_ID}_x}` example was itself a
  YAML parse error and is gone.
- **`.graph/<run>/qa-findings.json`.** Schemathesis drift, and anything else qa
  finds beside the criteria, is written there in the review-protocol format and
  read by the fix node beside `findings.json`; `--auto-merge` checks both.
- **The runtime template ships empty.** `/graph-init` fills what it detects;
  an empty required field is qa `BLOCKED` naming it. The health poll adds
  `--max-time 5 --retry-max-time <timeout>` (spiked: a listener that accepts
  and never answers now stops the poll at the budget instead of hanging), and
  `expect` is a raw substring, so the docs warn off JSON-spaced tokens.
- **qa's Bruno command passes tokens and hides headers.** One `--env-var` per
  name in `runtime.env` (an unbound `{{TOKEN}}` is sent literally),
  `--reporter-skip-all-headers`, and an absolute report path.
- **`runtime.port` and `runtime.health.expect`.** qa checks the port is free
  before `up` and the health body contains `expect`. The spike hit it: an
  unrelated process already on the port answered the health poll with 401 until
  the real server bound, and a status-only check would have gone green against
  the wrong service.
- **A `qa` node in the feature playbook**, parallel with review (both share
  `next: fix`). Its `FAILED` rows feed the fix loop beside review findings and
  are re-run each round; `BLOCKED` is a setup stop, not a fix-loop input, and
  the merge gate does not open on a run whose qa leg never ran. `--auto-merge`
  now also requires qa `PASS`.

### Changed

- **`hooks/scripts/resolve_touched_project.py` walks past a project file that
  declares neither `lint` nor `typecheck`, to the nearest ancestor of the SAME
  kind that declares one.** A directory holding a project file of another kind,
  or the project bound, ends the search, and the answer is the nearest project
  file, the same answer as before. Previously the walk always stopped at the
  nearest project file. In a uv workspace that is the member's scriptless
  `pyproject.toml`, so every edit under `packages/*/src/` resolved to a project
  with no scripts, and the PostToolUse hook exited 0 **in silence**: the whole
  library went unlinted. The same-kind limit keeps a scriptless
  `web/package.json` under a Python root from resolving to the root and
  running `uv run lint` on a `.tsx` file. A project file that cannot be read or parsed still stops the walk
  where it is, rather than letting an ancestor's scripts run against a file that
  ancestor does not own. `hooks/README.md` and `lint-touched-file.sh`'s header
  both stated the old rule and were corrected with it.
- **`skills/python/pydantic-house-rules`** — the `Verify` block now carries an
  executable recipe. The old check walked `src/` for a `@dataclass` whose
  preceding line held the exemption comment, which approximated a rule nothing
  enforced; it is replaced by the ruff `banned-api` ban, a fixture proving the
  rule fires (exit 1, `TID251`), and an explicit statement of the four spellings
  that reach a real dataclass past it. The framework-adapter section gains the
  `# noqa: TID251  # framework adapter exception: <call>` spelling, and
  `ruff --select PGH004` rejects a bare `# noqa`. Check 6 (every Temporal
  client passes the converter) now matches any call whose target **ends with**
  `Client.connect`, rather than only the exact text `Client.connect`. The exact
  match missed `temporalio.client.Client.connect(...)` and an aliased
  `client.Client.connect(...)`, so a bare client written that way passed.
- **`.claude-plugin/plugin.json`** lists `./skills/messaging` so the new group
  loads. `version` is deliberately unchanged.

### Removed

- **Content and social media leave the plugin; it is engineering only.** The
  `content-writer` and `media-producer` agents, the `content` skill group
  (`short-form-posts`, `short-attention-media`), the profile template's
  `content:` block and `publication` gate, and the `launch` / `content`
  playbooks from the plan. The roster is seven agents. `ux-evidence` keeps the
  two recording rules it borrowed from `short-attention-media` (cut every wait,
  ≤ 30s per flow) inline. Dated specs and plans under `docs/` still describe the
  old roster and are left as the record of what was decided then.
