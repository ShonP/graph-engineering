---
name: argocd
description: Use when writing or reviewing Argo CD Applications, ApplicationSets, app-of-apps roots, sync waves and hooks, custom health checks in argocd-cm, or Argo-rendered Helm sources. Covers what a wave actually waits for, why a child Application needs its own health Lua, and how to bound a gate that never opens.
license: MIT
---

# Argo CD

Written for Argo CD **3.5.2** (`argocd version --client` on the authoring machine reported
`v3.5.2+e258ee2`). Every page below is the `/en/release-3.5/` build of the docs, not `stable`.

Sources (fetched 2026-09-10, argocd 3.5.2):
- https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/ - "Cluster Bootstrapping - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/ - "Sync Phases and Waves - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/ - "Resource Health - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/multiple_sources/ - "Multiple Sources for an Application - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/applicationset/ - "Introduction - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/ - "Helm - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-options/ - "Sync Options - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/auto_sync/ - "Automated Sync Policy - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/diffing/ - "Diff Customization - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/argocd-cmd-params-cm-yaml/ - "argocd-cmd-params-cm.yaml example - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/commands/argocd_app_diff/ - "argocd app diff Command Reference - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/commands/argocd_admin_settings_resource-overrides_health/ - "argocd admin settings resource-overrides health Command Reference - Argo CD - Declarative GitOps CD for Kubernetes"

`operator-manual/commands/argocd_admin_settings_resource-overrides_health/` returns 404 at
release-3.5; the command reference lives under `user-guide/commands/`, cited above.
`user-guide/resource_hooks/` returns 200 but renders only "This page has moved", so every hook
rule here cites the sync-waves page, which is where the hook tables now live.

## When to apply

- Any `argoproj.io/v1alpha1` `Application` or `ApplicationSet` manifest.
- An app-of-apps root and the child Applications it renders.
- `argocd.argoproj.io/sync-wave`, `argocd.argoproj.io/hook`, `argocd.argoproj.io/sync-options`
  annotations anywhere.
- `resource.customizations.health.<group>_<kind>` Lua in `argocd-cm` or in the Argo CD chart's
  values.
- An Application whose source is a Helm chart (`helm:` with `valuesObject`, `values` or
  `valueFiles`), including the multi-source chart-plus-values shape.
- Controller tuning in `argocd-cmd-params-cm` that changes ordering or timeouts.

## Rules

### App of apps

- An app-of-apps root is one Application whose source renders nothing but child `Application`
  objects; the docs' own layout is a chart with one template file per child.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/
- Treat push access to the root's repository as admin-level. The root can create Applications in
  arbitrary Projects, and a Project with access to the Argo CD namespace is effectively cluster
  admin; review every change to a child's `project` field.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/
- Pin a third-party child's `targetRevision` to a commit SHA or a chart version so the child only
  moves when the root's commit moves; `HEAD` or a branch name means an upstream push changes your
  cluster with no diff in your repository.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/
- Give each child the `resources-finalizer.argocd.argoproj.io` finalizer when deleting the root
  must delete the children's resources; without it the deletion is not cascading.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/
- Reach for an `ApplicationSet` before hand-writing a root when the children differ only by
  cluster or by directory; the docs recommend it over app-of-apps and it is bundled with Argo CD.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/ and
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/applicationset/
- If children are edited live for debugging, allow it explicitly with `ignoreDifferences` on
  `kind: Application` plus `RespectIgnoreDifferences=true`, and say in a comment which field and
  why. https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/

### Sync phases and waves

