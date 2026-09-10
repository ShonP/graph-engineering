---
name: bruno
description: Use when a repo holds .bru files, an opencollection.yml or a bruno.json, when adding API contract checks to the qa node, or when running an API collection in CI. Covers collection layout, environments and secrets, assertions and tests, reporters as evidence artifacts, and the bru run flags.
license: MIT
---

# Bruno

Sources (fetched 2026-09-10 with curl, all HTTP 200):

- https://docs.usebruno.com/bru-cli/overview - "Bruno CLI - Bruno Docs"
- https://docs.usebruno.com/bru-cli/runCollection - "Command Examples - Bruno Docs"
- https://docs.usebruno.com/bru-cli/commandOptions - "Command Options - Bruno Docs"
- https://docs.usebruno.com/secrets-management/overview - "Secret Management - Bruno Docs"
- https://docs.usebruno.com/secrets-management/secret-variables - "Secret Variables - Bruno Docs"
- https://docs.usebruno.com/secrets-management/secret-masking - "Secret Masking in Reports - Bruno Docs"
- https://docs.usebruno.com/secrets-management/dotenv-file - "DotEnv File - Bruno Docs"
- https://docs.usebruno.com/testing/tests/introduction - "Testing - Bruno Docs"
- https://docs.usebruno.com/testing/tests/assertions - "Assertions - Bruno Docs"

Version: written against `bru` CLI 4.1.0 (installed 2026-09-10 for the Verify
run). Two version facts the docs flag: from v3.0.0 the sandbox defaults to
`safe`, so a collection needing external npm packages or filesystem access must
pass `--sandbox=developer`; v4 changed the JUnit `classname` attribute, which
matters to anything parsing older reports.

## When to apply

- Any `*.bru` file, `bruno.json`, `opencollection.yml` or `environments/` directory.
- Adding an API contract or smoke check to the qa node of a run.
- Wiring a collection into CI, Docker or a task runner.
- Deciding how a test gets its token or base URL.

## Rules

**Collection layout**

