# Deterministic run controls

Use `uv run scripts/graph-control.py …` from the plugin checkout. The PEP 723 entry point requires Python ≥3.11 and pins PyYAML 6.0.2. The controls inspect files, executable availability and Git state. They **never execute configured project commands, start a runtime, call a model or make network requests**, with one exception: `host-check` runs `docker info` (5 s timeout) when the profile's runtime names docker or compose, and that call reaches whatever daemon `DOCKER_HOST` points at, a remote one included. `uv` may install its pinned runtime/dependency when first invoked; provision it before offline use.

Successful commands return JSON `{"status":"PASS",…}` and exit 0. Invalid, missing, stale or incomplete evidence returns `{"status":"BLOCKED","reason":"…"}` and exit 1. Parser errors use argparse's exit 2. There is no N/A/skip route for required checks. Every check declared in the run is required; keep optional diagnostics outside this gate manifest.

```
uv run scripts/graph-control.py validate-plan /absolute/run/plan.json
uv run scripts/graph-control.py snapshot /absolute/candidate --repo backend
uv run scripts/graph-control.py fingerprint /absolute/run/run.json
uv run scripts/graph-control.py preflight /absolute/run/run.json --profile /absolute/profile.yaml --graph /absolute/run/graph.md
uv run scripts/graph-control.py record-receipt /absolute/run/run.json /absolute/run/receipt.json --store /absolute/run/receipts.json
uv run scripts/graph-control.py verify /absolute/run/run.json --store /absolute/run/receipts.json
uv run scripts/graph-control.py validate-attempts /absolute/run/attempts.json
uv run scripts/graph-control.py event /absolute/run/event.json --state /absolute/run/events.json
uv run scripts/graph-control.py guard-agent --profile /absolute/repo/.claude/graph-profile.yaml --root /absolute/repo < hook-input.json
uv run scripts/graph-control.py check /absolute/candidate --reuse
uv run scripts/graph-control.py doctor --root /absolute/repo [--quick]
uv run scripts/graph-control.py status [--line] [--root /absolute/repo] [--session <session id>]
uv run scripts/graph-control.py depth --root /absolute/candidate --base <rev> --profile /absolute/repo/.claude/graph-profile.yaml [--plan /absolute/run/plan.json]
uv run scripts/graph-control.py findings /absolute/run/review-1.md [/absolute/run/review-2.md ...] [--counts]
uv run scripts/graph-control.py waves /absolute/run/plan.json [--max-width 4]
uv run scripts/graph-control.py validate-briefs /absolute/run
uv run scripts/graph-control.py digest --root /absolute/candidate --base <rev> [--plan /absolute/run/plan.json] [--profile /absolute/repo/.claude/graph-profile.yaml]
uv run scripts/graph-control.py render [--root /absolute/plugin] [--write|--check]
uv run scripts/graph-control.py host-check --root /absolute/repo [--min-free-gb <n>] [--profile /absolute/repo/.claude/graph-profile.yaml]
uv run scripts/graph-control.py skills-check --required graph-engineering:bruno,superpowers:test-driven-development --loaded "<the child's skills_loaded: value>"
```

`preflight --readiness-only` is for the stage before implementation/runtime startup: it checks configuration, plan, tools, models and baseline source, but does not require the runtime observation file yet. Its `phase: readiness` result cannot authorize completion. Use a planned runtime artifact path and placeholder fingerprint until the runner reports actual identity, then refresh the candidate manifest. Recording and verification never accept readiness-only mode.

`fingerprint` hashes canonical JSON (sorted keys, compact separators). File hash fields instead use SHA-256 of the exact file bytes. `snapshot` prints `source` suitable for a candidate. Put mutable run artifacts outside candidate source roots, or in a deliberately ignored run directory; otherwise adding a receipt correctly changes the dirty source fingerprint. Record source identity **after** implementation and before checks. After changing source, update the manifest and rerun affected checks; do not relabel old receipts. `record-receipt` and `verify` rerun read-only preflight from the manifest's bound profile/playbook paths. A changed plan, profile or graph invalidates the candidate contract.

