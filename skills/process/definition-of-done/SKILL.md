---
name: definition-of-done
description: Use when planning, implementing or reviewing any task - maps each change type (API endpoint, DB schema, infra/k8s, background job, UI, config/flag, dependency bump, AI agent/prompt) to the artifacts its PR must carry beyond the code - tests, contract suite, migration and rollback, rendered-manifest diff, observability, docs, rollout and rollback plan. The planner stamps the rows into acceptance criteria; the implementer ships them; the reviewer checks them.
---

# Definition of done

A task is done when the code works **and** the change can be operated: someone
can see it misbehave, roll it back, and understand it later. Code review checks
the first; this skill names the second, per change type, so no one has to
remember it at 5pm.

Sources the matrix is synthesized from - it is a house synthesis, not a copy of
any one table:

- Google eng-practices, [What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html) - tests in the same change as the code, functionality, complexity.
- Google SRE, [Reliable Product Launches at Scale](https://sre.google/resources/book-update/reliable-product-launches-at-scale/) and its Launch Coordination Checklist - monitoring, capacity, rollout, rollback as launch preconditions.
- DORA [capabilities](https://dora.dev/capabilities/) - test automation, deployment automation, monitoring and observability.
- Martin Fowler, [ParallelChange](https://martinfowler.com/bliki/ParallelChange.html) - expand, migrate, contract for any change a live reader depends on.
- The house rules this composes rather than restates: `api-contract`, `ux-evidence`, `prior-art`, and `superpowers:verification-before-completion` for what "verified" means.

## How to use it

1. **Classify** every task in the plan by the rows below it matches. A task can
   match several (an endpoint that adds a column is API + DB schema).
2. **Stamp** each matched row's required cells into the task's acceptance
   criteria, verbatim enough that the reviewer can tick them. A cell marked
   *if* applies only when its condition holds; say which way it went.
3. **Ship** them in the same PR as the code. "Follow-up PR for the alert" is how
   the alert never ships.
4. **Check** at review: a required cell with no artifact and no written reason
   is Important; one that is also a stated house rule (`api-contract`,
   `ux-evidence`) is Blocking, as those skills already say.

## The matrix

| Change type | Tests | Contract | Data change | Rendered diff | Observability | Docs | Rollout / rollback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **API endpoint** | unit + integration through the handler | Bruno suite + current schema (`api-contract`), Schemathesis gate | *if* it writes new data: see DB row | - | a log line per failure path with a correlation id; request metric; alert *if* SLO-bearing | schema is the doc | *if* breaking: versioned route or ParallelChange, never an in-place break |
| **DB schema / migration** | migration applied up **and** down on a copy with data; the query it serves | *if* the API shape changes | **ParallelChange**: expand (additive), migrate (backfill, dual-write), contract (drop) in separate deploys; lock/statement timeout set | - | slow-query or lock-wait signal for the new access path | ADR *if* a modelling decision | apply order, backfill plan, and the down path - or why none is safe and what replaces it |
| **Infra / k8s / Helm / Argo** | render + validate (see `infra-verification`: `helm template` / `kustomize build`, kubeconform, policy) | *if* a service's endpoints change | *if* it touches a stateful set or PVC: data survives | **required**: the rendered manifest diff against the base, in the PR | dashboard / alert for new resources; probes on new workloads | runbook line for anything an operator must do | sync-wave order; `git revert` path proven to render |
| **Background job / queue consumer** | idempotency test (same message twice = one effect); retry and poison-message test | *if* it emits or consumes an event: the schema | *if* it writes | *if* deploy config changes | consumer lag / age-of-oldest metric + alert; dead-letter count | - | replay or backfill plan; how to pause the consumer |
| **UI** | component + one e2e for the journey | the experience spec's placement and state rows (`ux-journey`), when one exists | - | - | client error tracking on the new path | before/after evidence (`ux-evidence`) | behind a flag *if* risky or partial |
| **Config / feature flag** | both flag states tested | - | - | *if* delivered as a ConfigMap or values | the flag state is observable (log / metric label) | flag registry entry: owner, default, removal date | flip-off is the rollback; say who can flip it |
| **Dependency bump** | full suite; the changelog's breaking changes checked against usage | - | *if* the dep owns a schema | *if* it is a base image or chart | - | the reason, in the PR | lockfile revert; canary *if* runtime-critical |
| **AI agent / prompt** | eval set or golden cases, run before and after, numbers in the PR | *if* exposed over an API: `api-contract` | - | - | token, cost and latency per call; guardrail / refusal counter | prompt change note | prompt/model version pinned; previous version one flag away |

Every row also carries the always-on duties: tests written first
(`review-testing-rules`), the prior-art note (`prior-art`), and fresh
verification evidence before any "done" claim
(`superpowers:verification-before-completion`).

## Rules

- **The matrix is a floor, not a menu.** A cell can be answered "not
  applicable, because ..." in one line. It cannot be silently skipped.
- **Rollback is a thing you ran, not a sentence.** For DB and infra rows the
  down path or the revert render is executed once, and the command and its
  output go in the PR.
- **Observability ships with the code path it watches.** An alert for a feature
  that shipped last week is a separate incident waiting to be found.
- **Small tasks still get classified.** A one-line config change is a
  Config row; its cells are short, not absent.

## Anti-patterns

- "Tests will follow." Failure: they never do, and the change is now
  load-bearing and untested.
- A migration that drops or renames in the same deploy that stops reading.
  Failure: the old pods still running during rollout read a column that is
  gone.
- A dashboard link as the observability artifact. Failure: nobody is paged; an
  alert with an owner is the artifact.
- "Rollback: revert the PR" on a migration. Failure: the data already moved.