- The wave is an integer in the `argocd.argoproj.io/sync-wave` annotation, quoted as a string.
  Everything unannotated is wave 0, and negative waves run first.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- Ordering precedence is phase, then wave (lowest first), then kind, then name. Waves order
  resources **inside** a phase; they do not reorder PreSync against Sync.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- **A wave waits for health, not for apply.** Argo CD picks the first wave holding anything
  out-of-sync or unhealthy, applies it, and repeats until all phases and waves are in-sync **and
  healthy**. That is why an unhealthy resource in an early wave can stop the Application reaching
  Healthy at all. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- The health a wave waits on is the health Argo CD can compute. A kind with no built-in and no
  custom check contributes nothing, so a wave boundary drawn across such a kind orders nothing.
  Write the health check first, then the wave.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- The inter-wave delay is a fixed pause, not a gate: 2 s by default,
  `controller.sync.wave.delay.seconds` in `argocd-cmd-params-cm` or `ARGOCD_SYNC_WAVE_DELAY`.
  Never let a comment claim that the delay is what orders two resources.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/ and
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/argocd-cmd-params-cm-yaml/
- Pruning reverses the wave order: higher waves are pruned first, and a failed prune stops lower
  waves. A wave number is therefore a statement about teardown as well as rollout.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- PostSync runs only after a successful apply **and** all resources Healthy; PreSync failure stops
  the whole sync. Put a schema migration in PreSync and a smoke test in PostSync, never the
  reverse. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- Give every hook a `argocd.argoproj.io/hook-delete-policy` on purpose. With none set Argo CD
  assumes `BeforeHookCreation`, which keeps the last run's object around until the next sync.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- Hooks are applied with `kubectl apply`, not `create`, so a named hook that already exists is not
  re-run unless `BeforeHookCreation` deletes it first. Make every hook idempotent.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- Hooks do not run during a selective sync, so a selective sync is not a rehearsal of a full one.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/

### Health, and the child-Application check

Full rules in `rules/health-checks.md`. The two that decide whether an app-of-apps gate exists:

- The built-in health assessment of `argoproj.io/Application` was removed in Argo CD 1.8, so an
  app-of-apps orchestrated with sync waves has no gate at all until you restore one in
  `resource.customizations.health.argoproj.io_Application`.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- **The docs' restore snippet relays `obj.status.health.status` verbatim, which is weaker than a
  gate needs.** A gate-grade check requires all three of `status.sync.status == "Synced"`, relayed
  tree health `Healthy`, and `status.operationState.phase == "Succeeded"` (or no operation yet),
  and it must guard the nil status of a child that was just created.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/ and
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/

### Helm sources

- Precedence is `parameters > valuesObject > values > valueFiles > the chart's own values.yaml`,
  and with multiple `valueFiles` the last listed wins. Set a key in one place and know which.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- Prefer multiple sources (chart from the registry, values from git via `$values/...`) over
  vendoring a third-party chart, and keep the `sources` array to two or three entries; the docs
  call more than that an abuse of the feature.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/multiple_sources/
- If two sources produce the same group/kind/name/namespace the last one wins and Argo CD raises
  `RepeatedResourceWarning`. That is an override mechanism, not an accident to leave in place.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/multiple_sources/
- Helm hook annotations are mapped onto Argo CD hooks (`pre-install` and `pre-upgrade` to PreSync,
  `post-install` and `post-upgrade` to PostSync, `helm.sh/hook-weight` to `sync-wave`), but this
  is annotation compatibility, not identical lifecycle semantics: delete policies are still
  evaluated against Argo CD sync phases. `test-success`, `test-failure`, `pre-rollback` and
  `post-rollback` are not supported and are silently ignored.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- Defining any Argo CD hook in a chart makes Argo CD ignore **all** Helm hooks in it. Pick one
  annotation family per chart. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- Argo CD has no notion of install versus upgrade: every operation is a sync, so `pre-install` and
  `pre-upgrade` hooks both run every time.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- `helm.sh/hook: Skip` on a subchart's admission-webhook Job is the documented escape hatch when a
  chart's own hook wedges the sync.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- `source.helm.skipCrds: true` stops Argo CD installing the chart's `crds/` directory. Leaving it
  false is what lets a CRD-shipping chart sit in an earlier wave than its consumers.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/

### Sync options, diffing and bounding a held gate

- `ServerSideApply=true` runs `kubectl apply --server-side --force-conflicts`. Use it for
  resources too big for the 262144-byte last-applied annotation and for objects Argo CD only
  partly owns. `Replace=true` takes precedence over it.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-options/
- Server-side apply is settable per resource with
  `argocd.argoproj.io/sync-options: ServerSideApply=true`, and disable-able per resource with
  `ServerSideApply=false` under an app-level enable. Reach for the per-resource form whenever
  app-level SSA breaks a sibling resource in the same chart.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-options/
- `ignoreDifferences` entries carry a reason comment naming the controller or webhook that mutates
  the field. The documented causes are a mutating controller, a chart template such as
  `randAlphaNum`, or a field the API server drops; anything else is a manifest bug to fix rather
  than to ignore. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/diffing/
