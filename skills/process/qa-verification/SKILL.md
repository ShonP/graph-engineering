---
name: qa-verification
description: Use when verifying that shipped work actually does what its acceptance criteria claim - end-to-end UI checks, API contract checks, production smoke tests. Evidence-based; a criterion without captured evidence is not verified.
---

# QA Verification

Review reads code; QA runs it. This skill verifies acceptance criteria against a **running system**, and its output is evidence, not opinion.

## Protocol

qa runs once per merge unit, on the run branch after the unit's last task
merges: the stack is stood up once and every task's criteria in that unit are
rows of one report, never once per task. With the ready queue the merge unit is
the whole run unless the plan splits it.

1. **Read the acceptance criteria** from the task/plan. Each becomes one checklist row. No criteria = `NEEDS_SETUP` (ask the planner, do not invent criteria).
2. **Stand the system up from the profile's `runtime` block.** A nonempty
   `runtime.command` selects a bounded acceptance harness: run that command
   from the candidate worktree root with `GRAPH_RUN_ID` set. What it must do
   and report (run-id and root guards, evidence under `.graph/<run>/qa/<case-id>/`,
   teardown on every exit, the report JSON) is `references/harness-contract.md`;
   `templates/qa-harness.sh` is a skeleton that implements it for a repo to
   copy. Do not start a second stack or invent up/down commands for this mode.
   Steps 3 to 5 execute inside the harness while its runtime is alive;
   afterward consume its report and captured evidence. Extra probes require
   extending and rerunning that harness, never calling a service it already
   tore down. A mocked browser harness or fake workflow activities must be
   labelled; they cannot satisfy criteria requiring a real backend/scanner.
   Otherwise follow the standalone mode below.

   **Standalone runtime.** If `runtime.none` holds a reason, skip this step: verify through the repo's own public surface instead (the CLI as a user runs it, the package imported from a clean environment, the documented commands) and say so in the report. Otherwise, in this order. **Every Bash call is a fresh shell**: an `export` does not survive to the next call (spiked), so prefix every runtime command, in every call, with `GRAPH_RUN_ID=<the run id from your dispatch>` - the profile's commands use `${GRAPH_RUN_ID:?}`, which fails loudly instead of running as project `ge-`. The names in `runtime.env` are read from the environment you were started with (never write their values anywhere). For a compose `up`, run the isolation check below and refuse to start (`BLOCKED`, naming each line it prints) until it exits 0; check `runtime.port` is free (`lsof -nP -iTCP:<port> -sTCP:LISTEN` prints nothing - a taken port is `BLOCKED`, because health would be answered by another process), run `up` (its `-p ge-${GRAPH_RUN_ID:?}` gives the run its own project), wait on `health` (`url`: `curl -fsS --max-time 5 --retry <n> --retry-delay 2 --retry-max-time <timeout> --retry-connrefused --retry-all-errors <url>`, and the body must contain `health.expect`; or run `command`), then `seed`. Run `down` as its own final call, whatever the outcome - including after a failed `up` or health check. Not a `trap`: a trap set in the `up` call fires when that call ends, before anything is verified. An empty `up`, `baseUrl` or `health`, a name in `runtime.env` that is not exported, or health never passing: `BLOCKED`, naming the field that is missing or the command that failed and its output. Fall back to the repo's README / CLAUDE.md only to fill a gap the profile leaves, and say you did. Seeded, deterministic data - never verify against empty or random state, and never against a shared environment. The one exception is the `post-deploy` node, which runs under `post-deploy-verification` instead of this step: vetted read-only smoke requests, no hostile probes.
   **Compose isolation check.** `-p` renames only project-scoped resources.
   Anything with its own `name:`, a `container_name:`, anything `external:
   true`, a host-backed volume, `network_mode: host` / `container:...`,
   `volumes_from: container:...` or a bind mount from outside the worktree
   stays shared with the developer's stack - their app's `db` becomes
   resolvable from yours, or their files become yours to seed and wipe. Run the
   check beside this file with the same project and `-f` files as `up`; it
   renders every profile (`--profile '*'`), prints one line per leak and exits
   1, and exits 2 when the config cannot be rendered (`BLOCKED`, never "no
   leaks"):

   ```bash
   GRAPH_RUN_ID=<run id> bash "<this skill's dir>/compose_isolation.sh" \
     "ge-<run id>" <the -f files from runtime.up>
   ```

   A relative bind (`./data`) is fine: qa runs in the run's own worktree, so
   it is the run's copy. Tested by `tests/test_compose_isolation.sh` (Compose
   v2.40.3): each leak kind above, a leak hidden behind a profile, a clean
   file, and an unparseable file (exit 2). The fix for a leak is a committed
   `compose.qa.yaml` override (recipe: `/graph-init` step 4,
   `commands/graph-init.md`).