## Plan schema (versions 1 and 2)

`schema_version` is 1 or 2; any other value is rejected. Version 2 is version 1 plus the optional success signals below. All fields in this example are required in both versions. Unknown/duplicate keys and duplicate IDs are rejected. Arrays below may be empty unless the example/comment says otherwise.

```json
{
  "schema_version": 1,
  "external_contracts": [{"id": "RunDetail", "fields": ["fan_out_planned"]}],
  "cases": [{
    "id": "AC-FANOUT", "given": "two known downstream candidates",
    "when": "the first starts", "then": "header shows Product 1 of 2",
    "oracle": "visible total equals the supplied candidate count", "runner": "playwright",
    "requires_real": false,
    "witness": {"kind": "synthetic", "reference": "tests/fixtures/fanout.json", "claim": "two candidates"},
    "transitions": ["not_started", "running"]
  }],
  "tasks": [{
    "id": "FE3", "depends_on": [], "produces": [{"id": "stage-renderer", "fields": ["deriveStageStatus"]}],
    "consumes": [{"id": "RunDetail", "fields": ["fan_out_planned"]}],
    "writable_paths": ["frontend/src/stages/**"], "case_ids": ["AC-FANOUT"], "stateful": true
  }, {
    "id": "FE4", "depends_on": ["FE3"], "produces": [],
    "consumes": [{"id": "stage-renderer", "fields": ["deriveStageStatus"]}],
    "writable_paths": ["frontend/src/downstream/**"], "case_ids": ["AC-FANOUT"], "stateful": true
  }]
}
```

Every case has an owning task. Every task has at least one case and writable path. Stateful tasks need a case with at least two named transition events/states. Real-world claims set `requires_real: true`; synthetic witnesses cannot satisfy them. Witness kinds are exactly `real` or `synthetic`. A reviewer must verify the witness's **truth and relevance**: the parser cannot discover that a supposedly real Solr fixture was invented, or that a range belongs to another product.

Contract producers are unique. A consumed contract's producer must be an ancestor dependency; all consumed fields must exist. External contracts must already exist and have evidence in the case/research artifacts. Dependencies reject cycles/unknown tasks. Unordered tasks cannot claim overlapping writable paths. Glob overlap uses a conservative static-prefix check: ambiguous ownership must be narrowed or serialized. Paths are repo-qualified relative paths, without `..`.

### Success signals (version 2)

A version 2 plan may add two optional top-level keys (shown alone below; the rest of the plan is as above); a version 1 plan carrying either is rejected, so adding signals means bumping `schema_version` to 2. Every other file this tool reads (run.json, receipt stores, event state, attempts) still requires `schema_version` 1.

```json
{
  "schema_version": 2,
  "success_signals": [{
    "goal": "checkout errors stay rare", "source": "prometheus",
    "command": ["scripts/signals/checkout-error-ratio"],
    "success_condition": "value <= 0.01", "window_days": 7
  }]
}
```

- `goal`: nonempty text, the outcome in the user's terms, unique within the plan: `measure.md`, `baseline.json` and the due count key each signal by its goal, compared as a table cell shows it (whitespace collapsed, `|` as `/`).
- `source`: exactly `prometheus`, `sentry`, `sql-readonly` or `command`.
- `command`: a nonempty argv array of nonempty strings (repeated flags are fine). It must print one aggregate, a bare number or `{"value": n}`; `scripts/measure_signals.py` rejects anything else, raw tool output included (`promtool query instant` prints `{} => 0.003 @[...]`), so the command is usually the repo's own adapter around the query. Row-level queries are a planner and reviewer rule, which this parser cannot detect.
- `success_condition`: the grammar below.
- `window_days`: an integer from 1 to 90.
- `success_signals: []` is valid only with a nonempty `success_signals_reason` (internal, refactor and infra work usually has no user-facing signal). The reason is rejected next to a nonempty list, or without the list, because it only explains an empty one. Omitting both keys is also valid.

`success_condition` is a deterministic grammar, matched against the whole string:

