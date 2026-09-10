---
name: agent-router
description: Use when routing LLM or MCP traffic through Envoy Gateway with Agent Router (the project formerly called Envoy AI Gateway) - AIGatewayRoute, AIServiceBackend, BackendSecurityPolicy, GatewayConfig, MCPRoute, the aigw CLI - or when wiring provider credentials for OpenAI, Azure OpenAI, Anthropic, Bedrock or Vertex, or when per-caller token and cost metrics are missing from Prometheus.
license: MIT
---

# Agent Router

Targets **v1.1.x** (latest release `v1.1.0`, 2026-08-21). Written from the `/docs/` tree, which
served `docusaurus_version: 1.1` on every page below, so it is the v1.1 tree and not `next`.

**The rename, checked 2026-09-10.** `envoyproxy/ai-gateway` now redirects (HTTP 301, GitHub API)
to **`theagentrouter/agent-router`**, Apache-2.0, "Manages Unified Access to Generative AI Services
built on Envoy Gateway", an Agentic AI Foundation project. Cite that repo and `theagentrouter.ai`,
never the old name, as current.

**What did NOT change.** The docs are explicit: "no CRD, API, or CLI names have changed (`aigw`,
`AIGatewayRoute`, and the `aigateway.envoyproxy.io` API group are all unchanged), and there is
nothing to migrate" (`/docs/`). The v1.1 API reference contains **zero** occurrences of a kind
named `AgentRoute`; the served kinds are `AIGatewayRoute`, `AIServiceBackend`,
`BackendSecurityPolicy`, `GatewayConfig`, `MCPRoute` (`/docs/api/`). The Helm charts and the
controller namespace still carry the old names too (`envoyproxy/ai-gateway-helm`,
`envoy-ai-gateway-system`). Expect the product name and the API names to disagree; that is
correct, not a stale doc.

Sources (fetched 2026-09-10 with `curl -sSL`, all HTTP 200, all `docusaurus_version: 1.1`):
- https://theagentrouter.ai/docs/ - "Home | Agent Router"
- https://theagentrouter.ai/docs/getting-started/ - "Getting Started | Agent Router"
- https://theagentrouter.ai/docs/getting-started/installation/ - "Installation | Agent Router"
- https://theagentrouter.ai/docs/compatibility - "Compatibility Matrix | Agent Router"
- https://theagentrouter.ai/docs/concepts/architecture/ - "Architecture | Agent Router"
- https://theagentrouter.ai/docs/capabilities/ - "Capabilities | Agent Router"
- https://theagentrouter.ai/docs/capabilities/security/upstream-auth - "Upstream Authentication | Agent Router"
- https://theagentrouter.ai/docs/capabilities/observability/metrics/ - "AI/LLM Metrics | Agent Router"
- https://theagentrouter.ai/docs/api/ - "API Reference | Agent Router"
- https://theagentrouter.ai/docs/cli/ - "Agent Router CLI | Agent Router"

GitHub fallback when a page moves: `https://github.com/theagentrouter/agent-router` at tag
`v1.1.0` (`README.md`, `docs/`, `api/`).

## When to apply

- Routing LLM traffic through Envoy Gateway: `AIGatewayRoute`, `AIServiceBackend`, model-based
  routing, provider fallback, model virtualization.
- Attaching provider credentials: `BackendSecurityPolicy` for OpenAI, Azure OpenAI, Anthropic,
  AWS Bedrock, GCP Vertex.
- Per-caller token, cost and latency metrics, or a `gen_ai.*` based Prometheus alert.
- MCP gateway work: `MCPRoute`, tool routing, per-identity discovery and invocation control.
- Local development or a repro with the `aigw` CLI.
- Version bumps: checking the Envoy Gateway / Gateway API / Kubernetes compatibility row.

## Rules

### Install and version compatibility

- Agent Router is a **control plane on top of Envoy Gateway**, not a replacement for it. Data
  plane = Envoy Proxy plus the AI Gateway external processor; control plane = the AI Gateway
  controller working with the Envoy Gateway controller. Envoy Gateway must be installed first.
  (`/docs/concepts/architecture/`)