- Automated sync fires only when the Application is OutOfSync, only once per commit SHA plus
  parameters, and **never re-attempts a sync that already failed against the same SHA**. A
  transient failure therefore needs `syncPolicy.retry`, not patience.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/auto_sync/
- Give any Application that gates others a `syncPolicy.retry` block with `limit` and a `backoff`
  of `duration`, `factor` and `maxDuration`. The wait ladder is the backoff, capped by
  `maxDuration`, so compute the worst case before choosing the numbers.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/auto_sync/
- `retry` only fires on a **failed** operation. An operation that is merely never Healthy stays
  `Running` forever at the default `controller.sync.timeout.seconds: "0"`. Set that parameter to
  the cold-start budget plus margin so a held gate ends as a Failed operation naming the stuck
  child rather than hanging.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/argocd-cmd-params-cm-yaml/ and
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/auto_sync/

## Anti-patterns

- **Relaying `status.health.status` verbatim for a child Application.** The child reports Healthy
  while a PostSync hook still runs, the root starts the next wave, and every "wave N waits for
  wave N-1" comment in the repository becomes false without anything turning red.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- **A health Lua with no nil-status guard.** It aborts on a child that has no `status` yet, which
  is every child on a cold start. https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- **A wave boundary across a kind with no health check.** Nothing is waited for; the ordering that
  appears to work is holding by latency and breaks the first time the earlier step is slow.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- **Moving a resource into a later wave than a required volume or Secret consumer in an earlier
  one.** Once the gate genuinely holds this is not a wait, it is a deadlock: the later wave never
  starts because the earlier one can never be Healthy.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/
- **`targetRevision: main` or `HEAD` on a third-party chart or repo.** An upstream push changes
  the cluster with no commit in your repository to review or revert.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/cluster-bootstrapping/
- **Hand `kubectl apply` into a namespace an Application owns.** With `selfHeal` the controller
  reverts it, and without it the resource shows as a permanent diff nobody can explain.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/auto_sync/
- **Values keys the chart never renders.** Precedence makes them silently inert, so the setting
  reads as applied and is not. Prove each key exists at that chart version.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- **Mixing Argo CD hook annotations into a chart that has Helm hooks.** All the Helm hooks are
  ignored the moment one Argo hook exists.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- **One health Lua block past a couple hundred lines covering many kinds.** The docs say to
  duplicate per resource instead; split into per-domain values files.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- **Treating `Synced + Healthy` as done in a wait script.** It is exactly the window in which a
  PostSync hook is still running. Poll `status.operationState.phase` too.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/

## Verify

```bash
# 1. The manifests you are about to push match what is live. Exit 0 = no diff, 1 = diff, 2 = error.
argocd app diff <app> --local <dir> --local-repo-root <repo-root>

# 2. The triple that actually means "done" for one Application.
kubectl -n argocd get application <app> \
  -o jsonpath='{.status.sync.status} {.status.health.status} {.status.operationState.phase}'
# expect: Synced Healthy Succeeded

# 3. Every child of an app-of-apps root, same triple, one line each.
kubectl -n argocd get application -o \
  jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.sync.status}{"\t"}{.status.health.status}{"\t"}{.status.operationState.phase}{"\n"}{end}'

# 4. Run a health Lua against a fixture without touching the cluster. Keep one fixture per
#    branch of the script (no status, mid-sync, hooks-running, healthy, failed-op, degraded-tree)
#    and assert each one; deleting any clause of the Lua must turn exactly one fixture red.
kubectl -n argocd get cm argocd-cm -o yaml > /tmp/argocd-cm.yaml
argocd admin settings resource-overrides health ./fixture-app.yaml --argocd-cm-path /tmp/argocd-cm.yaml
# expect: STATUS: <one of Healthy|Progressing|Degraded|Suspended>  MESSAGE: <your message>

# 5. The ordering parameters the controller is really running with.
kubectl -n argocd get cm argocd-cmd-params-cm \
  -o jsonpath='{.data.controller\.sync\.timeout\.seconds} {.data.controller\.sync\.wave\.delay\.seconds}'
```

A new Application, a wave change, or anything the bootstrap Helm release renders is unverified
until a cold start: a warm cluster already holds the CRDs, Services and Secrets the ordering
depends on, so it can neither fail nor pass.
