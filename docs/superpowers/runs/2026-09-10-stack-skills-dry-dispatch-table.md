# Stack skills dry dispatch: the per-file resolution table

Companion to
[`2026-09-10-stack-skills-dry-dispatch.md`](2026-09-10-stack-skills-dry-dispatch.md).
Split out so that both files stay under the 250-line house limit. Everything
here is the output of the matcher described in that file, run on 2026-09-10
against `templates/graph-profile.yaml` at plugin 0.8.0.

## Table 1: sample file, rows matched, REQUIRED list per role

Names are resolved to paths in table 2. The list per role is the union of the
matched rows' entries for that role plus the `always` block for that role, in
first-seen order, which is the order the spine writes into a dispatch.

| File | Rows matched | impl | review | qa |
| --- | --- | --- | --- | --- |
| `argocd/root.yaml` | `argocd/**/*.{yaml,yml}` | `argocd`, `helm`, `kubectl`, `architecture-resilience-rules`, `prior-art`, `review-testing-rules` | `argocd`, `helm`, `review-protocol`, `security-review`, `privacy-review` | `kubectl` |
| `argocd/apps/loki.yaml` | `argocd/**/*.{yaml,yml}` | `argocd`, `helm`, `kubectl`, `architecture-resilience-rules`, `prior-art`, `review-testing-rules` | `argocd`, `helm`, `review-protocol`, `security-review`, `privacy-review` | `kubectl` |
| `argocd/values-health-data.yaml` | `argocd/**/*.{yaml,yml}` | `argocd`, `helm`, `kubectl`, `architecture-resilience-rules`, `prior-art`, `review-testing-rules` | `argocd`, `helm`, `review-protocol`, `security-review`, `privacy-review` | `kubectl` |
| `manifests/forge-pg/cluster.yaml` | `manifests/**`<br>`**/*-pg/**` | `kubectl`, `kustomize`, `cloudnativepg`, `prior-art`, `review-testing-rules` | `kubectl`, `cloudnativepg`, `review-protocol`, `security-review`, `privacy-review` | `kubectl` |
| `manifests/forge-pg-backup/scheduledbackup.yaml` | `manifests/**`<br>`**/*-pg-*/**` | `kubectl`, `kustomize`, `cloudnativepg`, `prior-art`, `review-testing-rules` | `kubectl`, `cloudnativepg`, `review-protocol`, `security-review`, `privacy-review` | `kubectl` |
| `manifests/gateway-auth/securitypolicy-bugsink.yaml` | `manifests/**`<br>`**/{httproute,securitypolicy,backendtlspolicy,backendtrafficpolicy,clienttrafficpolicy,gateway,gatewayclass,referencegrant}*.{yaml,yml}`<br>`**/{gateway,gateway-*}/**` | `kubectl`, `kustomize`, `envoy-gateway`, `prior-art`, `review-testing-rules` | `kubectl`, `envoy-gateway`, `security-review`, `review-protocol`, `privacy-review` | `kubectl` |
| `manifests/gateway-exemptions/httproute-gatus-health.yaml` | `manifests/**`<br>`**/{httproute,securitypolicy,backendtlspolicy,backendtrafficpolicy,clienttrafficpolicy,gateway,gatewayclass,referencegrant}*.{yaml,yml}`<br>`**/{gateway,gateway-*}/**` | `kubectl`, `kustomize`, `envoy-gateway`, `prior-art`, `review-testing-rules` | `kubectl`, `envoy-gateway`, `security-review`, `review-protocol`, `privacy-review` | `kubectl` |
| `manifests/forge-secrets/secrets/nats-auth.enc.yaml` | `manifests/**`<br>`{.sops.yaml,**/*.enc.yaml,**/*.enc.yml}` | `kubectl`, `kustomize`, `sops-age`, `prior-art`, `review-testing-rules` | `kubectl`, `sops-age`, `security-review`, `review-protocol`, `privacy-review` | `kubectl` |
| `.sops.yaml` | `{.sops.yaml,**/*.enc.yaml,**/*.enc.yml}` | `sops-age`, `prior-art`, `review-testing-rules` | `sops-age`, `security-review`, `review-protocol`, `privacy-review` | (none) |
| `manifests/ntfy/kustomization.yaml` | `manifests/**`<br>`**/kustomization.{yaml,yml}` | `kubectl`, `kustomize`, `prior-art`, `review-testing-rules` | `kubectl`, `kustomize`, `review-protocol`, `security-review`, `privacy-review` | `kubectl` |
| `observability/kustomization.yaml` | `**/kustomization.{yaml,yml}`<br>`{observability/**,**/dashboards/**/*.json,**/*rule*.{yaml,yml}}` | `kustomize`, `promql`, `loki`, `tempo`, `prior-art`, `review-testing-rules` | `kustomize`, `promql`, `loki`, `tempo`, `review-protocol`, `security-review`, `privacy-review` | `promql`, `loki`, `tempo` |
| `observability/dashboards/cnpg-cluster.json` | `{observability/**,**/dashboards/**/*.json,**/*rule*.{yaml,yml}}` | `promql`, `loki`, `tempo`, `prior-art`, `review-testing-rules` | `promql`, `loki`, `tempo`, `review-protocol`, `security-review`, `privacy-review` | `promql`, `loki`, `tempo` |
| `tests/81-cnpg.sh` | (none, `always` only) | `prior-art`, `review-testing-rules` | `review-protocol`, `security-review`, `privacy-review` | (none) |
| `docs/HANDOFF.md` | (none, `always` only) | `prior-art`, `review-testing-rules` | `review-protocol`, `security-review`, `privacy-review` | (none) |
| `charts/temporal/Chart.yaml` | `**/Chart.yaml` | `helm`, `prior-art`, `review-testing-rules` | `helm`, `review-protocol`, `security-review`, `privacy-review` | (none) |
| `manifests/temporal/httproute.yaml` | `manifests/**`<br>`**/{httproute,securitypolicy,backendtlspolicy,backendtrafficpolicy,clienttrafficpolicy,gateway,gatewayclass,referencegrant}*.{yaml,yml}` | `kubectl`, `kustomize`, `envoy-gateway`, `prior-art`, `review-testing-rules` | `kubectl`, `envoy-gateway`, `security-review`, `review-protocol`, `privacy-review` | `kubectl` |
| `manifests/ai-gateway/backend-foundry.yaml` | `manifests/**`<br>`**/{ai-gateway,agent-router,llm-gateway}/**` | `kubectl`, `kustomize`, `agent-router`, `envoy-gateway`, `prior-art`, `review-testing-rules` | `kubectl`, `agent-router`, `security-review`, `review-protocol`, `privacy-review` | `kubectl` |
| `apps/codec-server/pyproject.toml` | `**/{pyproject.toml,uv.lock,.python-version}` | `uv`, `prior-art`, `review-testing-rules` | `uv`, `review-protocol`, `security-review`, `privacy-review` | (none) |
| `apps/codec-server/src/codec/workflows/encode.py` | `**/*.py`<br>`**/{workflows,activities}/**/*.py` | `uv`, `pydantic`, `pydantic-house-rules`, `fastapi`, `backend-rules`, `architecture-resilience-rules`, `temporal-developer`, `prior-art`, `review-testing-rules` | `pydantic`, `pydantic-house-rules`, `fastapi`, `backend-rules`, `architecture-resilience-rules`, `temporal-developer`, `review-protocol`, `security-review`, `privacy-review` | (none) |
| `apps/codec-server/src/codec/agents/router.py` | `**/*.py`<br>`**/agents/**/*.py` | `uv`, `pydantic`, `pydantic-house-rules`, `fastapi`, `backend-rules`, `architecture-resilience-rules`, `microsoft-agent-framework`, `building-pydantic-ai-agents`, `agent-workflow-rules`, `prior-art`, `review-testing-rules` | `pydantic`, `pydantic-house-rules`, `fastapi`, `backend-rules`, `architecture-resilience-rules`, `microsoft-agent-framework`, `agent-workflow-rules`, `review-protocol`, `security-review`, `privacy-review` | (none) |
| `tests/e2e/login.spec.ts` | `**/*.{ts,tsx}`<br>`{tests/**/*.spec.ts,playwright.config.ts}` | `react-rules`, `tanstack-query-rules`, `tanstack-router`, `frontend-rules`, `ux-evidence`, `playwright-cli`, `playwright-component-testing`, `prior-art`, `review-testing-rules` | `react-rules`, `tanstack-query-rules`, `frontend-rules`, `ux-evidence`, `playwright-cli`, `review-protocol`, `security-review`, `privacy-review` | `ux-evidence`, `playwright-cli`, `playwright-trace` |
| `tests/api/health.bru` | `{**/*.bru,**/bruno.json}` | `bruno`, `prior-art`, `review-testing-rules` | `review-protocol`, `security-review`, `privacy-review` | `bruno` |

