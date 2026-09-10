---
name: kubectl
description: Use when touching Kubernetes manifests under manifests/**, k8s/** or any chart output, and whenever verifying a cluster by hand. Covers read-only-first workflow, dry runs, diffs, jsonpath assertions, namespaces, requests and limits, images and secrets, and who owns apply in a GitOps repo.
license: MIT
---

# kubectl

Sources (fetched 2026-09-10 with curl, all HTTP 200):

- https://kubernetes.io/docs/reference/kubectl/ - "Command line tool (kubectl) | Kubernetes"
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/ - "kubectl apply | Kubernetes"
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/ - "kubectl diff | Kubernetes"
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_delete/ - "kubectl delete | Kubernetes"
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/ - "kubectl kustomize | Kubernetes"
- https://kubernetes.io/docs/reference/kubectl/generated/kubectl_wait/ - "kubectl wait | Kubernetes"
- https://kubernetes.io/blog/2025/11/25/configuration-good-practices/ - "Kubernetes Configuration Good Practices | Kubernetes"
- https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/ - "Resource Management for Pods and Containers | Kubernetes"
- https://kubernetes.io/docs/concepts/containers/images/ - "Images | Kubernetes"
- https://kubernetes.io/docs/concepts/configuration/secret/ - "Secrets | Kubernetes"

Version note: `docs/concepts/configuration/overview/` now redirects (HTTP 301)
to the 2025-11-25 blog post above, which is a community article on
kubernetes.io rather than a reference page: treat it as guidance and prefer the
reference and concept pages for anything load bearing. Written against kubectl
1.35.8 (the version forge pins in `mise.toml`); the flags below were exercised
with client v1.36.4, embedded Kustomize v5.8.1.

## When to apply

- Any manifest under `manifests/**`, `k8s/**`, an overlay directory, or a chart's rendered output.
- Any imperative cluster operation during verification, debugging or QA.
- Writing a test script that asserts on cluster state.
- Deciding whether a change should be applied by hand at all (in a GitOps repo it should not).

## Rules

**Read-only first**

- Start with `get`, `describe`, `logs`, `events` and `diff`. `kubectl diff -f FILE`
  (or `-k DIR`) diffs the live object against what would be applied, and its
  exit status is contractual: 0 no differences, 1 differences found, greater
  than 1 kubectl or the diff tool failed.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/)
- `kubectl diff --show-secrets` is off by default and secret values are masked;
  do not turn it on to "just look", and never paste that output anywhere.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/)
- Before any write, dry run it. `--dry-run` takes `none`, `server` or `client`:
  `client` only prints the object that would be sent, `server` submits the
  request to the API server without persisting, so only `server` catches
  admission webhooks, defaulting and validation.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/)
- `kubectl delete` also takes `--dry-run=server`, and the docs warn that delete
  does no resource-version check, so a concurrent update is lost with the
  object. Dry run first, and prefer `-i/--interactive` or an explicit name over
  `--all`.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_delete/)

**Who owns apply**

- In a GitOps repo the reconciler owns `apply`. A hand `kubectl apply` in a
  namespace an Argo CD Application owns is drift you then have to revert.
  Evidence (rung 1, forge-platform 2026-09-10): `kubectl diff -k manifests/ntfy`
  against the live cluster exits 1 and the only difference is the removal of
  `argocd.argoproj.io/tracking-id`, because a workstation client-side apply
  would strip the annotation the controller wrote. Read with kubectl, write
  through git.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/,
  https://kubernetes.io/blog/2025/11/25/configuration-good-practices/)
- Manifests live in version control; the blog's phrasing is "Never apply
  manifest files directly from your desktop". The rollback path is a revert, not
  a second imperative command.
  (https://kubernetes.io/blog/2025/11/25/configuration-good-practices/)
- Where an apply is legitimate (a bootstrap step, a cluster the reconciler does
  not own), prefer `--server-side`: apply then runs in the API server and field
  ownership is tracked, with `--force-conflicts` as the deliberate override.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/)
- `--prune` is documented as alpha and incomplete ("Do not use unless you are
  aware of what the current state is"); let the reconciler prune.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/)

**Targeting**

- Always name the namespace. In-cluster, kubectl infers the namespace from the
  service account token, and `POD_NAMESPACE` overrides the default; outside a
  cluster it uses the current context. Explicit `-n/--namespace` overrides both,
  so a script that omits it acts on whatever the last `kubectl config
  use-context` left behind.
  (https://kubernetes.io/docs/reference/kubectl/)
- Use `kubectl api-resources` to check whether a kind is namespaced and which
  API version is current before writing the manifest; the good-practices page
  makes "use the latest stable API version" its first rule.
  (https://kubernetes.io/docs/reference/kubectl/,
  https://kubernetes.io/blog/2025/11/25/configuration-good-practices/)
- Select with labels, not name lists: `-l tier=frontend` for get and delete.
  Use the standard `app.kubernetes.io/*` labels so other tools understand the
  objects. (https://kubernetes.io/blog/2025/11/25/configuration-good-practices/)

**Assertions in scripts**

- Assert with `-o jsonpath=<template>` (or `-o json` piped to a parser), never
  by grepping human-readable output; the plain-text format is explicitly the
  human format and is free to change.
  (https://kubernetes.io/docs/reference/kubectl/)
- `kubectl wait` is the documented way to block, and a `sleep` is not. `--for`
  takes `create`, `delete`, `condition=<name>[=<value>]` or
  `jsonpath='{path}'[=value]`, so a non-condition field has a sanctioned form
  too: `kubectl wait --for=jsonpath='{.status.phase}'=Running pod/x`, or
  `--for=jsonpath='{.status.loadBalancer.ingress}' service/lb`. Repeat `--for`
  to require several at once (the reference's own example waits for
  `--for=condition=Ready --for=create`), and set `--timeout`.
  (https://kubernetes.io/docs/reference/kubectl/,
  https://kubernetes.io/docs/reference/kubectl/generated/kubectl_wait/)
- Build a kustomize directory with `kubectl kustomize DIR`, which needs no
  second binary, and pipe it into a dry-run apply for validation.
  (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_kustomize/)

**Workload content**

- Every container carries resource requests and limits. Requests drive
  scheduling and are reserved by the kubelet; cpu limits are enforced by
  throttling, memory limits by OOM kill, which the docs describe as reactive.
  A limit with no request makes Kubernetes copy the limit into the request.
  (https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- Pin images by tag plus digest, or by digest. The docs say to avoid `:latest`
  in production because you cannot tell what is running or roll back cleanly,
  and note that `imagePullPolicy` is set at creation and does not change when
  the tag later changes.
  (https://kubernetes.io/docs/concepts/containers/images/)
- Run workloads through a controller (Deployment, StatefulSet, Job), not naked
  Pods: a naked Pod dies with its node and nothing brings it back.
  (https://kubernetes.io/blog/2025/11/25/configuration-good-practices/)
- Avoid `hostPort` and `hostNetwork` unless you are building infrastructure;
  they pin Pods to nodes. Use `kubectl port-forward` for local access instead.
  (https://kubernetes.io/blog/2025/11/25/configuration-good-practices/)

**Secrets**

- A `Secret` manifest is base64, not encryption. The docs' caution is explicit:
  Secrets are stored unencrypted in etcd by default and anyone able to create a
  Pod in the namespace can read them. A plain Secret therefore never gets
  committed; encrypt it (see the `sops-age` skill) and keep RBAC least
  privilege. (https://kubernetes.io/docs/concepts/configuration/secret/)
- `stringData` exists so you do not hand-encode values; it does not make the
  file safe to commit.
  (https://kubernetes.io/docs/concepts/configuration/secret/)

## Anti-patterns

- `kubectl apply` by hand in a namespace a GitOps controller owns. Failure: the
  next reconcile reverts you, or worse, the controller adopts your object and
  the repo no longer describes the cluster.
- Writing without a dry run, or dry-running with `client` and believing it.
  Failure: admission webhooks, defaulting and validation are never exercised, so
  the error surfaces on the real apply.
- `kubectl delete --all` (or a bare `-l` selector) typed straight in. Failure:
  the blast radius is whatever the current context and namespace happen to be,
  and delete does no resource-version check, so concurrent updates vanish.
- Grepping `kubectl get` table output in a test. Failure: a column order or
  wording change breaks the assertion, or worse, passes it by accident. Use
  jsonpath.
- Omitting `-n` in a script. Failure: it works on the author's laptop and
  targets the wrong namespace in CI.
- Containers with no requests or limits. Failure: the scheduler cannot place
  the Pod sensibly and one noisy workload starves the node.
- `image: something:latest`. Failure: nobody can say what is running and a
  rollback has nothing to roll back to.
- Committing a plain `Secret` (or `stringData`) manifest. Failure: a
  credential in git history forever; route the file through `sops-age`.
- `kubectl edit` on a live object to "just fix it". Failure: an undocumented
  change that no diff, review or replay can reproduce.

## Verify

```bash
kubectl version --client                       # record client and embedded kustomize
kubectl kustomize <dir> | kubectl apply --dry-run=server -f -
kubectl diff -f <file>                         # 0 in sync, 1 drift, >1 error
kubectl get <kind> <name> -n <ns> -o jsonpath='{.status.phase}'; echo
```

Run on forge-platform, 2026-09-10, cluster up:

```
$ kubectl kustomize manifests/ntfy | kubectl apply --dry-run=server -f -
configmap/ntfy-config-kt78tfbb24 configured (server dry run)
service/ntfy configured (server dry run)
persistentvolumeclaim/ntfy configured (server dry run)
deployment.apps/ntfy configured (server dry run)
httproute.gateway.networking.k8s.io/ntfy configured (server dry run)

$ kubectl diff -k manifests/ntfy ; echo "exit=$?"
-    argocd.argoproj.io/tracking-id: ntfy:apps/Deployment:forge-obs/ntfy
exit=1
```

Expected: the dry run reports every object and persists nothing. The `diff`
exit of 1 here is the GitOps rule in action, not a manifest bug: the live
objects carry Argo CD's tracking annotation, which a workstation apply would
remove. Do not "fix" it by applying.
