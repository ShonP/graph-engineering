# Competency routing fallback

Read only when a dispatch and project profile do not provide routing. Prefer
actual imported frameworks and changed surfaces over file extension alone. A
Python helper does not imply FastAPI, Pydantic, Temporal or an agent framework.
Keep security/privacy duties in every role. Missing required skills are NEEDS_SETUP.

## implementer


Normally your dispatch names your REQUIRED skills (the spine derives them from the profile's `routing`). **If your dispatch names none, do not work from priors: derive them yourself** - read `.claude/graph-profile.yaml`, match its `routing` globs against the files your task touches, and invoke `Skill` for every match before touching code. If no profile exists, use this table:

| Files | Load |
|---|---|
| `*.ts` / `*.tsx` React | react-rules, tanstack-query-rules, tanstack-router, frontend-rules |
| `*.swift` | swiftui-pro (+ healthkit / widgetkit / activitykit / photokit / push-notifications when the task touches that framework) |
| `*.kt` / `*.kts` | compose-state, compose-ui, kotlin-concurrency (+ kotlin-functions, kotlin-types-value-class, kotlin-control-flow as the task calls for them) |
| SQL / migrations / schemas | supabase, supabase-postgres-best-practices (+ gdpr-erasure-retention, gdpr-consent for personal data) |
| `*.py` | uv, pydantic, pydantic-house-rules, fastapi, backend-rules, architecture-resilience-rules |
| `pyproject.toml`, `uv.lock`, `.python-version` | uv |
| `*.py` under `agents/**` | microsoft-agent-framework, agent-workflow-rules (+ building-pydantic-ai-agents, pydantic-ai-harness when the repo uses Pydantic AI) |
| `*.py` under `workflows/**` or `activities/**` | temporal-developer, pydantic-house-rules, architecture-resilience-rules |
| `argocd/**` | argocd, helm, kubectl, architecture-resilience-rules |
| `manifests/**` | kubectl, kustomize (+ cloudnativepg under a `postgres` / `cnpg` / `*-pg` directory, envoy-gateway under `gateway*`, agent-router under `ai-gateway` / `agent-router` / `llm-gateway`) |
| `Chart.yaml`, a chart's `templates/**` | helm |
| `kustomization.yaml` | kustomize |
| Any infra file above (`argocd/**`, `manifests/**`, charts, kustomize) | infra-verification (render, validate, rendered diff; qa also runs the ephemeral apply) |
| `.sops.yaml`, `*.enc.yaml` | sops-age |
| `tests/**/*.spec.ts`, `playwright.config.ts` | playwright-cli, playwright-component-testing, playwright-trace (reading a recorded trace) |
| `*.bru`, `bruno.json` | bruno, api-contract |
| Server-side API surface (`routers/`, `controllers/`, `endpoints/`, server-language `routes/` / `handlers/`, NestJS `*.controller.ts`, Next.js `app/api/**/route.ts`, OpenAPI/AsyncAPI spec - never frontend `src/routes/`) | bruno, schemathesis, api-contract |
| `observability/**`, `dashboards/**/*.json` | promql, loki, tempo |
| UI placement / flow decisions | ui-ux-pro-max (UX-judgment domains only) |
| Anything a user sees (`*.tsx`, `*.swift`, Compose `*.kt`, templates, styles) | ux-evidence |
| Any task, any stack | review-testing-rules (definition-of-done and impact-map are preloaded) |

`pydantic-house-rules` is the house overlay on the vendored `pydantic` skill: load both, and where they disagree the house rule wins (spec 4.5 precedence, house > vault-generated > adopted community).

## qa


Normally your dispatch names your REQUIRED skills (the spine derives them from the profile's `routing`). **If your dispatch names none, do not work from priors: derive them yourself** - read `.claude/graph-profile.yaml`, match its `routing` globs against the files your task touches, and invoke `Skill` for every match before touching code. If no profile exists, use this table:

| Files | Load |
|---|---|
| `*.ts` / `*.tsx` React | react-rules, tanstack-query-rules, tanstack-router, frontend-rules |
| `*.swift` | swiftui-pro (+ healthkit / widgetkit / activitykit / photokit / push-notifications when the task touches that framework) |
| `*.kt` / `*.kts` | compose-state, compose-ui, kotlin-concurrency (+ kotlin-functions, kotlin-types-value-class, kotlin-control-flow as the task calls for them) |
| SQL / migrations / schemas | supabase, supabase-postgres-best-practices (+ gdpr-erasure-retention, gdpr-consent for personal data) |
| `*.py` | uv, pydantic, pydantic-house-rules, fastapi, backend-rules, architecture-resilience-rules |
| `pyproject.toml`, `uv.lock`, `.python-version` | uv |
| `*.py` under `agents/**` | microsoft-agent-framework, agent-workflow-rules (+ building-pydantic-ai-agents, pydantic-ai-harness when the repo uses Pydantic AI) |
| `*.py` under `workflows/**` or `activities/**` | temporal-developer, pydantic-house-rules, architecture-resilience-rules |
| `argocd/**` | argocd, helm, kubectl, architecture-resilience-rules |
| `manifests/**` | kubectl, kustomize (+ cloudnativepg under a `postgres` / `cnpg` / `*-pg` directory, envoy-gateway under `gateway*`, agent-router under `ai-gateway` / `agent-router` / `llm-gateway`) |
| `Chart.yaml`, a chart's `templates/**` | helm |
| `kustomization.yaml` | kustomize |
| Any infra file above (`argocd/**`, `manifests/**`, charts, kustomize) | infra-verification (render, validate, rendered diff; qa also runs the ephemeral apply) |
| `.sops.yaml`, `*.enc.yaml` | sops-age |
| `tests/**/*.spec.ts`, `playwright.config.ts` | playwright-cli, playwright-component-testing, playwright-trace (reading a recorded trace) |
| `*.bru`, `bruno.json` | bruno, api-contract |
| Server-side API surface (`routers/`, `controllers/`, `endpoints/`, server-language `routes/` / `handlers/`, NestJS `*.controller.ts`, Next.js `app/api/**/route.ts`, OpenAPI/AsyncAPI spec - never frontend `src/routes/`) | bruno, schemathesis, api-contract |
| `observability/**`, `dashboards/**/*.json` | promql, loki, tempo |
| UI placement / flow decisions | ui-ux-pro-max (UX-judgment domains only) |
| Anything a user sees (`*.tsx`, `*.swift`, Compose `*.kt`, templates, styles) | ux-evidence |
| Any task, any stack | review-testing-rules |

`pydantic-house-rules` is the house overlay on the vendored `pydantic` skill: load both, and where they disagree the house rule wins (spec 4.5 precedence, house > vault-generated > adopted community).

## reviewer


Your dispatch names the conditional stack lenses (the spine derives them from the profile's `routing` review entries). **If it names none, derive them yourself before reading the diff** - read `.claude/graph-profile.yaml` and match its routing against the diff's files; without a profile, use the table below. Never review a stack diff with no stack lens loaded. Your preloaded lenses (review-protocol, security-review, privacy-review, definition-of-done) apply to every diff regardless.

| Diff touches | Load |
|---|---|
| `*.ts` / `*.tsx` React | react-rules, tanstack-query-rules, frontend-rules |
| `*.swift` | swiftui-pro |
| `*.kt` / `*.kts` | compose-performance, compose-state, kotlin-control-flow |
| SQL / migrations / schemas | supabase-postgres-best-practices (+ gdpr-erasure-retention, gdpr-consent for migrations touching personal data) |
| `*.py` | pydantic, pydantic-house-rules, fastapi, backend-rules, architecture-resilience-rules |
| `*.py` under `agents/**` | microsoft-agent-framework, agent-workflow-rules |
| `*.py` under `workflows/**` or `activities/**` | temporal-developer, architecture-resilience-rules |
| `argocd/**` | argocd, helm |
| `manifests/**`, `kustomization.yaml` | kubectl, kustomize (+ cloudnativepg for Cluster manifests) |
| `Chart.yaml`, a chart's `templates/**` | helm |
| Gateway API kinds (`HTTPRoute`, `SecurityPolicy`, `BackendTLSPolicy`, ...), `gateway*/**` | envoy-gateway |
| `ai-gateway/**`, `agent-router/**`, `llm-gateway/**` | agent-router |
| `.sops.yaml`, `*.enc.yaml` | sops-age |
| `tests/**/*.spec.ts` | playwright-cli |
| `*.bru`, `bruno.json` | bruno, api-contract |
| Server-side API surface (`routers/`, `controllers/`, `endpoints/`, server-language `routes/` / `handlers/`, NestJS `*.controller.ts`, Next.js `app/api/**/route.ts`, OpenAPI/AsyncAPI spec - never frontend `src/routes/`) | api-contract (+ schemathesis when judging the qa evidence) |
| `observability/**`, `dashboards/**/*.json` | promql, loki, tempo |

`pydantic-house-rules` is the house overlay on the vendored `pydantic` skill: read both, and a diff that follows the community skill against the house rule is a finding, not a tie (spec 4.5 precedence, house > vault-generated > adopted community). `security-review` and `privacy-review` are already on and are not repeated per row.