```
condition := "value" SP op SP rhs
op        := "<" | "<=" | ">" | ">=" | "=="
rhs       := number | "baseline" SP "*" SP number [ SP "+" SP number ]
number    := [ "-" ] digits [ "." digits ]
```

`SP` is exactly one space, `digits` are ASCII 0-9, and nothing may precede or follow. `value` is the command's result; `baseline` is the value the measuring step recorded before the change shipped. Accepted: `value <= 0.01`, `value >= baseline * 1.1 + 5`, `value < baseline * 2 + -0.5`. Rejected: `value < foo`, `x > 1`, `value != 1`, `value<=1`, `value >= 1.1 * baseline`, `value > 1e3`. graph_control validates and stores signals; it never runs a signal's command.

## Run schema (version 1)

```json
{
  "schema_version": 1, "id": "run-id", "plugin_version": "<executing plugin version>",
  "plan": "/absolute/run/plan.json", "plan_sha256": "<file SHA256>",
  "profile": "/absolute/project/.claude/graph-profile.yaml", "profile_sha256": "<file SHA256>",
  "graph": "/absolute/run/graph.md", "graph_sha256": "<file SHA256>",
  "candidate": {
    "sources": [{"repo": "backend", "root": "/absolute/candidate", "revision": "<full Git object ID>", "dirty_sha256": "<snapshot value>"}],
    "runtime": null, "fixture_sha256": "<fixture-set SHA256>", "schema_sha256": "<schema SHA256>"
  },
  "capability_nodes": {"plan": "plan", "implement": "implement", "review": "review", "qa": "qa", "verify": "qa"},
  "checks": [{"id": "unit", "capability": "implement", "kind": "test", "argv": ["uv", "run", "pytest"],
              "cwd": "/absolute/candidate", "case_ids": ["AC-FANOUT"], "max_age_seconds": 3600}],
  "actors": [{"id": "worker-session-id", "role": "implement", "requested_model": "sonnet",
              "resolved_model": "<concrete available host model>", "resolution_source": "<host capability evidence>", "skills": []}],
  "available_models": ["<concrete available host model>"], "tools": ["git", "uv"],
  "runtime_identity": null, "runtime_max_age_seconds": 120,
  "requires_api": false, "requires_design": false
}
```

This abbreviated example intentionally shows only one check/actor; a valid run needs checks covering **implement, review, QA, verify** and actors covering **plan, implement, review, QA, verify**. Use distinct session IDs for actors; each actor has one role. A reviewer and QA actor must differ from implementers and from each other. Required check kinds are fixed: implement=`test`, review=`analysis`, qa=`public`, verify=`final`. QA and final checks together must each cover every plan case. Known lint/typecheck-only commands cannot masquerade as public/final checks. Arbitrary command semantics remain the reviewer's responsibility.

Checks use argv arrays, never eval/shell interpretation by this helper. `cwd` must exactly match a canonical candidate source root (use `snapshot` output; `/var` versus `/private/var` aliases are not interchangeable in the manifest). `argv[0]` and declared tools must be discoverable executables. Skills must be existing files. `available_models` and `resolution_source` are **host-supplied observations**, not proof obtained by this tool. Include concrete model IDs from actual host capability discovery; unavailable resolution blocks. Receipt response-model metadata is compared with the resolved dispatch. Do not substitute an agent saying “I am model X” for provider metadata.

The actual saved graph is parsed: capability node existence, agent role, cycles and unknown edges are checked. The full feature graph's QA node can map both `qa` and `verify`, but these still require **separate check receipts**; final verify is not inferred from the QA label. A reduced graph missing QA is blocked. When design is required, the design node must exist; `design: owner` cannot silently become `plan: auto` without a design gate.

The profile must declare either an explicit `runtime.none` reason for a CLI/library public surface, or a live runtime. Missing setup cannot be replaced by `none` for API work. A live runtime accepts either:

- `runtime.command`: a bounded project-owned setup→checks→cleanup harness, or
- nonempty `runtime.up`, `seed`, `down`, `baseUrl`, and `health.command` or `health.url`+`expect`.