- Compatibility matrix for **v1.1.x**: Envoy Gateway **v1.8.1+** (Envoy Proxy v1.38.x),
  Kubernetes **v1.32+**, Gateway API **v1.5.x**. "Compatibility" there means the combination was
  tested and verified; other versions "may work but are not officially supported".
  (`/docs/compatibility`)
- Install is two Helm charts, CRDs first, and the CRD chart version must match the controller
  chart version: `oci://docker.io/envoyproxy/ai-gateway-crds-helm --version v1.1.0` then
  `oci://docker.io/envoyproxy/ai-gateway-helm --version v1.1.0`, both into
  `envoy-ai-gateway-system`. Gate on
  `kubectl wait -n envoy-ai-gateway-system deployment/ai-gateway-controller --for=condition=Available`.
  (`/docs/getting-started/installation/`)
- Upgrading from a release that only had `ai-gateway-helm`: install the CRD chart with
  `--take-ownership` first, then upgrade the main chart. (`/docs/getting-started/installation/`)
- Pin an explicit `--version`. The docs' own warning against floating tags is that "the latest
  container tags are overwritten", so an unpinned install drifts under you.
  (`/docs/getting-started/installation/`)

### API version

- Write `apiVersion: aigateway.envoyproxy.io/v1beta1` for new resources. `v1alpha1` is deprecated
  but still served for `AIGatewayRoute`, `AIServiceBackend`, `BackendSecurityPolicy`,
  `GatewayConfig` and `MCPRoute`. `QuotaPolicy` is **v1alpha1-only**; there is no v1beta1.
  (`/docs/compatibility`)
- Storage-version migration is **not automatic**. Existing objects stay stored as `v1alpha1`
  until you re-apply them as `v1beta1` (or drive the storage migration API). Upgrading the CRD
  chart alone does not migrate them. (`/docs/compatibility`)

### Routing

- `AIGatewayRoute` binds `AIServiceBackend`s to one or more Gateways and generates, in its own
  namespace, an `HTTPRoute` with the same name plus an `HTTPRouteFilter` named
  `ai-eg-host-rewrite-${AIGatewayRoute.Name}`. Those are implementation detail "subject to
  change": do not hand-edit them. To change generated behaviour, attach Envoy Gateway's
  `BackendTrafficPolicy` to the generated `HTTPRoute`, or use `EnvoyPatchPolicy`.
  (`/docs/api/`, `AIGatewayRoute`)
- Route by model with the **`x-ai-eg-model`** header in an `AIGatewayRouteRule` match. The model
  name is extracted from the request body before the routing decision, so the header exists even
  though no client sent it. Multi-rule matching follows Gateway API semantics.
  (`/docs/api/`, `AIGatewayRouteSpec.rules`)
- A rule that matches on `x-ai-eg-model` also feeds the OpenAI-compatible `/models` endpoint;
  `modelsOwnedBy` (default `Envoy AI Gateway`) and `modelsCreatedAt` set what that endpoint
  reports for those models. (`/docs/api/`, `AIGatewayRouteRule`)
- `AIGatewayRoute.spec.parentRefs` currently accept `Kind: Gateway` only. `hostnames` behaves as
  the Gateway API `HTTPRouteSpec` field of the same name. (`/docs/api/`)

### Credentials: BackendSecurityPolicy

- One `BackendSecurityPolicy` per `AIServiceBackend` or `InferencePool`, and **only one**:
  "Attaching multiple BackendSecurityPolicies to the same resource is invalid and will result in
  an error during the reconciliation of the resource." Only one auth mechanism may be set per
  policy. (`/docs/api/`, `BackendSecurityPolicySpec`)
- Credentials are **always** a `secretRef`, never an inline literal, and the secret key is fixed
  per type: `apiKey` for `apiKey`, `azureAPIKey` and `anthropicAPIKey`; `client-secret` for
  `azureCredentials.clientSecretRef`. The controller needs RBAC to read that secret.
  (`/docs/api/`, `BackendSecurityPolicyAPIKey`, `BackendSecurityPolicyAzureAPIKey`,
  `BackendSecurityPolicyAnthropicAPIKey`, `BackendSecurityPolicyAzureCredentials`)
