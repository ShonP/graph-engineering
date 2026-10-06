# The `runtime.command` harness contract

A nonempty `runtime.command` in the profile hands the whole stack to one
process: it stands the stack up, runs every acceptance case against the public
surface, tears the stack down and writes a report. qa runs it once, reads the
report and opens the evidence; qa never calls a service the harness already
tore down. This is what any such harness must do, whatever the stack (web app,
API, CLI, mobile backend, cluster). `../templates/qa-harness.sh` is a runnable
skeleton that implements all of it; `../tests/test_qa_harness_template.sh`
proves it.

## What the plugin ships and what the repo owns

| Plugin (generic, this contract and the template) | Consuming repo (behind `runtime.command`) |
| --- | --- |
| run-id and worktree-root guards, evidence layout, teardown on every exit, the report | the hooks file: stack up, readiness, seeds, the case commands |
| status and exit-code rules | login helpers, throwaway users and their account cleanup |
| the accessibility audit recipe below | the pinned `axe-core` dev dependency, the pages to audit |

App-specific helpers (login, throwaway users, account cleanup) belong to the
consuming repo, committed beside its hooks file. Per-run drivers (a one-off
Playwright script, a probe written for this run's criteria) stay in the run
directory, `.graph/<run>/qa/`, uncommitted.

## Invocation

qa runs the command from the candidate worktree root with the run id set:

```bash
GRAPH_RUN_ID=<run id> <runtime.command>
# for the template, runtime.command is for example:
#   GE_HARNESS_HOOKS=qa/hooks.sh bash qa/qa-harness.sh "$PWD"
```

With the template, the repo's hooks file (named by `GE_HARNESS_HOOKS`)
defines `ge_setup`, `ge_checks` (one `ge_case <case-id> <command...>` per
case) and `ge_teardown`; the template's header documents the rest.

## Duties

1. **`GRAPH_RUN_ID` is required.** Missing, or not a plain name
   (`[A-Za-z0-9][A-Za-z0-9._-]*`): refuse with exit 2 before anything starts.
   The id names every isolated resource the run creates (compose project,
   database, namespace, bucket prefix) and the evidence folder.
2. **Refuse to run outside the candidate worktree root passed as the first
   argument.** The argument must be a git worktree's top level and the working
   directory must be that root; otherwise exit 2. A harness run from anywhere
   else verifies, seeds and wipes a tree that is not the candidate.
3. **Record the candidate before setup:** `revision` is `git rev-parse HEAD`;
   `dirty_sha256` is the sha256 of the uncommitted diff plus untracked files,
   `.graph/` excluded, and `null` when the tree is clean.
4. **Setup owns readiness and isolation:** the stack, a readiness wait,
   deterministic seeds and throwaway accounts, all named from the run id. Never
   a shared environment.
5. **One case per acceptance criterion id**, through the public surface. Each
   case writes its evidence (response bodies, screenshots, query results,
   `output.log`) to `.graph/<run>/qa/<case-id>/`, emptied at case start so no
   earlier round's files pass for this one. A case ends `VERIFIED`, `FAILED` or
   `BLOCKED` (it could not execute: a missing prerequisite, never a soft fail);
   the template maps a case command's exit 0 to `VERIFIED`, 77 to `BLOCKED`
   and anything else to `FAILED`.
6. **Teardown always runs:** after success, a failed case, a failed setup, an
   early exit from the checks, and an interrupt. It removes everything setup
   created, throwaway accounts included, and logs to `teardown.log`.
7. **Write the report** to `.graph/<run>/qa/harness-report.json`, after
   teardown, so its exit code covers teardown too.

## The report

```json
{
  "run_id": "r1",
  "candidate": {"revision": "<40-hex HEAD>", "dirty_sha256": null},
  "runtime_instance": "ge-r1",
  "cases": [{"id": "AC-1", "status": "VERIFIED", "evidence": ".graph/r1/qa/AC-1"}],
  "executed": 1,
  "skipped": 0,
  "exit_code": 0
}
```

`executed` counts cases that reached `VERIFIED` or `FAILED`; `skipped` counts
`BLOCKED` ones. `exit_code`, also the process exit: 0 every case `VERIFIED`;
1 any case `FAILED`; 2 refused, nothing started, no report; 3 incomplete (a
`BLOCKED` case, failed setup, aborted checks, failed teardown, a duplicate or
invalid case id, or no cases at all).

How qa reads it: a required case missing from `cases` is `BLOCKED`; a
`revision` or `dirty_sha256` that is not the candidate qa was asked to verify
makes every row `BLOCKED` (a stale report); exit 0 is not evidence, so open
each case folder before calling a row `VERIFIED`.

## UI criteria: the accessibility audit

When the repo has a web UI, each UI case also runs an axe audit through
`playwright-cli` on the page the criterion names and saves it as `a11y.json` in
the case folder. A `critical` or `serious` violation on an element the change
touched is a `FAILED` sub-check, so it fails the row. Pin `axe-core` as a dev
dependency. `file:` URLs are refused, so audit the served app.

```bash
playwright-cli open "$BASE_URL/<page>"
playwright-cli --raw run-code --filename=a11y.js >"$GE_EVIDENCE_DIR/a11y.json"
```

```js
// a11y.js; the path resolves from the directory playwright-cli runs in
async page => {
  await page.addScriptTag({ path: 'node_modules/axe-core/axe.min.js' });
  const r = await page.evaluate(() => axe.run(document, { runOnly: ['wcag2a', 'wcag2aa'] }));
  return r.violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => n.target) }));
}
```

Serve the page over HTTP; a `file:` page is refused.