## Table 2: every name the sample routed, resolved

Resolution rule: a name resolves to the single `skills/<group>/<name>/SKILL.md`
whose directory basename is the name. The frontmatter `name` column is what
`scripts/check-skill-frontmatter.sh` compares against that basename, and it is
also what a routing row would have to say if the loader took the invocation
name from frontmatter instead of the directory. They agree on every row, so the
question does not bite here.

| Name | Resolved path | frontmatter `name` | extra frontmatter keys |
| --- | --- | --- | --- |
| `agent-router` | `skills/k8s-gitops/agent-router/SKILL.md` | `agent-router` | `license` |
| `agent-workflow-rules` | `skills/rules/agent-workflow-rules/SKILL.md` | `agent-workflow-rules` | none |
| `architecture-resilience-rules` | `skills/rules/architecture-resilience-rules/SKILL.md` | `architecture-resilience-rules` | none |
| `argocd` | `skills/k8s-gitops/argocd/SKILL.md` | `argocd` | `license` |
| `backend-rules` | `skills/rules/backend-rules/SKILL.md` | `backend-rules` | none |
| `bruno` | `skills/qa/bruno/SKILL.md` | `bruno` | `license` |
| `building-pydantic-ai-agents` | `skills/python/building-pydantic-ai-agents/SKILL.md` | `building-pydantic-ai-agents` | `compatibility`, `license`, `metadata` |
| `cloudnativepg` | `skills/k8s-gitops/cloudnativepg/SKILL.md` | `cloudnativepg` | `license` |
| `envoy-gateway` | `skills/k8s-gitops/envoy-gateway/SKILL.md` | `envoy-gateway` | `license` |
| `fastapi` | `skills/python/fastapi/SKILL.md` | `fastapi` | none |
| `frontend-rules` | `skills/rules/frontend-rules/SKILL.md` | `frontend-rules` | none |
| `helm` | `skills/k8s-gitops/helm/SKILL.md` | `helm` | `license` |
| `kubectl` | `skills/k8s-gitops/kubectl/SKILL.md` | `kubectl` | `license` |
| `kustomize` | `skills/k8s-gitops/kustomize/SKILL.md` | `kustomize` | `license` |
| `loki` | `skills/observability/loki/SKILL.md` | `loki` | `license` |
| `microsoft-agent-framework` | `skills/agents/microsoft-agent-framework/SKILL.md` | `microsoft-agent-framework` | `license` |
| `playwright-cli` | `skills/qa/playwright-cli/SKILL.md` | `playwright-cli` | `allowed-tools` |
| `playwright-component-testing` | `skills/qa/playwright-component-testing/SKILL.md` | `playwright-component-testing` | none |
| `playwright-trace` | `skills/qa/playwright-trace/SKILL.md` | `playwright-trace` | `allowed-tools` |
| `prior-art` | `skills/process/prior-art/SKILL.md` | `prior-art` | none |
| `privacy-review` | `skills/privacy/privacy-review/SKILL.md` | `privacy-review` | none |
| `promql` | `skills/observability/promql/SKILL.md` | `promql` | `license` |
| `pydantic` | `skills/python/pydantic/SKILL.md` | `pydantic` | none |
| `pydantic-house-rules` | `skills/python/pydantic-house-rules/SKILL.md` | `pydantic-house-rules` | `license` |
| `react-rules` | `skills/react/react-rules/SKILL.md` | `react-rules` | none |
| `review-protocol` | `skills/process/review-protocol/SKILL.md` | `review-protocol` | none |
| `review-testing-rules` | `skills/rules/review-testing-rules/SKILL.md` | `review-testing-rules` | none |
| `security-review` | `skills/security/security-review/SKILL.md` | `security-review` | none |
| `sops-age` | `skills/k8s-gitops/sops-age/SKILL.md` | `sops-age` | `license` |
| `tanstack-query-rules` | `skills/react/tanstack-query-rules/SKILL.md` | `tanstack-query-rules` | none |
| `tanstack-router` | `skills/react/tanstack-router/SKILL.md` | `tanstack-router` | none |
| `tempo` | `skills/observability/tempo/SKILL.md` | `tempo` | `license` |
| `temporal-developer` | `skills/temporal/temporal-developer/SKILL.md` | `temporal-developer` | `version` |
| `uv` | `skills/python/uv/SKILL.md` | `uv` | `license` |
| `ux-evidence` | `skills/process/ux-evidence/SKILL.md` | `ux-evidence` | none |