API work also requires `api.collection` and `api.schema`; the repo-relative collection must contain bruno.json inside a candidate source. The helper checks declarations, not endpoint health; the runner owns actual startup, isolation, identity observations and cleanup. Static candidates use `runtime: null` and `runtime_identity: null`. Live candidates require both values and a fresh identity artifact:

```json
{
  "worker_revision": "<one candidate source revision>",
  "sources_sha256": "<canonical fingerprint of the full candidate.sources array>",
  "run_id": "<run.id>", "instance_id": "<unique runtime instance ID>",
  "images_sha256": "<pinned image-set SHA256>",
  "corpus_sha256": "<pinned corpus SHA256>",
  "fingerprint": "<canonical SHA256 of preceding six identity fields>",
  "observed_at": "2026-09-29T12:00:00+00:00"
}
```

The runtime fingerprint must match `candidate.runtime`; worker revision must be among candidate sources, the full source fingerprint includes dirty trees, and run/instance identity distinguishes parallel stacks. The timestamp must not be future or older than `runtime_max_age_seconds`. A runner must regenerate this artifact from its observed worker/images/corpus, not copy the expected values. Fixture/schema hashes likewise come from observed runner inputs; use canonical JSON `[]` hash only for an honestly empty fixture/schema set. No running service is queried by this tool.

## Receipt schema

```json
{
  "check_id": "public-api", "actor": "qa-session-id", "model": "<actual provider response model>",
  "run_sha256": "<fingerprint run.json>",
  "candidate": {"sources": [], "runtime": null, "fixture_sha256": "<hash>", "schema_sha256": "<hash>"},
  "argv": ["make", "test-api-acceptance"], "cwd": "/absolute/candidate", "status": "PASS",
  "exit_code": 0, "executed": 1, "skipped": 0,
  "cases": [{"id": "AC-FANOUT", "status": "PASS"}],
  "observed_at": "2026-09-29T12:00:00+00:00",
  "log_path": "/absolute/run/evidence/api.log", "log_sha256": "<file SHA256>",
  "findings": {"blocking": 0, "important": 0}
}
```

Copy the **complete actual** candidate object; `sources: []` is only an illustration and is invalid. Case results are exactly PASS/FAIL/SKIPPED/BLOCKED. Receipt status is PASS/FAIL/BLOCKED. For analysis, `executed` counts inspected acceptance assertions, not claimed test executions; for test/public/final checks it is actual selected cases/checks executed. Preserve the original process exit status before any log-filtering pipeline. Zero executions, skipped required cases, missing cases, wrong actor/role/model, nonzero exit, important/blocking findings, changed logs, wrong candidate and expired evidence cannot prove PASS.

A store is `{"schema_version":1,"receipts":[…]}`. Recording uses a local POSIX file lock and atomic replacement. Receipt observation times must strictly increase per check; an old pass cannot overwrite a newer failure. The latest appended receipt per check wins; a later failure cannot be hidden by an older pass. Old source-state receipts remain in the store for history but do not prove the new candidate. The files are audit artifacts, **not tamper-proof signed attestations**; independent reviewers/QA must observe their own evidence.

## Attempts and events

```json
{"schema_version":1,"max_fix_rounds":3,"task_ids":["T1"],"attempts":[
  {"task_id":"T1","round":1,"decision":"fix","candidate":"<revision>","reason":"range assertion failed","hypothesis":"per-product ranges","outcome":"failed"}
]}
```

Run this validator before every fix dispatch. Rounds are consecutive per task and never reset. Outcomes are pending/passed/failed. After two failures for the same task/hypothesis, another fix on that hypothesis is rejected; a new diagnosis must name its changed hypothesis and evidence in reason. Beyond the limit the decision must be `replan` or `blocked`; either closes that task's repair series. A new approved plan is required to start another series. The tool validates an artifact; it cannot observe unrecorded dispatches or enforce host calls made outside the engine.

An event is `{"task_id":"T1","sequence":1,"kind":"progress","summary":"tests running"}`. Kinds are progress/yielded/completed/failed/decision. Per-task sequence strictly increases. State retains only the latest event per task; only completed/failed/decision returns `wake:true`. The engine/host must honor this signal; the helper does not intercept native notifications.