- Where the provider supports short-lived credentials, prefer them. The control plane performs
  **automated credential management**: AWS Bedrock via OIDC to AWS STS, Azure OpenAI via Entra ID
  short-lived access tokens, GCP Vertex via workload federation and Google STS, each issuing
  fresh credentials per request. Long-lived API keys are the manual fallback, not the default.
  (`/docs/capabilities/security/upstream-auth`)
- Azure keyless: `azureCredentials` with `clientID` and `tenantID` required, then **exactly one**
  of `clientSecretRef` or `oidcExchangeToken`. "Credentials will not be generated if neither are
  set" - a policy with neither reconciles quietly and then fails at request time.
  `oidcExchangeToken` carries an `oidc` block, plus optional `grantType` and `aud`; the
  controller queries Entra ID for an access token and stores it in a secret.
  (`/docs/api/`, `BackendSecurityPolicyAzureCredentials`, `AzureOIDCExchangeToken`)
- AWS: with neither `credentialsFile` nor `oidcExchangeToken`, the AWS SDK default credential
  chain is used (env vars, EKS Pod Identity, IRSA, EC2 IMDS, ECS task roles). The docs recommend
  that chain for Kubernetes because it rotates without manual configuration. Either explicit
  field takes precedence over it. (`/docs/api/`, `BackendSecurityPolicyAWSCredentials`)
- Read `status.conditions` on the policy; the known types are `Accepted` and `NotAccepted`, and
  "at most one condition is set". (`/docs/api/`, `BackendSecurityPolicyStatus`)
- Client-to-gateway authentication is **not** this API's job. The docs route it to Envoy
  Gateway's own security documentation (`SecurityPolicy`: OIDC, JWT, API key). Upstream
  authentication only covers gateway-to-provider.
  (`/docs/capabilities/security/upstream-auth`)

### Metrics

- Metrics are collected by default, in OpenTelemetry format following the **OpenTelemetry Gen AI
  Semantic Conventions**, and exposed for Prometheus.
  (`/docs/capabilities/observability/metrics/`)
- Instruments: `gen_ai.client.token.usage` (attribute `gen_ai.token.type` splits input / output /
  total), `gen_ai.server.request.duration`, `gen_ai.server.time_to_first_token`,
  `gen_ai.server.time_per_output_token`. Default attributes include `gen_ai.operation.name`
  (`chat`, `completion`, `embedding`, `rerank`, `image_generation`, `messages`),
  `gen_ai.original.model`, `gen_ai.request.model`, `gen_ai.response.model`,
  `gen_ai.provider.name`. (`/docs/capabilities/observability/metrics/`)
- In PromQL the dots become underscores and the counter takes the usual suffix, for example
  `sum(gen_ai_client_token_usage_sum{...}) by (gen_ai_request_model, gen_ai_token_type)`. Write
  alert expressions against the underscore form, not the dotted names.
  (`/docs/capabilities/observability/metrics/`)
- Per-caller attribution comes from request headers, configured in Helm values:
  `controller.requestHeaderAttributes` for a base mapping shared with spans and access logs, and
  `controller.metricsRequestHeaderAttributes` for metrics only. "Metrics never default to
  `session.id` because it is high-cardinality" - pick a low-cardinality caller identifier and
  keep it out of the per-request dimension. (`/docs/capabilities/observability/metrics/`)
- Metrics exist only for the instrumented endpoints: `/v1/chat/completions`, `/v1/completions`,
  `/v1/embeddings`, `/cohere/v2/rerank`, `/anthropic/v1/messages`. Traffic on any other path
  produces no `gen_ai.*` series, so a spend alert over it silently reads zero.
  (`/docs/capabilities/observability/metrics/`)

### CLI

- `aigw` is **experimental and under active development**; do not build a pipeline on its flags.
  (`/docs/cli/`)
- `aigw run` starts a standalone OpenAI-compatible router on `localhost:1975` with no Docker and
  no Kubernetes (Linux and macOS), auto-configuring from the same environment variables the
  OpenAI SDK reads, and can front self-hosted models and MCP servers. It takes the same
  configuration API as the Kubernetes path, which makes it the cheapest repro for a routing
  question. (`/docs/getting-started/`, `/docs/cli/`)

