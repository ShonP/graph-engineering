---
name: qa-verification
description: Use when verifying that shipped work actually does what its acceptance criteria claim - end-to-end UI checks, API contract checks, production smoke tests. Evidence-based; a criterion without captured evidence is not verified.
---

# QA Verification

Review reads code; QA runs it. This skill verifies acceptance criteria against a **running system**, and its output is evidence, not opinion.

## Protocol

1. **Read the acceptance criteria** from the task/plan. Each becomes one checklist row. No criteria = `NEEDS_SETUP` (ask the planner, do not invent criteria).
2. **Stand the system up from the profile's `runtime` block.** If `runtime.none` holds a reason, skip this step: verify through the repo's own public surface instead (the CLI as a user runs it, the package imported from a clean environment, the documented commands) and say so in the report. Otherwise, in this order. **Every Bash call is a fresh shell**: an `export` does not survive to the next call (spiked), so prefix every runtime command, in every call, with `GRAPH_RUN_ID=<the run id from your dispatch>` - the profile's commands use `${GRAPH_RUN_ID:?}`, which fails loudly instead of running as project `ge-`. The names in `runtime.env` are read from the environment you were started with (never write their values anywhere). For a compose `up`, run the isolation check below and refuse to start (`BLOCKED`, naming each line it prints) until it exits 0; check `runtime.port` is free (`lsof -nP -iTCP:<port> -sTCP:LISTEN` prints nothing - a taken port is `BLOCKED`, because health would be answered by another process), run `up` (its `-p ge-${GRAPH_RUN_ID:?}` gives the run its own project), wait on `health` (`url`: `curl -fsS --max-time 5 --retry <n> --retry-delay 2 --retry-max-time <timeout> --retry-connrefused --retry-all-errors <url>`, and the body must contain `health.expect`; or run `command`), then `seed`. Run `down` as its own final call, whatever the outcome - including after a failed `up` or health check. Not a `trap`: a trap set in the `up` call fires when that call ends, before anything is verified. An empty `up`, `baseUrl` or `health`, a name in `runtime.env` that is not exported, or health never passing: `BLOCKED`, naming the field that is missing or the command that failed and its output. Fall back to the repo's README / CLAUDE.md only to fill a gap the profile leaves, and say you did. Seeded, deterministic data - never verify against empty or random state, and never against a shared environment. The one exception is the `post-deploy` node, which runs under `post-deploy-verification` instead of this step: vetted read-only smoke requests, no hostile probes.
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
   `compose.qa.yaml` override (template `runtime.up` comment).

3. **Verify each criterion end-to-end**, choosing the cheapest sufficient probe:
   - **UI flow**: drive the real browser (Playwright script, or chrome automation tools). Walk the journey a user would, not the shortcut a developer would.
   - **API contract**: run the PR's Bruno folders with the exact command in `api-contract` "How it runs" - `--env <api.env>`, one `--env-var NAME="$NAME"` per token name in `runtime.env` (an unbound `{{TOKEN}}` is sent literally and fails as a false bug), `--reporter-skip-all-headers`, and the report at an absolute `"$REPO_ROOT/.graph/<run>/qa/..."` path (bru runs from the collection directory) - then the whole collection for regressions. A failed request is a `FAILED` row with the report path. Then Schemathesis against `api.schema` per `schemathesis`: the gate checks are pass/fail rows (report path + seed), the full default set runs report-only and each unique drift failure is written as an Important finding to `.graph/<run>/qa-findings.json`, in the `review-protocol` format (qa always writes this file, `[]` when there is nothing, so an absent file never reads as zero findings), which the fix node reads beside the reviewer's `findings.json`. Exit 2 (schema did not load) is `BLOCKED`. An API criterion with no Bruno request behind it is `FAILED` - the house rule is part of the acceptance criteria. curl is for your one hostile probe, not a substitute for the suite.
   - **Data effects**: query the store after the action; verify the write, and verify what must NOT have changed.
4. **Capture evidence per criterion**: a screenshot for UI, the response body for API, the query result for data. Save into the run directory.
   - For UI criteria, start from the implementer's before/after pair under the profile's `uxEvidence.path` (see `ux-evidence`). Verify the after capture matches what is running now; re-capture with the committed script if it is stale. Before and after indistinguishable where the criteria say they differ is a `FAILED` row, not a note. A UI criterion with no before/after pair at all is `FAILED` - the house rule is part of the acceptance criteria.
5. **Probe one level beyond the happy path** per criterion: the empty state, the double-submit, the invalid input, the refresh mid-flow. One good hostile probe each - this is verification, not a test suite.

## Report

One row per criterion:

```
criterion | VERIFIED / FAILED / BLOCKED | evidence path | note
```

- `FAILED` rows: exact reproduction steps and what happened instead. Never soften a failure into a note.
- `BLOCKED` (could not stand the system up, missing seed, missing env): say exactly what is missing. Do not mark VERIFIED anything you could not run.

## Rules

- **Exit code 0 is not evidence.** A green command whose output you did not read proves nothing - read the output, look at the screenshot.
- Verify through the public surface (UI, API), not by calling internals - internals passing is how broken features ship.
- You write test scripts and evidence files only. Never patch the product code; a failure goes back to the fix loop.
