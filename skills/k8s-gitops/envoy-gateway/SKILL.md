---
name: envoy-gateway
description: Use when writing or reviewing Gateway API and Envoy Gateway resources - GatewayClass, Gateway, HTTPRoute, SecurityPolicy (OIDC, JWT, claim authorization), BackendTLSPolicy, ClientTrafficPolicy, BackendTrafficPolicy - or when a route returns 401/403/302 unexpectedly, a policy shows Accepted=False, or an unauthenticated health probe needs to bypass a login gate.
license: MIT
---

# Envoy Gateway

Targets Envoy Gateway **v1.9.x** (forge pins chart `gateway-helm` v1.9.1). Every rule cites the
`/v1.9/` page it comes from; on a version bump, re-read those pages under the new prefix first.

Sources (fetched 2026-09-10 with `curl -sSL`, all HTTP 200):
- https://gateway.envoyproxy.io/v1.9/tasks/security/oidc/ - "OIDC Authentication"
- https://gateway.envoyproxy.io/v1.9/tasks/security/jwt-authentication/ - "JWT Authentication"
- https://gateway.envoyproxy.io/v1.9/tasks/security/jwt-claim-authorization/ - "JWT Claim-Based Authorization"
- https://gateway.envoyproxy.io/v1.9/api/extension_types/ - "Gateway API Extensions"
- https://gateway.envoyproxy.io/v1.9/api/gateway_api/backendtlspolicy/ - "BackendTLSPolicy"
- https://gateway.envoyproxy.io/v1.9/tasks/traffic/http-routing/ - "HTTP Routing"
- https://gateway.envoyproxy.io/v1.9/tasks/traffic/http-timeouts/ - "HTTP Timeouts"
- https://gateway.envoyproxy.io/v1.9/tasks/operations/egctl/ - "Use egctl"

## When to apply

- Authoring or reviewing `GatewayClass`, `Gateway`, `HTTPRoute`, `GRPCRoute`.
- Authoring or reviewing an Envoy Gateway extension policy: `SecurityPolicy` (OIDC, JWT,
  claim-based authorization), `BackendTLSPolicy`, `ClientTrafficPolicy`, `BackendTrafficPolicy`,
  `Backend`.
- Putting a login gate in front of an app, or carving an unauthenticated exemption (health probe,
  webhook ingest) out of a protected host.
- Cross-namespace references between a route, a policy and a backend (`ReferenceGrant`).
- Debugging: a protected route answers 200 without a session, an exempt route answers 302, a
  policy sits at `Accepted=False`, a gRPC client fails through the gateway.

## Rules

### Policy attachment and precedence

- `SecurityPolicy` may target `Gateway`, `ListenerSet`, `HTTPRoute`, `GRPCRoute` and `TCPRoute`.
  Against a `TCPRoute` target **only** client-IP CIDR authorization applies: JWT, API key, basic
  auth, OIDC, ext-auth and GeoIP based authorization are silently not applicable there.
  (api/extension_types, `SecurityPolicySpec`)
- Use `targetRefs` (list). `targetRef` (singular) is marked **Deprecated: use
  targetRefs/targetSelectors instead** in the v1.9 API reference; several task pages still show
  the singular form in older examples, so copy the field name from the API reference, not from a
  task snippet. (api/extension_types, `SecurityPolicySpec`)
- The policy and its target must be in the same namespace for the policy to have effect.
  (api/extension_types, `SecurityPolicySpec.targetRef`)
- Without `mergeType`, **no merging occurs and only the most specific configuration takes
  effect** - a route-level `SecurityPolicy` replaces the Gateway-level one for that route rather
  than layering on top of it. `mergeType` can only be set when targeting xRoute resources.
  (api/extension_types, `SecurityPolicySpec.mergeType`)
- `targetSelectors` reaching across namespaces needs a `ReferenceGrant` in the target namespace
  permitting this policy kind to reference that target kind; cross-namespace targets without a
  matching grant are **ignored**, not rejected. (api/extension_types, `TargetSelector.namespaces`)
- One `SecurityPolicy` per app, targeting that app's `HTTPRoute`, is the shape the docs show first
  and the only shape that lets a sibling route stay unauthenticated; a Gateway-level policy
  authenticates every route on the Gateway with one configuration. (tasks/security/oidc)

