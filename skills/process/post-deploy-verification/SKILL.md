---
name: post-deploy-verification
description: Use after a run's change is merged and deployed - waits for the merged commit to serve, runs vetted read-only smoke requests and baseline-compared PromQL checks against the deployed environment, and reports PASS / FAIL / BLOCKED / SKIPPED with a rollback recommendation. Never mutates shared data, never rolls back on its own, never feeds the fix loop.
---

# Post-deploy verification

Merged is not shipped. The change is done when the deployed environment runs
it and nothing got worse. This skill is the check that closes that gap. Its
metric checks borrow the shape Argo Rollouts analysis uses - a query, an
interval, a count, a success condition, a failure limit - so they read the
same whether or not the cluster runs Rollouts.

Sources: Argo Rollouts [Analysis & Progressive Delivery](https://argoproj.github.io/argo-rollouts/features/analysis/)
(`interval`, `count`, `successCondition`, `failureLimit`; the Prometheus
provider returns a vector, so conditions index it: `result[0] < 0.01`);
`superpowers:verification-before-completion` for what counts as evidence.

## This replaces parts of qa-verification

In a `post-deploy` node, this skill overrides `qa-verification` where they
differ: no `runtime` stand-up (the environment already exists), **no hostile
probes** (the environment is shared), and a `FAIL` never goes to the fix loop.
Everything else - evidence per row, exit code is not evidence, never mark
verified what did not run - still holds.

## The deployed environment is shared

- **Read-only, enforced before anything runs.** Only requests tagged `smoke`
  are candidates, and each one is vetted: GET, HEAD and OPTIONS run; a write
  runs only if `{{testTenant}}` is a whole segment of its URL **path** and
  `deploy.testTenant` is non-empty (qa passes `--env-var
  testTenant=<deploy.testTenant>`). A mention in docs, body, query string or
  headers does not count: it does not decide whose rows the write touches. Anything else is refused and named - it is a
  finding against the collection, not something to run. `vet_smoke.py` beside
  this file does the vetting (below).
- **Never roll back, never re-sync, never scale.** A FAIL produces a rollback
  *recommendation* - the profile's `deploy.rollback`, filled in - for the
  owner. Rolling back a shared environment is the owner's call.
- **Credentials by name only** (`deploy.env`), passed as `--env-var` / headers
  at run time. Reports skip all headers; nothing secret is written to the run
  directory.

## Steps

0. **Nothing to check.** `deploy.wait` empty: report `SKIPPED (no deploy block)`
   and stop. That is a result, not a failure.
1. **Wait for the deploy to land** with `deploy.wait` (e.g. `argocd app wait
   <app> --sync --health --timeout 600`, or a loop on a version endpoint until
   it reports the merge SHA the ledger recorded). Timeout = `BLOCKED`, naming
   what never converged. Checking before the new version serves proves the old
   version works. Then record `deployedAt`: when the merged revision **started**
   rolling out, never the time `wait` returned - that is too late on a resumed
   run (the deploy landed yesterday, `wait` returns at once) and on any rolling
   update (new pods served traffic while `wait` blocked), and a late baseline
   already contains the regression it is meant to expose. Use `deploy.startedAt`
   with `${SHA}` set to the merge SHA - for Argo CD, `kubectl get application
   <app> -n argocd -o json | jq -r --arg s "$SHA" '.status.history[] |
   select(.revision == $s) | .deployStartedAt'` (Argo appends `revision` and
   `deployStartedAt` to `status.history` on every successful sync). Empty or
   unset: the merge commit's time, `git show -s --format=%cI <sha>`, which is
   never after the rollout began.
2. **Vet, then smoke.**

   ```bash
   mkdir -p "$REPO_ROOT/.graph/<run>/post-deploy"
   python3 "<this skill's dir>/vet_smoke.py" "$REPO_ROOT/<api.collection>" \
     --test-tenant "<deploy.testTenant>" > "$REPO_ROOT/.graph/<run>/post-deploy/vetted.txt"
   ```

   Exit 1 means at least one `REFUSE` line: those requests are listed as
   findings and do not run. Exit 2 means nothing was vetted - the collection
   path does not exist (an unset `$REPO_ROOT` makes it `/bruno`) or it holds no
   `smoke`-tagged request - and is `BLOCKED`: an empty smoke list must never let
   step 4 call "every smoke request passed" true. Then run each `RUN` file on its own, from the
   collection directory:

   ```bash
   bru run <file> --env <deploy.bruEnv> --env-var testTenant="<deploy.testTenant>" \
     --env-var <NAME>="$<NAME>" ... --reporter-skip-all-headers \
     --reporter-junit "$REPO_ROOT/.graph/<run>/post-deploy/bru-<name>.xml"
   ```

   One `--env-var NAME="$NAME"` per name in `deploy.env`. Spiked 2026-09-23 on nine `.bru` files: `RUN` for a smoke GET and a smoke
   POST to `/tenants/{{testTenant}}/users`; `REFUSE` (exit 1) for an unscoped
   POST, a POST naming `{{testTenant}}` only in `docs`, a PUT naming it only in
   the body, a DELETE naming it only in the query string, and a GraphQL
   request; a `smoke-extended` tag and an untagged DELETE ignored. With
   `--test-tenant` empty, the tenant-scoped POST is refused too. The review's
   18 adversarial files added: a GET block followed by a DELETE block (Bruno
   merges them and sends the DELETE) - refused; `..` path segments - refused;
   Python 3.9 (macOS `/usr/bin/python3`) - runs. The final review's bypasses
   are now refused too - a script that changes the method or URL, one that runs
   or sends another request (in the file, a `folder.bru` or `collection.bru`),
   a `vars` block or `setVar` rebinding `testTenant`, an indented second method
   block - and a missing collection or zero smoke requests exits 2. All of it
   is pinned by `tests/test_vet_smoke.py` (15 cases; 8 fail against the
   previous version).
3. **Metrics against a baseline.** Each `deploy.checks` entry has `query` (a
   rate or ratio over a window, e.g. `[10m]`), `initialDelay`, `interval`,
   `count`, `failureLimit` (default 0, as in Argo) and `successCondition` over
   `result[0]` and `baseline[0]`, e.g. `result[0] <= baseline[0] * 1.5 + 0.001`.
   - **Baseline once, at `deployedAt`:** an instant query evaluated AT the
     moment the rollout started - `/api/v1/query?query=<query>&time=<deployedAt
     as unix seconds or RFC3339>` - so its window ends at the deploy and covers
     only the old version. Without `time=` Prometheus evaluates at "now", after
     the smoke run, and the baseline already contains new-version traffic. That value is `baseline[0]`
     for every measurement; no offset arithmetic, nothing in the profile to
     rewrite.
   - **Then wait `initialDelay`**, counted from when `wait` returned, at least the query's window (Argo has the
     same field for the same reason): measured earlier, the window still
     averages in old-version traffic and dilutes a regression below the
     threshold.
   - **Then measure** `count` times, `interval` apart; more than
     `failureLimit` failed measurements is a FAIL.

   The `baseline` operand is this skill's extension of Argo's shape - Argo's
   own conditions see only `result`.
4. **Verdict**: `PASS` when every vetted smoke request and every check passed;
   `FAIL` with the failing evidence and the filled-in rollback recommendation;
   `BLOCKED` when the deploy never landed, a check could not run, or a refused
   smoke request left an acceptance criterion unverified; `SKIPPED` from step
   0. Never a PASS on missing data.

## Anti-patterns

- Smoke-testing before the rollout finished. Failure: the old pods answer and
  the run reports PASS for code that is not live.
- `bru run --tags smoke` over the whole collection on a shared environment.
  Failure: an older write request tagged `smoke` mutates real data; vet first,
  run files one by one.
- An absolute threshold with no baseline (`result[0] < 0.01`). Failure: an
  error ratio that went from 0.1% to 0.9% passes.
- Auto-rollback from an agent. Failure: an agent with write access to a shared
  environment acting on a noisy metric at 3am.
