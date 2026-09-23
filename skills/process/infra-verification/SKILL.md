---
name: infra-verification
description: Use when a change touches Kubernetes manifests, Helm charts, kustomize overlays, Argo CD applications or other GitOps config - the render, validate, policy, diff, ephemeral-apply, smoke and rollback recipe that proves an infra change before merge, and the safety rules that keep it off any cluster the run did not create.
---

# Infra verification

An infra diff is not reviewed by reading YAML. It is rendered the way Argo CD
renders it, validated against schemas, diffed against what the base branch
renders, applied to a cluster the run created and throws away, and
smoke-tested there. This skill is that recipe. The stack competencies (`helm`,
`kustomize`, `argocd`, `kubectl`, `cloudnativepg`, `envoy-gateway`) say how to
write the change; this says how to prove it.

Versions this was written and spiked against (2026-09-23): helm v4.2.4,
kubeconform v0.8.0 (release binary), kind v0.32.0 installed. conftest v0.69.0
and kube-linter v0.8.3 are current upstream but were not installed or run here.

## Safety first

- **The run owns its kubeconfig.** Every cluster command passes
  `--kubeconfig "$REPO_ROOT/.graph/<run>/kubeconfig"` as a flag - an absolute
  path, because step 7 works from a scratch worktree and tool shells drop
  exported variables between calls - kind: `kind create cluster --name
  ge-${GRAPH_RUN_ID:?} --kubeconfig "$REPO_ROOT/.graph/<run>/kubeconfig" --wait 120s`; k3d:
  `--kubeconfig-update-default=false`, then `k3d kubeconfig get` into that
  file. The developer's `~/.kube/config` and current-context are never read or
  changed, so their shell keeps pointing at their own cluster and two runs
  never fight over a context.
- **Never touch a cluster the run did not create.** The run records the cluster
  name in the ledger when `create` succeeds; every later command passes
  `--kubeconfig` and `--context` for that cluster, and `delete` names only it.
  A kubeconfig or context from anywhere else - the developer's k3d/kind,
  staging, production - is never used, not even for a read.
- Secrets: render with the repo's non-secret values; never decrypt SOPS files
  into the run directory (`sops-age`).

## Static-only mode

When the profile's `infra.cluster` is empty - the owner chose no throwaway
cluster, or there is no disk for one (a kind node image is about 1 GB) - run
steps 1-4 and 7's render, mark steps 5, 6 and 8 `SKIPPED (static-only:
<reason>)`, and report `PASS (static-only)` if everything that ran passed. That
is an honest pass for what was checked, not `BLOCKED`: nothing is missing that
the profile promised. The merge gate shows it as static-only, and
`--auto-merge` does not accept it. `BLOCKED` is for a cluster that is
configured and failed to come up.

## The recipe

Run from the repo root. Everything goes under `.graph/<run>/qa/infra/`, **one
file per Application or overlay** - `rendered/<app>.yaml`, `base/<app>.yaml`,
`<app>.diff` - so a second chart never overwrites the first. Each step's
command and output are evidence.

| Step | Command | Pass |
| --- | --- | --- |
| 1. Render | For each Argo CD Application whose source the diff touches, render it **as Argo does**: `helm lint <chart> -f <values>...`, then `helm template <releaseName or app name> <chart> --namespace <destination.namespace> --include-crds -f <each helm.valueFiles> [--set-file / valuesObject as a -f file] > rendered/<app>.yaml` (Argo includes CRDs unless the Application sets `skipCrds`); `kustomize build <overlay> > rendered/<app>.yaml` for overlays. The profile's `infra.render` overrides this when set, with `${APP}` and `${OUT}` substituted per app | exit 0; object count as expected |
| 2. Validate | per file: `kubeconform -strict -summary -schema-location default -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' rendered/<app>.yaml` | `Invalid: 0, Errors: 0` |
| 3. Policy | per file: the profile's `infra.policy` with `${RENDERED}` set to the file (e.g. `conftest test ${RENDERED} -p policy/`); `kube-linter lint ${RENDERED}` when it is configured | exit 0, or each failure answered |
| 4. Diff | render the **merge base** the same way from a scratch `git worktree` into `base/<app>.yaml`; `diff -u base/<app>.yaml rendered/<app>.yaml > <app>.diff` | each diff shows exactly the intended change; all of them go in the PR (`definition-of-done`) |
| 5. Ephemeral apply | `infra.cluster.create`, then in order: (a) `infra.prereqs` - the operators and CRDs the rendered CRs need (Argo CD, CNPG, Envoy Gateway, cert-manager...), each pinned; (b) the `Namespace` objects the resources name (`kubectl create namespace` for any that `helm template` did not emit); (c) the rendered `CustomResourceDefinition`s first, then `kubectl wait --for=condition=Established crd/<name>`; (d) everything else with `kubectl apply --server-side`; (e) `kubectl rollout status` / `kubectl wait` on what changed | resources accepted, and the ones whose controller is present become ready within the budget |
| 6. Smoke | `bru run --tags smoke` against the ephemeral stack when it serves an API (`api-contract`); PromQL against its Prometheus when the change is an alert or rule (`promql`) | green, output captured |
| 7. Rollback | render the change reverted (`git revert --no-commit` in a scratch worktree, then steps 1-2) and, where the cluster exists, apply it and watch it converge | the revert renders valid and converges |
| 8. Teardown | `infra.cluster.delete`, always, pass or fail; delete `.graph/<run>/kubeconfig` | cluster gone |

A CR whose operator is not in `infra.prereqs` is still validated in step 2 but
cannot be proven live: the API server accepts it and nothing reconciles it.
List those kinds as `SKIPPED (no controller in prereqs)` rather than calling an
accepted object a working one.

Why the CRD catalog in step 2: kubeconform knows only core Kubernetes schemas.
Spiked: an Argo CD `Application` without the catalog is an **error** (exit 1,
"could not find schema"); with `-ignore-missing-schemas` it is **skipped**
(exit 0) - silently unvalidated, which in a GitOps repo means most of the diff.
With the datree CRDs-catalog location it is actually validated: a spec missing
`destination` and `project` failed (exit 1), a complete one passed (exit 0).
Use `-ignore-missing-schemas` only for a kind the catalog lacks, and name each
such kind in the report.

Spiked 2026-09-23: `helm create` chart, `helm lint` clean, 4 objects rendered,
kubeconform `Valid: 4` exit 0; the same chart with `containerPort` quoted to a
string failed `got string, want integer` exit 1. The review round's spike on
the same helm: a chart with a `crds/` file renders 0 CRDs without
`--include-crds` and 1 with it, and without `--namespace` no resource carries
a namespace - hence both flags in step 1.

## Anti-patterns

- `kubectl diff` or `argocd app diff` against a shared cluster "because it is
  read-only". Failure: it needs credentials to a cluster the run should never
  hold, and the next command in the same shell is an apply.
- `kind create cluster` without `--kubeconfig`. Failure: the developer's
  current-context silently switches to the throwaway cluster, and after
  teardown it is unset.
- `-ignore-missing-schemas` as a default. Failure: every CRD - Applications,
  HTTPRoutes, Clusters - passes unvalidated.
- Rendering with the chart's default values, without `--include-crds`, or
  without the destination namespace. Failure: the validated output is not what
  Argo will deploy.
- "Rollback: revert the commit" with no render of the revert. Failure: the
  revert conflicts or renders invalid at 2am.