- A collection is a directory with `bruno.json` at its root, requests as `.bru`
  files, and environments under `environments/`. `bru run` from that directory
  runs everything; `bru run <folder>` runs one folder, which is how a single
  feature's checks stay runnable on their own.
  (https://docs.usebruno.com/bru-cli/runCollection)
- Order is explicit: each request's `meta` block carries `seq`. If a check
  depends on an earlier request, that dependency is in the sequence, not in
  luck. (https://docs.usebruno.com/bru-cli/runCollection)
- Tag requests and select with `--tags` and `--exclude-tags` (comma separated)
  so a smoke subset and the full suite live in one collection.
  (https://docs.usebruno.com/bru-cli/runCollection,
  https://docs.usebruno.com/bru-cli/commandOptions)
- Data-driven runs take `--csv-file-path` or `--json-file-path`, and
  `--iteration-count` repeats a run. Prefer a data file over copy-pasted
  requests. (https://docs.usebruno.com/bru-cli/runCollection)
- `--parallel` exists but sequential is the default; only go parallel when no
  request depends on another's state.
  (https://docs.usebruno.com/bru-cli/runCollection)

**Environments and secrets**

- One environment per target, selected with `--env <name>`, or pointed at
  directly with `--env-file <path.bru|path.json>`. Base URLs belong there, not
  hardcoded in requests. (https://docs.usebruno.com/bru-cli/runCollection)
- Secrets are never committed. The docs are explicit that variables marked as
  secret in the app are not persisted to disk for the CLI, and are passed at
  runtime with `--env-var NAME=value` (or `--global-env-var`, which requires
  `--global-env`). (https://docs.usebruno.com/bru-cli/runCollection)
- Declare secret-bearing variables under `vars:secret` in the environment file
  (`vars:secret [ TOKEN ]`); those values are not saved to the environment file,
  so the collection stays safe to check in.
  (https://docs.usebruno.com/secrets-management/secret-variables)
- Two masking mechanisms exist and only one of them is yours. Bruno always masks
  a fixed list of sensitive header names (`authorization`, `x-api-key`,
  `cookie`, `client-secret` and others) whatever the value, and separately masks
  every value of a variable marked secret. Verified 2026-09-10 with bru 4.1.0,
  with the two effects separated: the same secret variable rendered into
  `X-Trace-Id`, a header on nobody's list, still came out `********`, while an
  ordinary variable in `X-Plain-Key` came out verbatim. So a credential in a
  custom header is protected only if you declared the variable secret.
  (https://docs.usebruno.com/secrets-management/secret-masking)
- The other supported local shape is a `.env` file at the collection root,
  referenced as `{{process.env.NAME}}` from the environment file. If you use it:
  `.env` goes in `.gitignore`, and a `.env.sample` without values documents the
  shape. (https://docs.usebruno.com/secrets-management/dotenv-file)
- Quote any `.env` value containing `#`, a newline, a quote or a backslash.
  `PASSWORD=ABC#DEF` parses as `ABC`, which fails later as a confusing auth
  error rather than a parse error.
  (https://docs.usebruno.com/secrets-management/dotenv-file)
- An external secret manager (Vault, AWS Secrets Manager, Azure Key Vault) is
  wired through an `externalSecrets` block plus `--secrets-env-file`; those
  values are injected at runtime and never written to disk or printed in logs.
  (https://docs.usebruno.com/bru-cli/commandOptions)

**Assertions and tests**

- Assert on values, not only on status. The declarative `assert` block takes an
  expression, an operator and a value (`res.status eq 200`,
  `res.body.user.profile.name eq John`, `res.body.users isNotEmpty`), including
  nested paths and array indexes.
  (https://docs.usebruno.com/testing/tests/assertions)
- Anything needing logic goes in a `tests` block, which is Chai `expect`
  syntax over `res.getStatus()` and `res.getBody()`.
  (https://docs.usebruno.com/testing/tests/introduction)
- For a contract check, assert the shape, not one field: `jsonBody` compares a
  body, a nested path, or a path and value, and `jsonSchema` validates the
  response against a JSON Schema document (Ajv, drafts 04 through 2020-12).
  That is what makes the collection a contract test rather than a ping.
  (https://docs.usebruno.com/testing/tests/introduction)
- Assert negatives too: `expect(res.getBody()).to.not.have.jsonBody("internal.debugInfo")`
  is how you prove an endpoint does not leak a field.
  (https://docs.usebruno.com/testing/tests/introduction)
- `--tests-only` runs just the requests that carry tests or active assertions,
  and `--bail` stops at the first failure. Use `--bail` for a gate, omit it when
  you want the full failure picture.
  (https://docs.usebruno.com/bru-cli/commandOptions)

**Evidence and CI**

- The artifact is a report file, not a screenshot:
  `--reporter-junit <file>`, `--reporter-json <file>`, `--reporter-html <file>`,
  and the three can be combined in one run.
  (https://docs.usebruno.com/bru-cli/commandOptions)
- Keep credentials and payloads out of published artifacts with
  `--reporter-skip-all-headers`, `--reporter-skip-headers <list>`,
  `--reporter-skip-request-body`, `--reporter-skip-response-body` or the
  `--reporter-skip-body` shorthand. Masking of secret variables is a second
  layer, not a substitute.
  (https://docs.usebruno.com/bru-cli/commandOptions)
- `-o/--output` and `-f/--format` are deprecated in favour of the reporter
  flags; do not write new CI steps against them.
  (https://docs.usebruno.com/bru-cli/commandOptions)
- The exit code is the gate. Verified with bru 4.1.0: a passing run exits 0, a
  failing assertion exits 1, with or without `--bail`. CI reads the exit code;
  the report is for humans.
  (https://docs.usebruno.com/bru-cli/overview)
- Leave the sandbox on `safe`. `--sandbox=developer` re-enables external npm
  packages and filesystem access, which is a real privilege for a test runner
  parsing responses from a service under test. Only pass it with a reason.
  (https://docs.usebruno.com/bru-cli/overview,
  https://docs.usebruno.com/bru-cli/commandOptions)
- `--insecure` and `--ignore-truststore` disable the checks you are presumably
  testing. Use `--cacert` (and `--client-cert-config` for mTLS) instead; the CLI
  does not read certificates from the desktop app's preferences.
  (https://docs.usebruno.com/bru-cli/commandOptions)

## Anti-patterns

- A token, cookie or API key written into a `.bru` file or a committed
  environment file. Failure: a live credential in git history. Pass it with
  `--env-var` at runtime.
- Using an ordinary variable for a credential because "it is only staging", or
  assuming the header name saves you. Failure: verified above, an ordinary var
  in a non-listed header is written to the JSON, HTML and JUnit reports
  verbatim, so the run's own artifact leaks it.
- A screenshot of the GUI runner as QA evidence. Failure: nothing is machine
  checkable, nothing gates the merge. Attach the JUnit or JSON report.
- A request with no `assert` and no `tests` block. Failure: the collection
  proves only that a socket opened.
- Asserting only `res.status eq 200`. Failure: an endpoint that returns 200 with
  an error envelope, or with a field silently removed, passes forever.
- Assuming a missing variable fails the run. Verified with bru 4.1.0: a
  `{{VAR}}` with nothing bound is sent as the literal `{{VAR}}` and the run
  still exits 0 if the assertions do not care. Assert on something only an
  authenticated, correct response contains.
- Deleting or skipping the failing request to get a green run. Failure: the
  regression ships and the suite now lies.
- `--sandbox=developer` or `--insecure` added to make a run pass. Failure: the
  test environment stops resembling production in exactly the dimension being
  tested.
- Publishing the HTML report from an authenticated run without the
  `--reporter-skip-*` flags. Failure: request bodies and headers become a
  public artifact.

## Verify

```bash
bru --version
bru run <folder> --env <env> --env-var TOKEN="$TOKEN" --reporter-junit results.xml
echo "exit=$?"; test -s results.xml
```

Run 2026-09-10, bru 4.1.0, two-request scratch collection against a local
server, with `TOKEN` declared under `vars:secret`:

```
health (200 OK) - 10 ms
Tests
   ✓ reports the service name
Assertions
   ✓ res.status: eq 200
   ✓ res.body.status: eq ok
missing (404 File not found) - 3 ms
Assertions
   ✓ res.status: eq 404
Status ✓ PASS | Requests 2 (2 Passed) | Tests 1/1 | Assertions 3/3
Wrote junit results to results.xml
exit=0

# same collection, one assertion flipped to an expectation the server fails
exit=1            (identical with and without --bail)

# JSON report headers: secret var in a listed and an unlisted header,
# ordinary var in an unlisted header
"Authorization": "Bearer ********"
"X-Trace-Id":    "********"
"X-Plain-Key":   "plain-visible-value"
```

Expected: exit 0 with every assertion listed, a non-empty report file, and no
credential in it. A run that passes without printing assertions is a collection
with nothing to assert.