### SecurityPolicy: OIDC

- `spec.oidc.provider.issuer` plus `clientID` (or `clientIDRef`) plus `clientSecret` (a Secret
  reference) plus `redirectURL` plus `logoutPath`. The client secret is an Opaque Secret whose
  key **must** be `client-secret`; `clientIDRef` likewise uses key `client-id`. Exactly one of
  `clientID` and `clientIDRef` may be set. (tasks/security/oidc; api/extension_types, `OIDC`)
- `redirectURL` and `logoutPath` must match the target route. Targeting an `HTTPRoute` for host
  `www.example.com` path `/myapp` means `redirectURL` is prefixed `https://www.example.com:8443/myapp`
  and `logoutPath` is prefixed `/myapp`, "otherwise the OIDC authentication will fail because the
  redirect and logout requests will not match the target HTTPRoute". Targeting a Gateway, they must
  match **one of** the routes attached to it. (tasks/security/oidc)
- The redirect URL must be HTTPS: "EG OIDC authentication requires the redirect URL to be HTTPS."
  (tasks/security/oidc)
- Set `cookieDomain` to the root domain when tokens must be shared across subdomains. It defaults
  to the request host **excluding** subdomains. Adding `cookieDomain` to an existing policy
  requires clearing browser cookies, or the old-subdomain cookies win and authentication fails.
  (tasks/security/oidc; api/extension_types, `OIDC.cookieDomain`)
- Non-browser callers: `passThroughAuthHeader: true` skips OIDC when the request carries a header
  the JWT filter will extract (by default `Authorization: Bearer ...`); `denyRedirect` matchers
  suppress the 302 for "AJAX or machine requests". (api/extension_types, `OIDC`)
- Forwarding identity upstream is opt-in: `forwardAccessToken` (default `false`) sends the access
  token as `Authorization: Bearer`, `forwardIDToken` configures an ID-token header. When
  `passThroughAuthHeader` is enabled the forwarded ID token header **must not** be a header a JWT
  provider extracts from; Envoy owns that header and rejects the configuration.
  (api/extension_types, `OIDC.forwardAccessToken`, `OIDC.forwardIDToken`)
- Do not set `disableTokenEncryption: true`; it stores access and ID tokens in plain text
  (default `false`). `defaultTokenTTL` defaults to `0`, which makes the provider's `expires_in`
  mandatory "or the OAuth flow will fail". (api/extension_types, `OIDC`)
- A provider with a private CA is reached through a `Backend` in `oidc.provider.backendRefs` plus
  a `BackendTLSPolicy` on that `Backend`. `oidc.provider.backendSettings` currently supports
  **only** a retry policy. (tasks/security/oidc, "Connect to an OIDC Provider with Self-Signed
  Certificate")
- Azure Entra: `issuer: https://login.microsoftonline.com/<TENANT_ID>/v2.0`, a registered scope
  (`api://.../<App>.OIDC`) in `provider.scopes`, `cookieNames.accessToken` set, and a `jwt`
  provider whose `remoteJWKS.uri` is the tenant's `discovery/v2.0/keys` with
  `extractFrom.cookies` naming that same cookie. (tasks/security/oidc, "Providers / Azure Entra")

### SecurityPolicy: JWT and claim authorization

- A JWT provider validates with `remoteJWKS.uri`, or `localJWKS` from a ConfigMap via
  `type: ValueRef` + `valueRef`. A remote JWKS behind a private CA needs a `Backend` in
  `remoteJWKS.backendRefs` plus a `BackendTLSPolicy`; the `Backend` is unnecessary when the JWKS
  is a Service in the same cluster. (tasks/security/jwt-authentication)
- Claim-based authorization requires JWT authentication configured **in the same SecurityPolicy**:
  the token has to be validated before its claims can be read. (tasks/security/jwt-claim-authorization)
- Write `authorization.defaultAction: Deny` and enumerate `Allow` rules. Claims use
  `valueType: StringArray` for array claims (for example `roles`); `scopes` matches the
  space-delimited `scope` claim. (tasks/security/jwt-claim-authorization)
- Expected responses: no token on a JWT-protected route is **401**; a valid token failing an
  authorization rule is **403**. (tasks/security/jwt-authentication;
  tasks/security/jwt-claim-authorization)
- Routing on a JWT claim needs three things together: `claimToHeaders` mapping claim to header,
  `recomputeRoute: true`, and a catch-all fallback route rule (its backend may be invalid). The
  docs state the SecurityPolicy must be applied "to both the fallback route as well as the route
  with the claim header matches, **to avoid spoofing**". (tasks/traffic/http-routing, "JWT Claims
  Based Routing")

### Routes and exemptions

- Hostnames are matched before any other matching. Within a matched hostname, "the most specific
  match will take precedence". (tasks/traffic/http-routing)
- An unauthenticated path on an otherwise protected host is its own `HTTPRoute`, not a rule inside
  the protected one: policy attachment is per route, so a separate route is the unit that can go
  ungated. In the docs' own OIDC walkthrough, `/foo` stays reachable after login precisely because
  it is a different HTTPRoute than the policy's target. (tasks/security/oidc, "Testing";
  api/extension_types, `SecurityPolicySpec`)
