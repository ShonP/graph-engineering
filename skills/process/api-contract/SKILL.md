---
name: api-contract
description: Use whenever a change touches an API surface - a route, controller, handler, request or response schema, status code, auth rule on an endpoint, or an OpenAPI/AsyncAPI spec. House rule - every API change ships a Bruno collection update and a current OpenAPI schema in the same PR, and qa runs the Bruno suite plus Schemathesis against a disposable running stack. Covers what counts, what the suite must assert, where it lives, how it runs, and who checks it.
---

# API contract evidence

**House rule: no API change merges without a Bruno suite that exercises it.**
A unit test proves a handler; it does not prove the endpoint a client calls -
routing, auth middleware, serialization, status codes and error envelopes all
sit between the two. The collection is the executable contract, it lives in
the PR beside the code, and qa runs it against the running stack.

Two layers, because each misses what the other catches:

- **Bruno** - the cases someone thought of, written with the code, reviewed in
  the PR, re-run after deploy. `bruno` is the competency.
- **Schemathesis** - the cases nobody thought of, generated from the schema.
  `schemathesis` is the competency, including which of its checks gate.

This skill is the duty: when it applies and what "done" means.

## The schema is part of the contract

Every HTTP API serves an OpenAPI schema (GraphQL: its SDL), current with the
code in the same PR. FastAPI generates it (`/openapi.json`); NestJS needs
`@nestjs/swagger`; elsewhere, a checked-in `openapi.yaml`. Every status an
endpoint returns is documented on it, errors included - FastAPI documents only
success and 422 unless the route declares `responses=`. A repo with no schema
gets one in the first API task that touches it; without it Schemathesis has
nothing to generate from and the API loses its second layer.

## What counts as an API change

- a new, removed or renamed endpoint, method or path parameter
- a changed request or response shape, field, type, default or status code
- a changed auth, authz, rate-limit or validation rule on an endpoint
- a changed error envelope or error code
- an edit to the OpenAPI / AsyncAPI spec file

Not an API change: an internal refactor with an identical wire contract. **When
in doubt, add the request.** If the existing suite already covers the
endpoint and still passes unchanged, say so in the PR; that is the evidence.

## What the suite must assert

Per endpoint touched, in its own folder so it runs alone (`bru run <folder>`):

| Case | Assert |
| --- | --- |
| Happy path | status, and the **values** that matter (`jsonBody` / `jsonSchema`), not just 200 |
| Auth | unauthenticated -> 401; wrong principal / tenant -> 403 or 404 (never another tenant's data) |
| Validation | one malformed or missing required field -> 4xx with the documented error envelope |
| Edge | the case the criteria name: empty list, pagination end, idempotent retry, conflict |
| Non-leak | a field that must NOT appear (internal ids, debug info, PII) is absent |

Tag the happy path `smoke` so post-deploy runs `bru run --tags smoke`. A request
with no `assert` or `tests` block does not count.

## Where it lives

The profile's `api.collection` (default `bruno/`) at the repo root, one
collection per repo unless the repo already splits by service - Bruno itself
sets no convention, so this is the house one:

```
<api.collection>/
  bruno.json
  environments/local.bru      base URL from the profile's runtime.baseUrl; secrets under vars:secret
  <resource>/<endpoint>/*.bru one folder per endpoint, seq-ordered
  .env.sample                 names only, never values
```

- **PR body** gets a `## API contract` section: the folders added or changed,
  the exact `bru run` command and its pass line
  (`Status ✓ PASS | Requests N | Assertions N/N`), and the Schemathesis gate
  command with its seed and summary line.
- During a playbook run, qa writes both JUnit reports to `.graph/<run>/qa/`.

## How it runs

Against the stack the profile's `runtime` block stands up (see
`qa-verification`), never against a shared or production environment:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT/<api.collection>"
bru run <folder> --env <api.env> --env-var TOKEN="$TOKEN" \
  --reporter-junit "$REPO_ROOT/.graph/<run>/qa/bru-<folder>.xml" \
  --reporter-skip-all-headers
echo "exit=$?"
```

One `--env-var` per token name in the profile's `runtime.env`: an unbound
`{{TOKEN}}` is sent as the literal text and fails every authenticated request
for a reason that is not a code defect. The report path is absolute because bru
runs from the collection directory.

Exit code is the gate (0 pass, 1 any failed assertion). Read the output; a run
that prints no assertions asserted nothing.

Then Schemathesis, per `schemathesis`: the gate checks
(`not_a_server_error,response_schema_conformance`) as pass/fail, then the full
default set report-only, whose failures are spec drift, written as Important
findings to `.graph/<run>/qa-findings.json` for the fix loop.
Both only against the disposable stack - it sends ~1,000 generated requests,
writes included.

## Who does what

| Role | Duty |
| --- | --- |
| planner | every task touching an API surface gets the criteria "Bruno suite under `api.collection` covers the cases in `api-contract`, runs green against `runtime`" and "Schemathesis gate checks pass against `runtime`" |
| implementer | keeps the schema current, writes the requests with the code, test-first where it can (the request goes red before the handler exists); runs the Bruno folder and the Schemathesis gate locally before `DONE`, and lists both commands and results in the report |
| reviewer | API diff with no collection change and no stated reason = **Blocking** (stated house rule); an endpoint whose returned statuses are missing from the schema, a request asserting only status, or a missing auth case = Important |
| qa | runs the touched Bruno folders, then the whole collection, then Schemathesis (gate, then drift report-only) against the running stack; a failed request or gate check is a `FAILED` row with the report path and seed; drift goes to `.graph/<run>/qa-findings.json` as Important findings |

## Anti-patterns

- Asserting `res.status eq 200` only. Failure: an endpoint returning 200 with an
  error envelope, or with a field silently dropped, passes forever.
- Running the suite against a shared staging stack. Failure: another branch's
  data makes the run flaky, and a write test mutates someone else's state.
- Deleting or skipping a failing request to get green. Failure: the regression
  ships and the suite now lies.
- A token in a committed `.bru` or environment file. Pass it with `--env-var`.
- Running Schemathesis against anything but the disposable `runtime` stack.
  Failure: ~1,000 generated writes in shared data.