## Command modules

Every subcommand beyond the eight built-ins above (`guard-agent` included) is a plug-in: one module under `scripts/graph_control/commands/`, discovered at startup, so a new subcommand is a new file and `cli.py` is not edited. A module defines:

- `NAME: str`, the subcommand name. A NAME that collides with an existing subcommand, built-in or plug-in, raises at startup.
- `HELP: str`, one line for `--help`.
- `add_arguments(parser)`, which adds its argparse arguments.
- `run(args) -> dict | Output`.

`iter_commands()` imports every module in the package with `pkgutil`, in name order, and raises `TypeError` for a module missing any of the four, so a broken module fails loudly instead of vanishing. Modules whose name starts with `_` are private helpers and are skipped. Import heavy dependencies such as PyYAML inside `run`, never at module top, so discovery stays cheap for every other subcommand.

Result handling in `cli.py`: a dict prints `{"status":"PASS",...}` with sorted keys and exits 0, exactly like the built-ins. An `Output(text, exit_code=0)` (frozen dataclass) prints `text` verbatim, with no added newline, and exits `exit_code`; use it when stdout belongs to another protocol, such as hook JSON. `Invalid`, `ValueError` and `OSError` print the BLOCKED JSON and exit 1. Plug-ins keep this tool's contract: they read files and never execute project commands.

## guard-agent

The body of the PreToolUse hook for `Agent|Task`, `hooks/scripts/guard-agent.sh`. It reads the hook payload on stdin and the profile's `policy:` block, prints hook JSON or nothing, and exits 0. Every key of the block is optional; these are the plugin defaults:

```yaml
policy:
  roles:            # agent type -> model alias; entries override these defaults one type at a time
    planner: opus
    ux-designer: opus
    implementer: opus
    reviewer: opus
    reviewer-lead: opus
    implementer-simple: sonnet
    researcher: sonnet
    researcher-spike: sonnet
    qa: sonnet
    qa-lead: sonnet
    retro: sonnet
  never: [haiku, fable]           # replaces the default when present
  block_types: [general-purpose]  # replaces the default when present
```

Semantics, first match wins:

1. No profile, a profile that is not a mapping, or no `policy` mapping: no decision. A repo without the block is untouched.
2. The type is `tool_input.subagent_type` with a leading `graph-engineering:` stripped. A call with no type counts as `general-purpose`, because that is what the host runs for it. A roster type takes its `roles` tier. A name among the values of `localAgents` takes the tier of the role its key names, either a role (`qa`) or a playbook leg (`plan`, `design`, `implement`, `review`, `research`, `verify`); a value may be one name or a stack-to-name mapping. Anything else (`Explore`, `Plan`, `other-plugin:x`, a `visual` leg) has no tier.
3. A prompt line matching `^policy-override: (.+)$` skips enforcement and appends one ledger line (below). This is the escape hatch for a deliberate exception.
4. A type in `block_types`: deny with `graph-engineering policy: subagent type <t> is blocked in this repo. Dispatch a roster agent (graph-engineering:implementer, implementer-simple, reviewer, reviewer-lead, researcher, researcher-spike, qa, qa-lead, planner, ux-designer, retro), or add a line policy-override: <reason> to the prompt.`
5. A `tool_input.model` in `never`: deny with `graph-engineering policy: model <m> is not allowed here (policy.never). Omit model or use <tier>.`, or just `Omit model.` for a type with no tier.
6. A tier with `model` absent or different: allow, with `updatedInput` set to the complete original `tool_input` plus `model: <tier>`. The host replaces the whole input with `updatedInput` (spike j, CLI 2.1.285, and the hooks reference), so every other field is copied unchanged; an omitted model is an absent key.
7. Otherwise no decision.

Output shape: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny" | "allow", "permissionDecisionReason": "...", "updatedInput": {...}}}`, with `updatedInput` on a rewrite only. `agent_id` and `agent_type` are present only on calls made inside a subagent, so both are optional.

Observability: an override appends one line to `<root>/.graph/ledger.md`, creating the directory:

```
- 2026-09-30T12:00:00+00:00 policy-override: type=general-purpose model=default agent=main reason=owner approved a one-off spike
```

`agent` is the calling subagent's `agent_id`, or `main`. Control characters in a field collapse to spaces and each field is capped at 200 characters, so a payload cannot forge ledger lines; the prompt itself is never logged.

Fail-open, on purpose: a broken policy must never block every dispatch in a repo. An unreadable payload or profile (missing, invalid YAML, duplicate keys through `preflight.read_profile`) gives no decision; a ledger write failure warns on stderr and keeps the decision. The wrapper drains stdin and exits 0 with no output when `CLAUDE_PROJECT_DIR` is unset, the profile is missing, it has no top-level `policy:` line (checked with `grep`, so such repos never start uv), `uv` is not on PATH, or the helper exits nonzero. The cost is that a broken profile silently disables enforcement; `preflight` still rejects that profile when a run starts. Rollback: delete the `policy:` block, which makes the hook a no-op, or revert. Claim: subagent type and model are enforced; delegation itself is only guided.

## check --reuse and the check memo

The Stop hook (`hooks/scripts/configured_check.py test`) memoizes the verdict of the `test` block of `.claude/graph-checks.json` by tree, so a Stop on an unchanged tree never reruns the suite. `scripts/graph_control/memo.py` owns the store; it is stdlib only because the hook imports it without PyYAML.

- **Key**: SHA-256 of canonical JSON `{root, revision, dirty_sha256, argv, config_sha256}`. The first three come from `snapshot(root)` (revision plus the dirty-tree hash, which covers staged, unstaged and untracked non-ignored files); `argv` is `test.argv`; `config_sha256` hashes the exact `graph-checks.json` bytes, so any config edit (argv, timeout, precheck) is a new key. A config in a monorepo package adds `dir`, its path from the worktree root, and the tree identity stays the whole worktree's, so two packages with identical configs never share a verdict. Git-ignored files (`node_modules`, `.venv`, build output) are not in the key.
- **Store**: `<git common dir>/graph-engineering/checks-state.json`, `{"schema_version":1,"entries":{<key>:<verdict>}}`, at most 200 entries (the oldest `observed_at` is dropped). It sits outside every worktree, so writing it never changes the dirty hash it is keyed by, and linked worktrees share one file (the key includes the root). Writes take the same POSIX lock and atomic replace as the receipt store. A missing, corrupt or foreign file reads as empty, and an entry that fails validation never replays.
- **Verdict**: `{status: pass|fail|timeout, exit_code: int|null, observed_at: <UTC ISO>, tail: <= 4000 chars, argv: [...]}`; `pass` has exit 0, `fail` a nonzero exit, `timeout` a null exit.
- **Hook behavior**: the key is computed before the precheck. A hit replays without running anything, precheck included: `pass` exits 0 silently; `fail` exits 2 with the stored tail and `(replayed: tree unchanged since <observed_at>)`; `timeout` exits 0 with `tests not verified (timed out at <observed_at>; tree unchanged)`. A miss runs as before and stores pass, fail or timeout, but only when the key after the run equals the key before it: a tree that moved while the suite ran (an edit, a suite that writes non-ignored files) is not stored. A precheck failure and a missing or unstartable runner are never stored. A non-Git root or any snapshot or memo error means no memo, and the suite runs normally.
- **Stale by environment**: a failure caused by something outside the tree (dependencies installed afterwards, a service that was down) replays until the tree changes. Configure a `precheck` for environment readiness, since a precheck failure is never recorded; the replayed failure message names the memo file to delete for a one-off rerun.
- **Kill switch and rollback**: any nonempty `GRAPH_CHECKS_NO_MEMO` (for example `GRAPH_CHECKS_NO_MEMO=1` in the environment Claude Code runs hooks with) disables lookup and store in the hook and makes `check --reuse` BLOCKED, so every Stop runs the suite. Deleting `checks-state.json` clears the memo; reverting the change removes it. A replay is observable by its `replayed` or `tree unchanged` text.