- A `backendRef` in another namespace needs a `ReferenceGrant` in the referent namespace.
  `port` is required when the referent is a Kubernetes Service, and it is the **service** port,
  not the target port. (api/extension_types, `BackendRef`)

### BackendTLSPolicy

- `BackendTLSPolicy` is GA and in the Gateway API Standard Channel since v1.4.0. It configures TLS
  from the Gateway to the backend ("backend TLS termination"), and works with any route type that
  forwards to backends. (api/gateway_api/backendtlspolicy)
- It is a Direct PolicyAttachment with no defaults and no overrides, and it must live in the same
  namespace as the Service it targets. **Cross-namespace certificate references are not allowed.**
  (api/gateway_api/backendtlspolicy)
- `validation.hostname` is the SNI the Gateway presents and must match the certificate the backend
  serves. IP addresses and wildcard hostnames are not allowed. (api/gateway_api/backendtlspolicy)
- `caCertificateRefs` and `wellKnownCACertificates` are mutually exclusive, exactly one per
  validation block; `System` is documented for environments where specific certificates are not
  required, "e.g. in a development environment". (api/gateway_api/backendtlspolicy)
- `subjectAltNames` (added in v1.2.0) is checked in addition to SNI, max 5 entries, each typed
  `Hostname` or `URI`; it is how mutual TLS and SPIFFE identities are pinned separately from SNI.
  (api/gateway_api/backendtlspolicy)
- Status uses `PolicyAncestorStatus`, so read `status.ancestors[].conditions`, never a top-level
  condition list. (api/gateway_api/backendtlspolicy)

### Timeouts

- Envoy Proxy's default request timeout is **15 seconds**. `HTTPRoute` rules carry
  `timeouts.request` (gateway responds to the client) and `timeouts.backendRequest` (one attempt
  to the backend), and `request` must be `>= backendRequest`. Exceeding it returns
  **504 Gateway Timeout** with body `upstream request timeout`. (tasks/traffic/http-timeouts)
- Long-lived and streaming responses are governed by `BackendTrafficPolicy`
  `timeout.http.maxStreamDuration` and `timeout.http.streamIdleTimeout`, not by the route's
  `timeouts.request`. `maxStreamDuration` **"When set to `0s`, no max duration is applied and
  streams can run indefinitely"**, and it "does not apply to non-streaming requests".
  `streamIdleTimeout` inherits from the listener-level `ClientTrafficPolicy` value when unset
  (listener default: 5 minutes). (api/extension_types, `HTTPTimeout`, `HTTPClientTimeout`)
- Listener-level connection timeouts live on `ClientTrafficPolicy.timeout.http`: `idleTimeout`
  (default 1 hour), `streamIdleTimeout` (default 5 minutes), `requestReceivedTimeout`,
  `requestHeadersReceivedTimeout`. (api/extension_types, `HTTPClientTimeout`)

## Unverified: verify, do not assume

Write these as open questions in a plan, never as rules. Each was checked against the pages above
on 2026-09-10 and the docs are **silent**.