3. **Verify each criterion end-to-end**, choosing the cheapest sufficient probe:
   - **UI flow**: drive the real browser (Playwright script, or chrome automation tools). Walk the journey a user would, not the shortcut a developer would.
   - **API contract**: run the PR's Bruno folders with the exact command in `api-contract` "How it runs" - `--env <api.env>`, one `--env-var NAME="$NAME"` per token name in `runtime.env` (an unbound `{{TOKEN}}` is sent literally and fails as a false bug), `--reporter-skip-all-headers`, and the report at an absolute `"$REPO_ROOT/.graph/<run>/qa/..."` path (bru runs from the collection directory) - or run the complete collection once for the final gate; reuse its touched-case results. A failed request is a `FAILED` row with the report path. Then Schemathesis against `api.schema` per `schemathesis`: the gate checks are pass/fail rows (report path + seed), the full default set runs report-only and each unique drift failure is written as an Important finding to `.graph/<run>/qa-findings.json`, in the findings schema from `review-protocol` (`{"schema_version": 1, "verdict": ..., "reviewed": ..., "findings": [...]}`; qa always writes this file, with an empty `findings` list when there is nothing, so an absent file never reads as zero findings), which the fix node reads beside the reviewer's `findings.json`. Exit 2 (schema did not load) is `BLOCKED`. An API criterion with no Bruno request behind it is `FAILED` - the house rule is part of the acceptance criteria. curl is for your one hostile probe, not a substitute for the suite.
   - **Data effects**: query the store after the action; verify the write, and verify what must NOT have changed.
4. **Capture evidence per criterion**: a screenshot for UI, the response body for API, the query result for data. Save into the run directory.
   - For UI criteria, start from the implementer's before/after pair under the profile's `uxEvidence.path` (see `ux-evidence`). Verify the after capture matches what is running now; re-capture with the committed script if it is stale. Before and after indistinguishable where the criteria say they differ is a `FAILED` row, not a note. A UI criterion with no before/after pair at all is `FAILED` - the house rule is part of the acceptance criteria.
5. **Probe one level beyond the happy path** per criterion: the empty state, the double-submit, the invalid input, the refresh mid-flow. One good hostile probe each - this is verification, not a test suite.

## Report

One row per criterion:

```
case ID | VERIFIED / FAILED / BLOCKED | candidate/runtime | evidence path | note
```

- A row's status is exactly `VERIFIED`, `FAILED` or `BLOCKED`. Any other status (`NOT RUN`, `SKIPPED`, `N/A`, out of time or budget) reads as `BLOCKED`, with its reason.
- A `FAILED` sub-check fails its row; it cannot be moved out as a side defect.
- `FAILED` rows: exact reproduction steps and what happened instead. Never soften a failure into a note.
- `BLOCKED` (could not stand the system up, missing seed, missing env, a required case absent from the harness report): say exactly what is missing. Do not mark VERIFIED anything you could not run.

