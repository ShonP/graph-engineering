# Argo CD health checks, and the child-Application gate

Split out of `../SKILL.md` (house shape: keep a SKILL.md under about 250 lines). Same sources,
same fetch date (2026-09-10), Argo CD 3.5.2 docs at `/en/release-3.5/`.


- The built-in health assessment of `argoproj.io/Application` was removed in Argo CD 1.8. If you
  orchestrate an app-of-apps with sync waves you must restore it yourself in
  `resource.customizations.health.argoproj.io_Application`.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- **The docs' restore snippet relays `obj.status.health.status` verbatim, and that is weaker than
  a gate needs.** A child's own health is computed over its live, non-hook resources, so a child
  that is `Synced` and `Healthy` with a PostSync hook still running relays `Healthy` and the next
  wave starts. A gate-grade check requires all three: `status.sync.status == "Synced"`, the
  relayed tree health `Healthy`, and `status.operationState.phase == "Succeeded"` (or no operation
  yet). Anything else is `Progressing`, and a failed operation is `Degraded`.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/ (the snippet this
  strengthens) and https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-waves/ (PostSync
  runs after the resources are Healthy, which is what makes `Synced + Healthy` reachable while an
  operation is still running). Rung-1 corroboration: a platform measured all three leaks on a live
  3.5.2 cluster (mid-sync, hooks-running, failed-op) and every one of them relayed `Healthy`.
- Guard the nil status. A child the root has just created has no `status` key at all; a Lua that
  indexes `obj.status.sync` aborts on **every** child of a cold start.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- Return a message built from what you keyed on (`sync=... health=... operation=...`). The message
  is what the root's resource result and any waiting script print while the gate holds.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- A custom check returns exactly one of `Healthy`, `Progressing`, `Degraded`, `Suspended`; the
  default is `Progressing`. Use `observedGeneration` where the CRD sets it, or the health flaps
  while the controller is still reconciling.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- The Lua sandbox has the standard libraries disabled unless
  `resource.customizations.useOpenLibs.<group>_<kind>: true` is set. Do not reach for `string` or
  `os` without turning them on deliberately.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- Keep each check resource-specific. The docs say outright: avoid massive scripts handling
  multiple resources, duplicate the relevant parts instead. Split per kind or per domain values
  file rather than growing one block.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- Wildcards only work under the `resource.customizations` key, never under
  `resource.customizations.health.<group>_<kind>`, because a Kubernetes ConfigMap key cannot hold
  a `*`. https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
