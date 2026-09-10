---
name: helm
description: Use when authoring a Helm chart (Chart.yaml, templates, values.yaml, crds/) or consuming a third-party chart through values files or an Argo CD valuesObject. Covers pinning, proving a values key exists, CRDs, hooks and weights, server-side apply, and why a null in a valuesObject deletes nothing.
license: MIT
---

# Helm

Written for Helm **3.21.4** (`helm version` on the authoring machine reported
`v3.21.4`). Note the doc path: `helm.sh/docs/...` now serves the **Helm 4** docs (the pages
showed a `Version: 4.3.0` banner on 2026-09-10). Every rule below cites the `/docs/v3/` build,
which showed `Version: 3.22.0`, the same major line as 3.21.4.

Sources (fetched 2026-09-10, helm 3.21.4):
- https://helm.sh/docs/v3/topics/charts/ - "Charts | Helm" (banner: Version: 3.22.0)
- https://helm.sh/docs/v3/chart_best_practices/ - "Best Practices | Helm"
- https://helm.sh/docs/v3/chart_best_practices/values/ - "Values | Helm"
- https://helm.sh/docs/v3/chart_best_practices/labels/ - "Labels and Annotations | Helm"
- https://helm.sh/docs/v3/chart_best_practices/custom_resource_definitions/ - "Custom Resource Definitions | Helm"
- https://helm.sh/docs/v3/chart_best_practices/templates/ - "Templates | Helm"
- https://helm.sh/docs/v3/chart_best_practices/dependencies/ - "Dependencies | Helm"
- https://helm.sh/docs/v3/topics/charts_hooks/ - "Chart Hooks | Helm"
- https://helm.sh/docs/v3/chart_template_guide/values_files/ - "Values Files | Helm"
- https://helm.sh/docs/v3/helm/helm_lint/ - "helm lint | Helm"
- https://helm.sh/docs/v3/helm/helm_template/ - "helm template | Helm"
- https://helm.sh/docs/v3/helm/helm_show_values/ - "helm show values | Helm"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/ - "Helm - Argo CD - Declarative GitOps CD for Kubernetes"
- https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-options/ - "Sync Options - Argo CD - Declarative GitOps CD for Kubernetes"
- https://kubernetes.io/docs/reference/using-api/server-side-apply/ - "Server-Side Apply | Kubernetes"

## When to apply

- Authoring a chart: `Chart.yaml`, `templates/**`, `values.yaml`, `values.schema.json`, `crds/`.
- Consuming a third-party chart: a values file, a `--set` flag, or an Argo CD Application with
  `helm.valuesObject`, `helm.values` or `helm.valueFiles`.
- Chart hooks and hook weights, and what they become once Argo CD renders the chart.
- Deciding whether a release needs server-side apply.

## Rules

### Pinning and chart metadata

- `apiVersion`, `name` and `version` are required in `Chart.yaml`; `appVersion` is optional,
  informational, unrelated to `version`, and should be quoted so YAML does not read `1.0` as a
  float or `1234e10` as scientific notation. https://helm.sh/docs/v3/topics/charts/
- Pin a chart you consume to an exact version. The dependency best-practice page recommends a
  patch-level range (`~1.2.3`) for a chart's own `dependencies:`, which is a floor for reuse, not
  a licence to float a deployed release: for anything a cluster syncs unattended, name the exact
  version so an upstream release cannot arrive without a commit.
  https://helm.sh/docs/v3/chart_best_practices/dependencies/
- Version ranges never match pre-releases unless you spell one out (`~1.2.3-0`). A chart pinned to
  `~1.2.3` will not pick up `1.2.4-rc1`, which is usually what you want and always worth knowing.
  https://helm.sh/docs/v3/chart_best_practices/dependencies/
- Prefer `https://` repository URLs, or a registered repo alias; `file://` is a special case for
  fixed pipelines. https://helm.sh/docs/v3/chart_best_practices/dependencies/
- Set `kubeVersion` when the chart genuinely needs an API that only some clusters have; Helm
  validates the constraint at install. https://helm.sh/docs/v3/topics/charts/

### Values: prove the key exists

- **Every values key you set must exist in the chart's own `values.yaml` at that exact version.**
  Helm merges your values over the chart's defaults; a key the chart never reads is silently
  inert and reads in review as if it were applied. Prove it with
  `helm show values <repo>/<chart> --version <v>`, which prints exactly that file.
  https://helm.sh/docs/v3/helm/helm_show_values/ and
  https://helm.sh/docs/v3/chart_template_guide/values_files/
- Quote all strings in a values file and be explicit about types: `foo: false` is not
  `foo: "false"`, and a large integer can be coerced to scientific notation. Store awkward
  integers as strings and convert with `{{ int $value }}`.
  https://helm.sh/docs/v3/chart_best_practices/values/
- Favour flat over nested values, and maps over lists, so a consumer can express an override with
  `--set servers.foo.port=80` instead of a positional `servers[0].port`.
  https://helm.sh/docs/v3/chart_best_practices/values/