Then one verdict line: `PASS` only when every required row is `VERIFIED`;
`FAIL INCOMPLETE: <row ids>` when any row is `FAILED`; otherwise
`INCOMPLETE: <row ids>`. The ids name every required row that is not
`VERIFIED`. `infra-verification` adds `PASS (static-only)`, and
`post-deploy-verification` keeps its own verdicts.

## Lead and leaves

The engine picks the shape of a qa leg from its criteria; the first row that
matches wins. A lane is one surface a user reaches: web UI, API, mobile, data,
notifications, CLI. A fix-loop re-run picks again from the rows it re-runs.

| Criteria | Shape |
| --- | --- |
| a nonempty `runtime.command` | one `qa`: the harness owns the stack and every case in one process |
| 2+ platforms (for example web and a mobile app), or ~8+ criteria and 3+ lanes | one `qa-lead` over at most 4 `qa` leaves |
| 2 lanes | one `qa-lead` over two `qa` leaves; the engine never owns a qa runtime |
| 1 surface, or anything else | one `qa` |

A leaf verifies on a stack it does not own. Its lead, the `qa-lead`,
follows `agents/qa-lead.md`: it stands the runtime up once
under the run's `GRAPH_RUN_ID`, dispatches every leaf in the foreground in one
message with the line `leaf mode: the runtime is up and owned by the lead -
never run up, seed or down`, merges their reports from disk and runs `down`
last. Each lane writes evidence to `.graph/<run>/qa/<lane>/`, its criterion
table and verdict line to `.graph/<run>/qa/<lane>.md` and its findings to
`.graph/<run>/qa/<lane>-findings.json`; only the lead writes `qa.md` and
`qa-findings.json`, so parallel lanes never overwrite each other.

## Rules

- **Exit code 0 is not evidence.** A green command whose output you did not read proves nothing - read the output, look at the screenshot.
- Verify through the public surface (UI, API), not by calling internals - internals passing is how broken features ship.
- You write test scripts and evidence files only. Never patch the product code; a failure goes back to the fix loop.
- **Simulators.** Every simulator use goes through `bash <plugin-root>/scripts/sim-session.sh` (headless). Never `open -a Simulator`. Close what you open. Agents get dedicated `graph-sim-*` devices (the wrapper creates or reuses one on the newest iOS runtime) and never touch any other simulator; the owner's devices are refused unless the owner names one (`--device <it> --allow-foreign`, which runs on it and never shuts it down). Multi-step qa (capture, read the PNG, decide the next step): `sim-session.sh acquire` once, which prints `SIM_UDID=` and `SIM_LEASE=`; run every step as `sim-session.sh run --lease <id> -- <command>`, which exports `SIM_UDID` and renews the lease; `sim-session.sh release --lease <id>` when the lane ends, failure included. A single command: `sim-session.sh -- <command>` (acquire, run and release in one call). A lease unused for 15 minutes (set `GRAPH_SIM_IDLE_MIN` on `acquire` for longer) expires: its next `run` exits 2, acquire again. The plugin's Stop and SubagentStop reaper only shuts down `graph-sim-*` devices a wrapper booted (that same boot) and nothing holds; it catches what a killed agent leaked and is not your teardown.
- **Compile lane, test-run lane.** When the profile declares `lanes:`, a compile (`build-for-testing`, `build`) runs inside `bash <plugin-root>/scripts/lane-run.sh xcodebuild --slots <n> -- <command>` and each `test-without-building` run against the already built product in the `xctest` lane, `lane-run.sh xctest --slots <n> -- <command>` (`lanes.xctest` slots, or the `xcodebuild` count when the profile does not declare it), each its own command, with the simulator lease inside the lane wrapper. Never a `test-without-building` run in the `xcodebuild` lane: it holds a compile slot it does not need, and a 20 s run queues behind a long compile. Type `<plugin-root>` as a literal absolute path, never through a shell variable. Rules and elastic slots: `<plugin-root>/docs/engine/lanes.md`.
