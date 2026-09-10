---
name: kustomize
description: Use when a directory holds a kustomization.yaml, when building bases and overlays, patching upstream manifests, or generating ConfigMaps and Secrets. Covers resources, patches, labels, namespace, generators and the hash-suffix trade-off, and how Argo CD renders a kustomize directory.
license: MIT
---

# kustomize

Sources (fetched 2026-09-10 with curl, all HTTP 200):

- https://kustomize.io/ - "Kustomize - Kubernetes native configuration management"
- https://kubectl.docs.kubernetes.io/references/kustomize/ - "Kustomize | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/ - "The Kustomization File | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/ - "patches | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/configmapgenerator/ - "configMapGenerator | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/secretgenerator/ - "secretGenerator | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/labels/ - "labels | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/commonlabels/ - "commonLabels | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/namespace/ - "namespace | SIG CLI"
- https://kubectl.docs.kubernetes.io/references/kustomize/cmd/build/ - "kustomize build | SIG CLI"
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/ - "kubectl kustomize | Kubernetes"

Version note: kustomize ships both as a standalone binary and inside kubectl.
forge-platform pins only `kubectl = "1.35.8"` in `mise.toml` and no standalone
`kustomize`, so `kubectl kustomize <dir>` and `kubectl apply -k <dir>` are the
house commands; the run below used client v1.36.4 with embedded Kustomize
v5.8.1. Some SIG CLI reference pages are old (the group index was last modified
2020-09-23); the per-field pages under `kustomization/` are the current ones and
are what the rules cite.

## When to apply

- Any directory holding a `kustomization.yaml`, and any base or overlay under it.
- Patching a third-party manifest set you do not want to fork.
- Generating ConfigMaps or Secrets from files or literals.
- An Argo CD Application whose `source.path` is a kustomize directory.

## Rules

**Shape**

- A kustomization is a KRM object: `apiVersion: kustomize.config.k8s.io/v1beta1`,
  `kind: Kustomization`, and, underneath, four ordered lists (`resources`,
  `generators`, `transformers`, `validators`). Order within each list is
  respected. Everything else (`labels`, `namePrefix`, `patches`) is shorthand
  for a transformer.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/)
- `resources` entries are either a path to a YAML file or a directory (local or
  a remote git repo) that itself holds a `kustomization.yaml`; the latter is
  built recursively and injected in order. That is the base and overlay
  relationship, and it is the only one: an overlay lists `../base` under
  `resources` and adds patches.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/)
- List every resource explicitly. There is no directory glob semantics to lean
  on, and a file nobody lists is a file nobody deploys.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/)
- Keep each kustomization rooted: the build default is
  `--load-restrictor LoadRestrictionsRootOnly`, and relaxing it to
  `LoadRestrictionsNone` "breaks the relocatability of the kustomization".
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/)

**Patches**

- Patch with the `patches` field. Each entry is a strategic merge patch or a
  JSON6902 patch, given as `path:` (a file) or `patch:` (inline), and each
  selects targets by `group`, `version`, `kind`, `name`, `namespace`,
  `labelSelector` and `annotationSelector`; a resource must match every field
  given.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/)
- Prefer a strategic merge patch for built-in kinds and JSON6902 for custom
  resources: strategic merge on a CRD may need extra `openapi` configuration to
  learn the merge key or that a list merges rather than replaces, while JSON6902
  behaves the same for both.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/)
- `target.name` and `target.namespace` are anchored regular expressions
  (`myapp` means `^myapp$`), so a name pattern such as `deploy.*` hits more
  than you may intend. Be specific.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/)
- Renaming or re-kinding through a patch needs the explicit
  `options.allowNameChange` or `options.allowKindChange`; both default to false.
  If you find yourself reaching for them, ask whether the base is wrong.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/)
- A patch should carry only the fields it changes. A patch that restates a whole
  resource is a fork with extra steps, and it silently stops tracking the base.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/)

**Labels and namespace**

- Use `labels:` with explicit `includeSelectors`, `includeTemplates` and
  `includeVolumeClaimTemplates` flags (all false by default), not
  `commonLabels`. `commonLabels` was deprecated in kustomize v5.0.0, always adds
  selectors, and will not exist in the `kustomize.config.k8s.io/v1`
  Kustomization API; `kustomize edit fix` converts it.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/labels/,
  https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/commonlabels/)
- Never change selectors on a resource that is already live. Both pages say it
  outright: selectors for Deployments and Services should not change once
  applied, and flipping `includeSelectors` to true on live resources "could
  result in failures".
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/labels/,
  https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/commonlabels/)
- `namespace:` belongs at the overlay and overrides any namespace already set on
  a resource, so a base that hardcodes a namespace is a trap for the second
  consumer. Leave the base namespace-free.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/namespace/)