- Document every property in `values.yaml`, starting the comment with the property name; a
  `values.schema.json` turns that documentation into validation.
  https://helm.sh/docs/v3/chart_best_practices/values/ and https://helm.sh/docs/v3/topics/charts/

### The `null` trap

- In a **values file** or `--set`, setting a key to `null` deletes it from the merged values. That
  is the documented way to drop a chart default, for example
  `--set livenessProbe.httpGet=null`. https://helm.sh/docs/v3/chart_template_guide/values_files/
- In an **Argo CD `valuesObject`** that does not hold. The Argo CD docs are silent on `null`
  inside `valuesObject` (the Helm page documents precedence and the `valuesObject` key, and says
  nothing about deletion). Measured instead, rung 1, on a live cluster with kubectl 1.35.8 and
  Argo CD 3.5.2: `kubectl apply --dry-run=server` of an Application whose `valuesObject` held
  `dropme: null` and `nested.alsodrop: null` stored `{"keep":"yes","nested":{}}`. The null keys
  never reach the stored object, so Helm never sees a deletion and coalesces the chart default
  back in. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/ (the page that is
  silent) and https://helm.sh/docs/v3/chart_template_guide/values_files/ (the mechanism that
  would have applied)
- So: to remove a chart default from an Argo CD Application, use the chart's own switch
  (`enabled: false`, or a real value such as `127.0.0.1` or `0`). If the chart has no switch, do
  not pretend: leave the component out of the pipeline entirely and assert the absence (a closed
  port, a missing container) in a test.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- Argo CD's precedence is `parameters > valuesObject > values > valueFiles > the chart's
  values.yaml`, and among multiple `valueFiles` the last listed wins. Set a key once and know
  which layer owns it. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/

### CRDs

- A CRD declaration must be registered before any resource of its kind is applied, and Helm 3's
  answer is the `crds/` directory: files there are **not templated**, are installed by default,
  and are skipped with a warning if the CRD already exists.
  https://helm.sh/docs/v3/chart_best_practices/custom_resource_definitions/
- Know what `crds/` costs: Helm will not upgrade or delete those CRDs, and `--dry-run` does not
  support them, so a chart with `crds/` cannot be fully dry-run against a cluster that lacks the
  CRD. https://helm.sh/docs/v3/chart_best_practices/custom_resource_definitions/
- Putting CRDs under `templates/` instead is a deliberate choice with a stated reason, not a
  slip. It buys templating and upgrade, and it is what a GitOps controller needs when the CRDs
  must be an ordinary, ordered, prunable resource; Argo CD's `source.helm.skipCrds` controls only
  the `crds/` directory. Write the reason in a comment next to the choice.
  https://helm.sh/docs/v3/chart_best_practices/custom_resource_definitions/ and
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- A chart that ships CRDs belongs in an earlier ordering step than the charts whose resources use
  them, whatever the ordering mechanism is; registration "sometimes takes a few seconds".
  https://helm.sh/docs/v3/chart_best_practices/custom_resource_definitions/

### Templates, labels and hooks

- One resource per template file, dashed file names that name the kind (`foo-pod.yaml`), `.tpl`
  only for files that render no content.
  https://helm.sh/docs/v3/chart_best_practices/templates/
- Defined templates are global across a chart and all its subcharts, so namespace every
  `{{ define }}` name (`nginx.fullname`, never `fullname`) and keep them in `_helpers.tpl`.
  https://helm.sh/docs/v3/chart_best_practices/templates/
- Carry the recommended labels: `app.kubernetes.io/name`, `helm.sh/chart` as
  `{{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}`, `app.kubernetes.io/managed-by` as
  `{{ .Release.Service }}`, `app.kubernetes.io/instance` as `{{ .Release.Name }}`. Metadata used
  for querying is a label; everything else is an annotation, and Helm hooks are always
  annotations. https://helm.sh/docs/v3/chart_best_practices/labels/
- Hook weights are strings, may be negative, and sort ascending within a kind. Hooks with no
  `helm.sh/hook-delete-policy` get `before-hook-creation`, and resources a hook creates are not
  removed by `helm uninstall` unless a delete policy or a Job TTL says so.
  https://helm.sh/docs/v3/topics/charts_hooks/
- Under Argo CD a Helm hook becomes an Argo hook by annotation mapping only: `pre-install` and
  `pre-upgrade` become PreSync, `post-install` and `post-upgrade` become PostSync,
  `helm.sh/hook-weight` becomes `sync-wave`, and `test`, `pre-rollback` and `post-rollback` are
  not supported and are ignored. Delete policies are then evaluated on Argo CD's sync phases, not
  Helm's hook events. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- `crd-install` was removed in Helm 3; do not carry it forward from an old chart.
  https://helm.sh/docs/v3/topics/charts_hooks/

### Server-side apply

- Reach for server-side apply when the rendered object exceeds the 262144-byte last-applied
  annotation, when Argo CD only partly owns the object, or when you want field ownership tracked
  rather than a last-applied blob. In Argo CD that is `ServerSideApply=true`, which runs
  `kubectl apply --server-side --force-conflicts`.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-options/
- **Prefer the per-resource annotation over the application-level flag when only one rendered
  object needs it.** `argocd.argoproj.io/sync-options: ServerSideApply=true` on that resource, or
  `ServerSideApply=false` on a resource that must be excluded from an app-level enable.
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-options/
- The reason that matters: under server-side apply a field marked `atomic` (`x-kubernetes-list-type:
  atomic`, `x-kubernetes-map-type: atomic`) is replaced whole and owned by a single manager, and
  the atomic list type is recursive. A chart that renders such a field where the API server also
  fills in defaults (a StatefulSet's `volumeClaimTemplates` is the classic one) comes back with
  those defaults as a permanent diff, and the release never reaches Synced. Turning app-level SSA
  on for one Secret can therefore wedge an unrelated StatefulSet in the same chart.
  https://kubernetes.io/docs/reference/using-api/server-side-apply/
- `Replace=true` takes precedence over `ServerSideApply=true`; setting both is a silent no-op for
  the second. https://argo-cd.readthedocs.io/en/release-3.5/user-guide/sync-options/

### Secrets

- `values.yaml` and every values file is ordinary chart content that ships with the chart and is
  committed to git. Nothing in it is secret; route credentials to the repository's secret
  tooling (SOPS and age, an External Secrets provider, a pre-created Secret referenced by name)
  and pass only the Secret's name through values. https://helm.sh/docs/v3/topics/charts/

## Anti-patterns

- **`latest`, a branch, or an unpinned chart version.** An upstream release changes the cluster
  with no commit to review. https://helm.sh/docs/v3/chart_best_practices/dependencies/
- **A values key the chart does not read.** Precedence makes it inert, the manifest reads as if
  the setting is applied, and the review passes.
  https://helm.sh/docs/v3/helm/helm_show_values/
- **A `null` in an Argo CD `valuesObject` meant to remove a chart default.** The API server drops
  the key before Helm sees it, the default is still in force, and the manifest reads as if the
  component is off (measured; see the null trap above).
  https://argo-cd.readthedocs.io/en/release-3.5/user-guide/helm/
- **Application-level `ServerSideApply=true` on a chart that also renders a StatefulSet with
  `volumeClaimTemplates`.** The atomic field returns the API server's defaults as a permanent
  diff and the Application never syncs. Use the per-resource annotation.
  https://kubernetes.io/docs/reference/using-api/server-side-apply/
- **A credential in `values.yaml`.** It is chart content, in git, in every rendered
  last-applied annotation. https://helm.sh/docs/v3/topics/charts/
- **An un-namespaced `{{ define }}`.** Defined templates are global across subcharts, so
  `fullname` collides silently with a dependency's.
  https://helm.sh/docs/v3/chart_best_practices/templates/
- **A `kind` hidden behind an undocumented conditional.** Nobody reading the values can tell
  whether the resource exists; document the property or drop the conditional.
  https://helm.sh/docs/v3/chart_best_practices/values/
- **Assuming `helm --dry-run` covers a chart's `crds/`.** It does not, so a green dry run says
  nothing about the CRDs.
  https://helm.sh/docs/v3/chart_best_practices/custom_resource_definitions/

## Verify

```bash
# 1. Lint the chart. [ERROR] fails installation, [WARNING] breaks convention.
helm lint <chart>
# expect: 1 chart(s) linted, 0 chart(s) failed

# 2. Render, then let the API server judge the result (catches schema and admission errors
#    that helm lint cannot see).
helm template <release> <chart> -f values.yaml | kubectl apply --dry-run=server -f -

# 3. Prove every values key you set exists in the chart at that exact version.
helm show values <repo>/<chart> --version <v> > /tmp/chart-values.yaml
# Use has(): a bare `yq '.a.b'` prints `null` for BOTH "key absent" and "key present and null",
# and so does `yq '.a.b // "MISSING"'`, because yq's `//` treats an explicit null as falsy.
# Only has() separates the two, and the difference is the whole point: an absent key is your
# typo, a present-and-null key is a real chart default you are allowed to set.
yq '.<parent> | has("<leaf>")' /tmp/chart-values.yaml   # expect: true
yq '.<the.key.you.set> // "MISSING"' /tmp/chart-values.yaml  # MISSING = absent OR null
# Measured on loki 18.12.1, which has `global.imageRegistry: null` and no `global.nosuchKey`:
#   yq '.global.imageRegistry'                 -> null       yq '.global.nosuchKey'  -> null
#   yq '.global.imageRegistry // "MISSING"'    -> MISSING     ... // "MISSING"       -> MISSING
#   yq '.global | has("imageRegistry")'        -> true        ... has("nosuchKey")   -> false
# For an Argo CD Application, read the keys straight out of the manifest:
yq '.spec.source.helm.valuesObject | keys' <app>.yaml

# 4. Prove a null in a valuesObject is dropped before Helm sees it (run once per cluster; this
#    is a dry run and writes nothing).
kubectl apply --dry-run=server -f <app-with-a-null>.yaml \
  -o jsonpath='{.spec.source.helm.valuesObject}'
# expect: the null-valued keys are absent from the output

# 5. Render one template only, when hunting a single resource.
helm template <release> <chart> -f values.yaml --show-only templates/<file>.yaml
```
