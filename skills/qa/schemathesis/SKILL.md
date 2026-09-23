---
name: schemathesis
description: Use when an API has an OpenAPI or GraphQL schema and needs the cases nobody wrote down - property-based and stateful tests generated from the schema, run against the live stack. Covers the run command, which checks gate a merge and which are spec drift, auth, reproducibility, reports, and why it only ever runs against a disposable stack.
license: MIT
---

# Schemathesis

Sources (fetched 2026-09-23):

- https://schemathesis.readthedocs.io/en/stable/ - overview, supported specs
- https://schemathesis.readthedocs.io/en/stable/reference/cli/ - `st run` flags, exit codes, `schemathesis.toml`

Version: written against `schemathesis` 4.28.0 (`uvx schemathesis --version`,
2026-09-23). Supports OpenAPI 2.0, 3.0, 3.1, 3.2 and GraphQL.

Bruno (`bruno`, `api-contract`) proves the cases someone thought of. This proves
the ones nobody did: it generates requests from the schema - boundary values,
wrong types, missing fields, chained create-then-read workflows - and checks
every response. The two are complements; neither replaces the other.

## When to apply

- The qa node of any run whose diff touches an API surface and the repo serves
  an OpenAPI/GraphQL schema (`api-contract` requires one).
- An implementer finishing an API task, as the last local check before `DONE`.
- Never against a shared, staging or production environment - see Safety.

## Rules

**The run**

```bash
# BASE_URL = runtime.baseUrl; the schema is api.schema (a path under it, or a repo file)
uvx schemathesis run "$BASE_URL/openapi.json" -u "$BASE_URL" \
  -H "Authorization: Bearer $TOKEN" \
  --checks not_a_server_error,response_schema_conformance \
  --seed "$SEED" -n 50 \
  --report junit --report-junit-path "$REPO_ROOT/.graph/<run>/qa/schemathesis.xml"
```

- The schema argument is a URL or a file path; `-u/--url` is the base URL the
  requests go to. (reference/cli)
- `-H NAME:VALUE` per header, repeatable; `-a USER:PASS` for basic auth. The
  token comes from the environment, never from a committed file. Output masks
  it: the reproduction curl prints `Authorization: [Filtered]`.
- `--seed` makes a run reproducible. Always pass one and print it in the report,
  so a failure can be replayed exactly (`st replay <test-case-id>` is printed
  per failure too).
- `-n/--max-examples` caps cases per operation; 50 ran ~1,000 cases over three
  operations in ~3s in the spike below. Raise it for a nightly run, not a PR.
- Narrow with `--include-path`, `--include-method`, `--include-tag`,
  `--include-operation-id` (and the `--exclude-*` mirrors) to the operations the
  diff touched when the schema is large; run everything when it is not.
- Phases are `examples, coverage, fuzzing, stateful`; all run by default.
  Stateful is the one that chains operations using the schema's links and is
  where cross-endpoint bugs surface. Keep it on.
- Config lives in `schemathesis.toml` in the repo (found in the cwd and its
  parents); prefer it over long command lines once a repo settles on flags.

**What gates, what is drift**

Exit codes: `0` all checks passed, `1` at least one check failed, `2` the run
aborted on a config or schema error. (reference/cli) `2` is `BLOCKED`, never
`PASS`.

| Check | Class | Why |
| --- | --- | --- |
| `not_a_server_error` | **gate** (Blocking) | a 5xx on generated input is a real bug, full stop |
| `response_schema_conformance` | **gate** (Blocking) | the response breaks the documented contract a client codes against |
| everything else in the default set - undocumented status code, missing auth header not rejected with 401/403, and the rest | **drift** (Important, to `qa-findings.json`) | the code and the spec disagree; fix whichever is wrong, usually the spec |

Run the gate checks as the pass/fail command: they decide the qa row. Run the
full default set once more, report-only, and write each unique failure as an
Important finding - operation, check, seed, reproduction curl - to
`.graph/<run>/qa-findings.json` in the `review-protocol` format. The fix node
reads that file beside the reviewer's `findings.json`, so drift goes through
the same fix loop as any Important finding (usually fixed on the schema side:
`responses=` on the route, a real auth dependency), and whatever survives three
rounds is listed for the owner at the merge gate. It does not fail the qa row,
and it is never silently dropped.

Framework note: FastAPI's generated schema documents only the success status
and 422. An out-of-the-box FastAPI app therefore always shows undocumented
401/404/400 drift and "missing header not rejected" (FastAPI answers a missing
required header with 422, not 401). The fix is `responses={401: ..., 404: ...}`
on the route and a real auth dependency, not a suppressed check.

**Safety**

- Schemathesis sends ~1,000 requests including writes, malformed bodies and
  chained deletes. Run it only against the disposable stack the profile's
  `runtime` block stands up, with `runtime.down` wiping state (`down -v`).
- Never point it at a URL that is not `runtime.baseUrl` on a stack you started.
  A shared environment gets polluted data and, with a real token, real side
  effects.
- A `--workers` value above 1 is for read-heavy schemas; stateful bugs are
  easier to read single-worker.

## Anti-patterns

- Gating on the full default check set. Failure: every FastAPI repo is red on
  day one for spec drift, the gate gets disabled, and the 5xx it would have
  caught ships.
- `--exclude-checks not_a_server_error` to get green. Failure: the one check
  that is always a real bug is off.
- No `--seed`. Failure: a failure that does not reproduce on the next run gets
  called flaky and waved through.
- Running against staging "because the stack is heavy". Failure: generated
  writes land in shared data.
- Treating exit 2 as a pass because nothing failed. Failure: the schema did not
  load, so nothing was tested.

## Verify

Spike 2026-09-23, schemathesis 4.28.0, a three-route FastAPI app
(`/health`, `POST /items` with a bearer header, `GET /items/{id}`) with a planted
bug - `100 // item.qty` on a `qty: int = Field(ge=0)`:

```
# planted bug, gate checks
$ uvx schemathesis run .../openapi.json -u ... -H "Authorization: Bearer secret" \
    --seed 42 -n 50 --checks not_a_server_error
  ❌ Server error: 1
  Reproduce with:
    curl -X POST -H 'Authorization: [Filtered]' -H 'Content-Type: application/json' \
      -d '{"name": "0", "qty": 0}' http://127.0.0.1:8765/items
  992 generated, 1 found 1 unique failures
exit=1

# same bug, full default checks: the 500 plus drift
  ❌ Server error: 1
  ❌ Missing header not rejected: 1
  ❌ Undocumented HTTP status code: 3
exit=1                      (JUnit report written with --report junit)

# bug fixed (Field(ge=1)), gate checks
  716 generated, 716 passed
  No issues found
exit=0

# bug fixed, full default checks: drift only
  ❌ Missing header not rejected: 1
  ❌ Undocumented HTTP status code: 2
exit=1
```

Expected: the gate command exits 1 on a planted 5xx and 0 once it is fixed,
while the full set keeps reporting drift - which is exactly why the two are run
separately.