- **`HTTPRoute` `timeouts.request: 0s`.** The v1.9 HTTP Timeouts page describes only `request` and
  `backendRequest` with positive durations and never mentions `0s`, "disabled", "unlimited" or
  "infinite". The only documented `0s` semantics in v1.9 belong to a *different* field,
  `BackendTrafficPolicy.timeout.http.maxStreamDuration`. Do not carry that meaning across. If a
  route must stream without a wall-clock cap, use the documented field, or spike `0s` on the
  route against v1.9.1 and record the observed behaviour before relying on it.
- **Server-sent events / streaming through the gateway.** No page fetched here describes SSE,
  chunked-response or long-poll behaviour, buffering, or which timeout fires first for a slow
  stream. Treat any SSE configuration as an untested spike.
- **Whether Envoy overwrites a client-supplied header that `claimToHeaders` also writes.** The
  docs prescribe applying the SecurityPolicy to the fallback route as well "to avoid spoofing",
  which implies the guard is *policy coverage of every route*, not header sanitisation. They do
  not state that a client-sent `x-sub` is stripped or overwritten. Until that is proven on the
  running version, treat a claim-derived header as trustworthy **only** on routes the policy
  covers, and prove it with a request that sets the header itself.

## Anti-patterns

- **OIDC at the Gateway, then expecting a per-route exemption.** A Gateway-level policy
  authenticates every route attached to that Gateway. The exemption has to be a route the policy
  does not target, and without `mergeType` a route-level policy replaces rather than refines the
  Gateway one. Result: health probes get 302'd into a login flow and the probe reports the app
  down.
- **Trusting an identity header from `claimToHeaders` on an uncovered route.** The docs' spoofing
  guard is policy coverage of every matching route including the fallback. A route the policy does
  not target will happily forward whatever header the client sent. Result: header-spoofed
  privilege escalation.
- **Reading `timeouts.request: 0s` as "no timeout".** Undocumented at v1.9 (see above). Result:
  either a silent 15s default or a 504 mid-stream, discovered in production.
- **HTTP/1.1-only listeners in front of gRPC clients.** gRPC needs HTTP/2 end to end; a client
  that cannot negotiate it (the `argocd` CLI, for example) needs `--grpc-web` or an HTTP/2
  listener. Result: opaque transport errors rather than a status code.
- **`targetRef` (singular) in new manifests.** Deprecated at v1.9; it also cannot express the
  multi-target and selector shapes. Result: a rewrite at the next bump.
- **Client secret inline, or in a Secret under any key but `client-secret`.** The OIDC filter
  reads that exact key. Result: policy accepted, login broken at runtime.
- **A `BackendTLSPolicy` in a different namespace from its Service, or a cross-namespace CA ref.**
  Both are disallowed. Result: the policy never attaches and egress silently loses its CA pin.

## Verify

Offline, on the manifest, before commit (no cluster needed). Feed a `GatewayClass` in with the
policy so the translator has a root:

```bash
{ cat <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata: { name: forge }
spec: { controllerName: gateway.envoyproxy.io/gatewayclass-controller }
---
EOF
cat manifests/gateway-auth/securitypolicy-<app>.yaml; } \
  | egctl x translate --from gateway-api --to gateway-api --add-missing-resources -f -
```

Expect YAML on stdout and **no `Error:` line**. A schema or field-name mistake shows up here as
`Error: unable to unmarshal input: ...`. (`-t/--type` selects an output type only for
`--to xds`; valid types are `bootstrap endpoint cluster listener route all`.)

On the cluster, after sync:

```bash
egctl x status securitypolicy -A                 # every row Accepted / True / Accepted
kubectl get securitypolicy -n <ns> <name> \
  -o jsonpath='{.status.ancestors[*].conditions[?(@.type=="Accepted")].status}'   # True
egctl x status backendtlspolicy -A               # Accepted / True
egctl config envoy-proxy listener -n envoy-gateway-system   # listener dump, non-empty
```

End to end, the two answers that prove the gate and its exemption:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -k https://<app>.<domain>/            # 302 to the IdP
curl -sS -o /dev/null -w '%{http_code}\n' -k https://<app>.<domain>/health/ready # 200
```

A protected path answering 200 without a session, or an exempt path answering 302, means the
policy is attached to the wrong route.
