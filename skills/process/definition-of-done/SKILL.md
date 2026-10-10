---
name: definition-of-done
description: Use when planning, implementing or reviewing any task - maps each change type (API endpoint, DB schema, infra/k8s, background job, UI, config/flag, dependency bump, AI agent/prompt) to the artifacts its PR must carry beyond the code - tests, contract suite, migration, rendered-manifest diff, observability, docs, rollout and rollback.
---

# Definition of done

Done means the code works **and** the change can be operated: someone can see it misbehave, roll it back and understand it later.

Sources, synthesized: Google [code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html), [SRE launches](https://sre.google/resources/book-update/reliable-product-launches-at-scale/), [DORA](https://dora.dev/capabilities/), Fowler [ParallelChange](https://martinfowler.com/bliki/ParallelChange.html), and the house rules the cells name.

## Use

- **Classify** each task by every row it matches, small ones too (an endpoint adding a column is API + DB; a config tweak is a short Config row).
- **Stamp** matched cells into its acceptance criteria, tickable at review. An *if* cell applies only when its condition holds; say which way.
- **Floor, not menu**: a cell may be "not applicable, because ..." in one line, never silently skipped.
- **Ship** every cell, observability included, in the code's PR.
- **Rollback is run, not written**: DB and infra rows run the down path or revert render once, command and output in the PR.
- **Review**: a required cell with no artifact and no written reason is Important; Blocking when also `api-contract` or `ux-evidence`.

## The matrix

| Change type | Tests | Contract | Data change | Rendered diff | Observability | Docs | Rollout / rollback |
|-|-|-|-|-|-|-|-|
| **API endpoint** | unit + integration through the handler | `api-contract`: Bruno, current schema, Schemathesis | *if* it writes new data: DB row | - | failure-path log with correlation id; request metric; alert *if* SLO-bearing | the schema | *if* breaking: versioned route or ParallelChange, never in place |
| **DB schema / migration** | up **and** down on a copy with data; the query it serves | *if* the API shape changes | **ParallelChange**: expand, migrate (backfill, dual-write), contract (drop), separate deploys; lock/statement timeout set | - | slow-query or lock-wait signal on the new access path | ADR *if* a modelling decision | apply order, backfill plan, down path (or why none is safe, and its replacement) |
| **Infra / k8s / Helm / Argo** | render + validate (`infra-verification`) | *if* a service's endpoints change | *if* a stateful set or PVC: data survives | **required**: rendered manifest diff vs base, in the PR | dashboard/alert for new resources; probes on new workloads | runbook line for any operator step | sync-wave order; `git revert` proven to render |
| **Background job / queue consumer** | idempotency (same message twice = one effect); retry and poison-message tests | *if* it emits or consumes an event: the schema | *if* it writes | *if* deploy config changes | consumer lag/oldest-message age + alert; dead-letter count; cost per run times frequency (missing on a recurring metered job is Important) | - | replay or backfill plan; kill switch pausing it |
| **Outbound messaging** (email, push, SMS, webhooks to people) | audience predicate and render tested; same trigger twice = one send; production read-only dry run, candidate count and at most 5 masked ids in the PR, never raw addresses; a dry run NOT RUN counts as BLOCKED | *if* a provider API or payload: its schema | *if* it records sends: the key making a resend a no-op | - | sent, failed, suppressed counts | copy and audience rule, in the PR | kill switch stopping sends without a deploy; who can flip it |
| **UI** | component + one journey e2e | experience spec placement and state rows (`ux-journey`), if one exists | - | - | client error tracking on the new path | before/after evidence (`ux-evidence`) | flag *if* risky or partial |
| **Config / feature flag / build** | both flag states; *if* it touches auth, build or flag config: env parity, profile `ci.parity` job green; clean checkout: CI green on the run branch where CI exists, else *if* it touches .gitignore, compose, build or generated paths, a build from `git archive $(git write-tree)` | - | - | *if* shipped as a ConfigMap or values | flag state observable (log/metric label) | flag registry entry: owner, default, removal date | flip-off is the rollback; who can flip it |
| **Dependency bump** | full suite; changelog breaking changes checked against usage | - | *if* the dep owns a schema | *if* a base image or chart | - | the reason, in the PR | lockfile revert; canary *if* runtime-critical |
| **Refactor** | behaviour contract: the touched code's tests pass unchanged before and after; characterization tests committed first, only when the impact map reports a coverage gap | unchanged; a moved contract adds its row | - | - | - | - | revert; behaviour unchanged, no flag |
| **AI agent / prompt** | eval set or golden cases, before and after, numbers in the PR | *if* exposed over an API: `api-contract` | - | - | token, cost, latency per call; guardrail/refusal counter | prompt change note | prompt/model version pinned; previous one flag away |
| **Host blast radius** (heavy builds, images, caches, local clusters) | free disk checked (`df`) before heavy work, refusing below a stated floor | - | - | - | image and cache sizes bounded and reported | - | long commands in the background; cleanup of its images, volumes and worktrees |

Every row also carries tests first (`review-testing-rules`), the `prior-art` note, fresh verification before any "done" claim (`superpowers:verification-before-completion`), and the quick gate: when the profile declares `gates.quick`, run it in the worktree before reporting `DONE`, report its exit line, and fix a red one like a red test. None declared: say so in one line.

## Anti-patterns

- Dropping or renaming a column in the deploy that stops reading it: old pods mid-rollout read a missing column.
- A dashboard link as the observability artifact: nobody is paged. Ship an alert with an owner.