`graph-control check <root> --reuse` reads `<root>/.claude/graph-checks.json`, where `<root>` is the directory holding that config (the Git worktree root, or a monorepo package with its own), computes the same key and returns `{"status":"PASS","verdict":"pass|fail|timeout","observed_at":"...","exit_code":0}`. It never executes anything. A tree with no stored verdict returns BLOCKED `no memo for the current tree`; a missing config, a config with no test block or a malformed `test.argv`, a root outside any Git worktree, and a set `GRAPH_CHECKS_NO_MEMO` are BLOCKED with the reason. `--reuse` is required: graph-control never runs project commands, so replay is the only mode. The memo is a speed cache, not merge evidence: the merge gate still proves checks with receipts (`record-receipt`, `verify`).

## doctor, status, depth, findings, waves, validate-briefs, digest, render, host-check, skills-check

Read-only plug-in commands; like every control, none executes project commands.

- `doctor --root <repo> [--quick]` inspects the repo's Graph Engineering setup and returns findings.
- `status [--line] [--root <repo>] [--session <id>]` reports run status; `--line` is the one-line form for a status line. Stdlib only, so it also runs as `python3 -m graph_control.status` with `PYTHONPATH=<plugin>/scripts`, without uv or PyYAML. The session is `--session`, else, with `--line`, the `transcript_path` or `session_id` of the JSON the host pipes to a `statusLine` command (pipe it through: `printf '%s' "$input" | ... --line`), else the newest session of the root. A named session that is not found prints nothing rather than another session's agents. The full form (no `--line`) adds DONE since the last look and NEXT, read from each run's `plan.json`, `run.json` and `receipts.json`; it never opens `ledger.md`.
- `depth --root <candidate> --base <rev> --profile <profile.yaml> [--plan <plan.json>]` picks the review depth for a diff and returns `{depth: lint|single|panel, changed_lines, files, risk_rows, reasons, untracked_excluded, regex_skipped_long_lines}`. `risk:` is a list of `{id, paths, keywords}` rows, the template's shape; any other shape (a mapping keyed by id, bare ids) is BLOCKED with the message `doctor` reports as `risk-shape`. A row matches on a path glob or on a keyword found, spelled exactly (case-sensitive), in an added line of a file that is not prose (the `lint` file types below); a keyword starting with `re:` is a Python regex instead, and an invalid one is BLOCKED with the message `doctor` reports as `risk-keyword`. A `re:` pattern must have no nested quantifiers (doctor warns `risk-nested` on shapes like `(a+)+`), runs per added line, skips lines over 4,096 characters (counted in `regex_skipped_long_lines`), and matching past 5 s is BLOCKED naming the row. A row with neither is a placeholder and matches nothing, except `outside-the-run`: with `--plan`, it matches when a changed path is in no task's `writable_paths` (repo-relative globs). One row is built in and reserved, `agent-control`: `**/.claude/**`, `**/CLAUDE.md`, `**/AGENTS.md`, `**/.mcp.json`, `.github/**` and the profile's `instructionPaths`, so a diff to the agent's own checks, hooks, permissions, gates or prompts is never class `none` and never `lint`; a profile row with that id is BLOCKED. `lint` is prose by file type only (`*.md`, `*.markdown`, `*.rst`, `*.adoc`, and README, CHANGELOG, LICENSE and similar named files, bare or `.txt`), never by directory: `docs/conf.py`, `requirements.txt` and `CMakeLists.txt` are code, and MDX is not prose.
- `findings <files...> [--counts]` reads reviewer finding files; an absent file is BLOCKED.
- `waves <plan.json> [--max-width N]` returns `{waves: [[task ids]], max_width}`: the plan's topological levels from `depends_on` (`Plan.levels()`, the same loop `validate` uses), with tasks in plan order within a level. A level wider than `N` splits into consecutive sub-waves, still in plan order, so a diamond (A; B and C depend on A; D on both) gives `[[A],[B,C],[D]]`, and five independent tasks at `--max-width 2` give `[[1,2],[3,4],[5]]`. The default 4 is the engine's sub-cap on concurrent opus agents; `N` must be a positive integer (argparse exit 2 otherwise). Tasks in one wave never claim overlapping `writable_paths`, because validation rejects overlaps between unordered tasks. The plan is fully validated first, so an invalid plan is BLOCKED with the `validate-plan` message.
- `validate-briefs <run-dir>` returns `{briefs: N}` when every task in `<run-dir>/plan.json` has a brief at `<run-dir>/tasks/<id>.md` of at most 300 lines, with at most 35% of its lines in fenced code blocks (fence lines included). Otherwise it is BLOCKED, naming every failing task in plan order with the file and the limit, for example `T2: tasks/T2.md has 8 of 20 lines fenced (limit 35%)`; a missing or blank brief, and a task id that is not a plain file name under `tasks/`, are BLOCKED the same way. Fences follow CommonMark: up to three spaces of indent, then three or more backticks or tildes; the closing fence uses the same character, is at least as long and has nothing after it; an unclosed fence runs to the end of the file. The plan is fully validated first, so an invalid plan is BLOCKED with the `validate-plan` message.
- `digest --root <candidate> --base <rev> [--plan <plan.json>] [--profile <profile.yaml>]` prints markdown, not JSON: the merge exhibit's change digest of the working tree against `<rev>`, at most 60 lines, from git alone. A small diff (at most 10 files and 300 changed lines) gets its per-file stat grouped by plan task, with `unplanned` last; a large one gets its size split by the profile's `digest.exclude` globs, files added under the `api-surface` risk row's globs, the top 5 hotspots (90-day churn times lines changed) and files added under `uxEvidence.path`. It passes `diff.autoRefreshIndex=false`, so it never rewrites the index.
- `render [--root <plugin>] [--write|--check]` draws one Mermaid `flowchart LR` per `graphs/*.md`, parsed by the same `read_graph` the engine uses: gate nodes as hexagons, `when:` labels on the edges into conditional nodes. No flag prints `docs/playbooks.md`; `--write` writes it; `--check` is BLOCKED when the file on disk differs, and `tests/graph_control/test_render.py` runs that check on every suite run.
- `host-check --root <repo> [--min-free-gb <n>] [--profile <profile.yaml>]` returns host findings before a run fans out: free disk against the floor (`--min-free-gb` for one call, else the profile's `host.min_free_gb`, else 20; a negative or non-integer profile value is BLOCKED), load average against the core count, `core.bare` of the root's Git config, how many commits the checkout is behind the upstream default branch (local refs only, never a fetch), and docker reachability, checked only when the profile's `runtime` mentions docker or compose. Only free disk below the floor is BLOCKED; every other finding is advisory and the command still returns PASS.
- `skills-check --required <names> --loaded <names>` compares the REQUIRED skills a dispatch named with the child's `skills_loaded:` line (comma-separated; the `skills_loaded:` prefix, backticks and `(annotations)` are dropped and names lowercased). A qualified `plugin:skill` is proven only by the identical name, a bare one only by the identical bare name; routing names plugin skills qualified (`doctor` warns `routing-bare`). Exit 0 is PASS `{required, missing: []}`; exit 1 prints `{"status":"SKILLS_MISSING","missing":[...]}`; exit 2 is BLOCKED on a name outside `[a-z0-9][a-z0-9_-]*(:[a-z0-9][a-z0-9_-]*)?`. It reads no file.

## Regression suite

```
uv run --python 3.12 --with PyYAML==6.0.2 python -m unittest discover -s tests/graph_control -v
```

Fixtures cover the command-module registry, guard-agent policy semantics, plan levels and wave splitting, plan schema v2 success signals and the condition grammar, brief size and fenced-share limits, the check memo (key identity, cap, corrupt store, stdlib-only import) and `check --reuse`, the audited FE3→FE4 missing edge, unavailable planned count, synthetic-as-real evidence, composed workflow transitions, missing QA graph/runtime, missing models/skills, lint-only false gates, exact source/dirty/runtime freshness, log drift, zero/skipped cases, later failures, repair limits, event coalescing, and a public CLI record→verify→wrong-candidate failure sequence. Semantic witness truth and meaningful oracle quality remain model-review/evaluation cases rather than parser claims.