**Generators**

- `configMapGenerator` creates one ConfigMap per entry, from `files`, `envs` or
  `literals`, and each entry takes `behavior: create|replace|merge` so an
  overlay can modify or replace the parent's map.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/configmapgenerator/)
- Keep the name hash suffix on. It is what makes an edit to the generated
  content roll the workloads that mount it, because kustomize rewrites the
  references. Set `options.disableNameSuffixHash: true` only where something
  external looks the ConfigMap up by a fixed name, and write the reason in a
  comment next to it.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/configmapgenerator/)
- The `disableNameSuffixHash` boolean does not compose: a global
  `generatorOptions.disableNameSuffixHash: true` "will trump any attempt to
  locally override it". Decide it per kustomization, not globally and then
  per entry.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/configmapgenerator/)
- Generator labels and annotations set per entry under `options` are not
  overwritten by the file-level `generatorOptions`.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/configmapgenerator/)
- `secretGenerator` "works like the configMapGenerator" and reads its input from
  files, envs or literals in the repo, so the generated Secret is only as secret
  as those inputs. Encrypted material goes through `sops-age`; a plaintext
  `secret/tls.key` next to the kustomization is a committed credential.
  (https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/secretgenerator/)

**Rendering and GitOps**

- `kustomize build` (or `kubectl kustomize DIR`) is the one command that
  hydrates a kustomization into the resource set; `DIR` must contain a
  `kustomization.yaml` and may be a git URL with a path suffix.
  (https://kubectl.docs.kubernetes.io/references/kustomize/cmd/build/,
  https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/)
- Kustomize is native to kubectl (`-k`) and every artifact it consumes or emits
  is plain YAML that can be validated as such. There is no rendered output to
  keep in the repo.
  (https://kustomize.io/)
- Argo CD renders a kustomize directory itself; the Application just points at
  it. Evidence (rung 1, forge-platform 2026-09-10):
  `argocd/apps/ntfy.yaml` has `source.path: manifests/ntfy` with no `plugin` or
  `kustomize` block, and `manifests/ntfy/kustomization.yaml` supplies the
  namespace and a hashed `configMapGenerator`. So the reconciler, not a CI step,
  is what runs the build. (https://kustomize.io/)
- The `--enable-helm` flag lets kustomize inflate a chart. Reach for it only when
  the platform running the build enables it too; otherwise the directory builds
  on your laptop and fails in the reconciler.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/)

## Anti-patterns

- Committing the output of `kustomize build`. Failure: two sources of truth, and
  the applied one is the one nobody reviewed.
- `commonLabels` in a new kustomization. Failure: it always injects selectors,
  it is deprecated since v5.0.0, and it is gone in the v1 API; on a live
  Deployment the selector change fails the apply.
- Flipping `includeSelectors: true` on an overlay that is already deployed.
  Failure: the Deployment's selector is immutable in practice, so the sync
  breaks until someone deletes the workload.
- An overlay that re-declares a whole resource instead of patching fields.
  Failure: base changes silently stop reaching that environment.
- `disableNameSuffixHash: true` set because "the pod did not restart". Failure:
  you removed the mechanism that rolls the pod; fix the reference, not the hash.
- A base that pins `namespace:` or environment-specific values. Failure: the
  second overlay has to override rather than add, and the diff stops being
  readable.
- A patch target of `name: .*` or a bare `kind:` with no other selector.
  Failure: the patch lands on resources nobody was thinking about, including
  ones added later.
- `LoadRestrictionsNone` to reach a file one directory up. Failure: the
  kustomization is no longer relocatable and the remote-base build breaks.

## Verify

```bash
kubectl version --client                          # note the embedded Kustomize version
kubectl kustomize <dir>                           # exit 0, full rendered set on stdout
kubectl kustomize <dir> | kubectl apply --dry-run=server -f -
kubectl diff -k <dir>                             # 0 in sync, 1 drift, >1 error
```

Run on forge-platform, 2026-09-10:

```
$ kubectl version --client
Client Version: v1.36.4
Kustomize Version: v5.8.1

$ kubectl kustomize manifests/ntfy | kubectl apply --dry-run=server -f -
configmap/ntfy-config-kt78tfbb24 configured (server dry run)
service/ntfy configured (server dry run)
persistentvolumeclaim/ntfy configured (server dry run)
deployment.apps/ntfy configured (server dry run)
httproute.gateway.networking.k8s.io/ntfy configured (server dry run)
```

Expected: the generated ConfigMap carries its hash suffix
(`ntfy-config-kt78tfbb24`) and the Deployment that mounts it is rewritten to
match, which is the proof the generator is wired correctly. A build that names
the ConfigMap without a suffix means the hash was disabled somewhere.