## Matcher header and summary, verbatim

```
routing rows parsed : 28
strict-yaml rejects : 1 ['skills/python/pydantic-house-rules/SKILL.md'] (read with the house line parser instead)
skills on disk      : 60
sample files        : 22
flags               : GLOBSTAR | BRACE | DOTGLOB

names routed by the sample : 35
resolved                   : 35
unresolved                 : 0 []
skills on disk not routed by this sample (25): activitykit, compose-build-and-test, compose-performance, compose-state, compose-ui, gdpr-consent, gdpr-erasure-retention, healthkit, kotlin-concurrency, kotlin-control-flow, kotlin-functions, kotlin-types-value-class, photokit, product-spec, push-notifications, pydantic-ai-harness, qa-verification, short-attention-media, short-form-posts, supabase, supabase-postgres-best-practices, swiftui-pro, ui-ux-pro-max, ux-journey, widgetkit
routing rows no sample file hits (10):
  - **/*.swift
  - **/{Health,Workout}*
  - **/{Widget,LiveActivity}*
  - **/{Photo,Camera}*
  - **/*[Nn]otification*
  - **/*.{kt,kts}
  - **/*.sql
  - **/{migrations,schemas}/**
  - **/{chart,charts}/**/templates/**/*.{yaml,yml,tpl}
  - **/{postgres,cnpg}/**

## every name in every routing row (not just the sample)
names in the template : 54
unresolved            : 0 []
```

Reading of the three summary blocks:

- `skills on disk not routed by this sample (25)`: expected. The sample is a
  GitOps and Python repo, so the iOS, Android, Supabase and privacy rows never
  fire. Six of those 25 are not in any routing row at all by design, because
  they are role competencies carried in an agent's own frontmatter rather than
  routed by file type: `product-spec` (planner), `qa-verification` (qa),
  `short-form-posts` (content-writer), `short-attention-media`
  (media-producer), `kotlin-functions` and `pydantic-ai-harness` (named in the
  implementer, implementer-simple and qa catalogs as conditional picks).
- `routing rows no sample file hits (10)`: the same story per row. Note
  `**/{chart,charts}/**/templates/**/*.{yaml,yml,tpl}` is in this list even
  though the sample carries `charts/temporal/Chart.yaml`; the chart in the
  sample has no rendered template file yet, and `**/Chart.yaml` covers it.
- `every name in every routing row`: the stronger check the commit subject
  claims. All 54 names used anywhere in `routing`, including the rows no sample
  file touched and the `design` role in `always`, resolve to a SKILL.md.