## Unverified: verify, do not assume

- **Envoy Gateway v1.9.1 with Agent Router v1.1.x.** The matrix row says "v1.8.1+" but names only
  Envoy Proxy v1.38.x as tested. EG v1.9 is not listed by name, and "tested and verified"
  attaches to the listed combinations. Verify on the target cluster before treating v1.9.1 as
  supported. (`/docs/compatibility`)
- **A workload-identity (keyless) Azure path from a local k3d cluster.** The docs describe
  `oidcExchangeToken` and Entra ID token exchange but say nothing about a cluster whose issuer is
  not reachable by Entra. Treat it as an unproven spike; a client secret in a Secret is the
  documented fallback.
- **The installation page's "main branch version" tip.** That page served
  `docusaurus_version: 1.1` and shows `--version v1.1.0`, yet still carries a tip about browsing
  "the documentation for the main branch version" and replacing `v0.0.0-latest`. The two disagree;
  trust the pinned `v1.1.0` commands and re-check on the next release.

## Anti-patterns

- **API keys in `values.yaml`, a ConfigMap, or inline in a CR.** Every credential type in this API
  is a `secretRef` with a fixed key. Result: a provider key in git and in every Helm release
  history, needing rotation rather than deletion.
- **Two `BackendSecurityPolicy` objects on one `AIServiceBackend`.** Explicitly invalid; it errors
  during reconciliation rather than merging.
- **One shared backend policy across tenants when per-caller cost is required.** Cost attribution
  comes from `gen_ai.*` metric attributes fed by request headers, not from the credential. A
  shared policy is fine; a missing `metricsRequestHeaderAttributes` mapping is what leaves spend
  unattributable.
- **`session.id` or another per-request value as a metrics label.** High cardinality; the docs
  refuse it by default for that reason. Result: a Prometheus that falls over before the alert
  ever fires.
- **Citing `envoyproxy/ai-gateway` docs or `docs.envoyproxy.io/ai-gateway` as current.** Renamed;
  cite `theagentrouter/agent-router` and `theagentrouter.ai`. The inverse mistake is just as bad:
  renaming `AIGatewayRoute` or `aigateway.envoyproxy.io` in a manifest because the product renamed.
  Result: a CR the API server does not recognise.
- **Editing the generated `HTTPRoute` or `ai-eg-host-rewrite-*` `HTTPRouteFilter`.** Owned by the
  controller and "subject to change". Result: reconciliation reverts you, or the next upgrade does.
- **Alerting on dotted metric names.** Prometheus sees `gen_ai_client_token_usage_sum`. Result:
  an alert that can never fire.

## Verify

Kinds and attachment, after sync:

```bash
kubectl get aigatewayroute,aiservicebackend,backendsecuritypolicy -A
kubectl get backendsecuritypolicy -n <ns> <name> \
  -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}'      # True
kubectl get deployment -n envoy-ai-gateway-system ai-gateway-controller # 1/1
kubectl api-resources --api-group=aigateway.envoyproxy.io               # v1beta1 served
```

A request through the gateway, using the model name the route matches on:

```bash
curl -sS http://$GATEWAY_HOST/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<model-in-the-route-rule>","messages":[{"role":"user","content":"ping"}]}'
```

Expect an OpenAI-shaped completion. A 404 with an empty model list usually means the rule does
not match on `x-ai-eg-model`; a 401/403 from the provider means the `BackendSecurityPolicy` is
`Accepted` but its secret key name is wrong.

Token counters reached Prometheus:

```bash
curl -s http://localhost:9090/api/v1/query --data-urlencode \
  'query=sum(gen_ai_client_token_usage_sum) by (gen_ai_request_model, gen_ai_token_type)' | jq '.data.result[]'
```

Expect one series per model per `gen_ai_token_type` (`input`, `output`). An empty result after a
successful completion means either an uninstrumented endpoint or a scrape that is not reaching the
proxy.

Local, without a cluster:

```bash
OPENAI_API_KEY=... aigw run    # then POST to http://localhost:1975/v1/chat/completions
```
