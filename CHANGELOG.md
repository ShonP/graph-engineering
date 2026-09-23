# Changelog

Notable changes to the graph-engineering plugin. Skills vendored from upstream
keep their own `CHANGELOG.md` beside them; this file covers the plugin.

Releasing is the owner's: bump `version` in `.claude-plugin/plugin.json` and move
the entries below under that number. An entry sitting in Unreleased has not
shipped to any install yet — `claude plugin update` compares versions, not
commits.

## [Unreleased]

## [0.9.0] - 2026-09-23

### Added

- **Four Python and messaging competencies**, written from what plan 6 measured
  on a live cluster rather than from vendor-docs digests. Each skill's header
  lists its sources, pinned to the version it was written against: a versioned
  docs path such as `docs.sqlalchemy.org/en/20/` or `loguru.readthedocs.io/en/0.7.3/`,
  the source at the release tag, or, for docs.nats.io, which has no versions,
  the `nats.docs` commit. Measured claims cite the ADR section by its
  location, `Equival-io/forge-platform` `docs/adr/`, a private repo, and the
  header says so. Every Verify recipe was run against forge-libs `552a9b9`,
  and each check shown to fail on a real violation. Sourcing pass:
  `docs/research/2026-09-23-python-skills-sourcing.md`.
  - `skills/python/ruff` — rule selection that survives a codebase, banning
    **symbols rather than modules** (a module ban also flags
    `from dataclasses import replace`, so it gets silenced on day one), the
    `extend-exclude` + `force-exclude: false` pair that lets a repo keep a
    deliberate red control, and per-file invocation for the edit hook.
  - `skills/python/sqlalchemy` — async session discipline, the
    `create_savepoint` test recipe with the async caveat the docs omit,
    psycopg3 on libpq keyword DSNs with both refusal texts verbatim, Alembic
    `lock_timeout`, **never `AND id > :last_seen` in a poll**, and
    `SQLAlchemyInstrumentor` on `engine.sync_engine`.
  - `skills/python/loguru` — the one-direction `InterceptHandler`, the frame
    walk a Sentry patch silently breaks, `log_config=None` (without it uvicorn's
    own `dictConfig` removes the interception and every server line arrives
    unparsed), INFO rather than DEBUG, and the `caplog` gap.
  - `skills/messaging/nats` — a new `messaging` group. `Nats-Msg-Id` and
    `duplicate_window`, **`stream=` mandatory on every nats-py subscribe**,
    per-stream `$JS.ACK`, `_INBOX.>` in every allow-list, order-independent
    handlers, and why a denied JetStream call is indistinguishable from a
    timeout.
- **Routing rows** for all four: `ruff` joins `**/*.py`; `sqlalchemy` on
  `**/{models,db,migrations}/**/*.py` and `**/alembic/**`; `nats` on
  `**/{bus,events,messaging}/**`, `**/nats*/**` and `**/nats*.{yaml,yml}` (the
  server config and the Stream/Consumer CRs); `loguru` on `**/logging*.py`.
- **Resolver fixtures** under `hooks/tests/fixtures`: `workspace/`, a uv
  workspace whose root owns the three script names, with one member that
  declares none and one whose `pyproject.toml` does not parse; and `mixed/`,
  a Python root that declares `lint`, with a `web/package.json` that declares
  only `build` and `test`.

- **`skills/process/api-contract`** — a house rule beside `ux-evidence`: every
  change to an API surface ships its Bruno requests in the same PR (happy path
  asserting values, auth, validation, edge, non-leak), qa runs them and then the
  whole collection, and the reviewer treats a missing suite as Blocking. Bruno
  documents no convention for where a collection lives in a repo, so the house
  one is the profile's `api.collection` (default `bruno/`). Routed by the new
  server-side API-surface rows described below. Sourcing: prior-art run 2026-09-23 (docs.usebruno.com,
  docs.docker.com compose `up`, devcontainers spec).
- **Profile `runtime` block** (`up`, `seed`, `port`, `health` {`url` |
  `command`, `expect`, `timeout`}, `baseUrl`, `down`, `env`, `none`) so qa
  stands any repo up itself. `none: "<reason>"` is for a repo with nothing to
  stand up (a library, a CLI, a plugin): qa verifies through its public surface
  instead, so a mandatory qa node does not trap those repos at `BLOCKED`.
  `up` mirrors `docker compose up --wait --wait-timeout`; `health.url` is polled
  with `curl --retry-connrefused --retry-all-errors`; `seed` has no analog in
  compose or devcontainer, so it is ours. devcontainer's lifecycle shape was
  rejected wholesale: it assumes every repo runs in a devcontainer and has no
  seed or health concept. Spiked 2026-09-23: curl 8.7.1 retries a refused
  connection and exits 7; Compose v2.40.3 has `--wait` and `--wait-timeout`.
  `/graph-init` now proposes the block and the API rows from what the repo holds.
- **`skills/qa/schemathesis`** — property-based and stateful API tests
  generated from the served OpenAPI/GraphQL schema, the second layer of
  `api-contract` beside Bruno. Only `not_a_server_error` and
  `response_schema_conformance` gate; the rest of the default set runs
  report-only as spec drift (Important), because an out-of-the-box FastAPI app
  fails it on day one and a gate that is always red gets turned off. Spiked
  2026-09-23 with schemathesis 4.28.0 on a FastAPI app with a planted
  `100 // qty` bug: gate checks found it unaided (exit 1, reproduction curl
  printed), exited 0 once fixed (716/716), while the full set still reported
  drift (exit 1). Hurl was weighed as a Bruno replacement and rejected (no GUI,
  no native JSON Schema assertion, and the tested `bruno` skill already exists);
  Postman was rejected for cloud-workspace collections that cannot ship in a PR.
- **`api-contract` requires a served schema.** Every HTTP API serves OpenAPI
  (GraphQL: SDL), current in the same PR, with error statuses documented;
  profile `api.schema` names where.
- **API-surface rows are server-side only.** `routes/` and `handlers/` route
  `api-contract` only for server languages (py, go, java, kt, rb, php, cs);
  `routers/`, `controllers/` (and ASP.NET/Laravel `Controllers/`),
  `endpoints/` for those plus ts/js; NestJS
  `*.controller.ts`, Next.js `app/api/**/route.ts` and `pages/api/**`, and the
  spec files. A bare `**/routes/**` matched TanStack Router, Remix and
  SvelteKit `src/routes/`, Angular `app.routes.ts` and MSW `mocks/handlers/`,
  which would have made a route-component task demand a Bruno suite and a
  schema the SPA cannot serve. Checked with wcmatch on 25 paths, 12 of them
  frontend or unrelated negatives. `/graph-init` adds a row for TS server routes
  it finds by content.
- **qa gets its own compose project.** `runtime.up`/`down` use
  `docker compose -p ge-${GRAPH_RUN_ID}`, and the engine exports
  `GRAPH_RUN_ID` to qa. Spiked: `-p` overrides a top-level `name:` and
  namespaces project-scoped volumes (`ge-<id>_pgdata`), but it does NOT rename
  a volume or network with its own `name:`, a `container_name:`, or anything
  `external: true` - the review reproduced qa's app resolving `db` to the
  developer's database over a shared named network. So a repo using them
  commits a block-style `compose.qa.yaml` that renames each with
  `${GRAPH_RUN_ID}` and drops the externals (`!override`, `!reset null`),
  `/graph-init` proposes it, and qa runs a `compose config | jq` isolation
  check and refuses to start while it prints anything. Spiked: five leaks
  printed on the base file, none with the override, none on a plain file; the
  first draft's flow-style `{name: ge-${GRAPH_RUN_ID}_x}` example was itself a
  YAML parse error and is gone.
- **`.graph/<run>/qa-findings.json`.** Schemathesis drift, and anything else qa
  finds beside the criteria, is written there in the review-protocol format and
  read by the fix node beside `findings.json`; `--auto-merge` checks both.
- **The runtime template ships empty.** `/graph-init` fills what it detects;
  an empty required field is qa `BLOCKED` naming it. The health poll adds
  `--max-time 5 --retry-max-time <timeout>` (spiked: a listener that accepts
  and never answers now stops the poll at the budget instead of hanging), and
  `expect` is a raw substring, so the docs warn off JSON-spaced tokens.
- **qa's Bruno command passes tokens and hides headers.** One `--env-var` per
  name in `runtime.env` (an unbound `{{TOKEN}}` is sent literally),
  `--reporter-skip-all-headers`, and an absolute report path.
- **`runtime.port` and `runtime.health.expect`.** qa checks the port is free
  before `up` and the health body contains `expect`. The spike hit it: an
  unrelated process already on the port answered the health poll with 401 until
  the real server bound, and a status-only check would have gone green against
  the wrong service.
- **A `qa` node in the feature playbook**, parallel with review (both share
  `next: fix`). Its `FAILED` rows feed the fix loop beside review findings and
  are re-run each round; `BLOCKED` is a setup stop, not a fix-loop input, and
  the merge gate does not open on a run whose qa leg never ran. `--auto-merge`
  now also requires qa `PASS`.

### Changed

- **`hooks/scripts/resolve_touched_project.py` walks past a project file that
  declares neither `lint` nor `typecheck`, to the nearest ancestor of the SAME
  kind that declares one.** A directory holding a project file of another kind,
  or the project bound, ends the search, and the answer is the nearest project
  file, the same answer as before. Previously the walk always stopped at the
  nearest project file. In a uv workspace that is the member's scriptless
  `pyproject.toml`, so every edit under `packages/*/src/` resolved to a project
  with no scripts, and the PostToolUse hook exited 0 **in silence**: the whole
  library went unlinted. The same-kind limit keeps a scriptless
  `web/package.json` under a Python root from resolving to the root and
  running `uv run lint` on a `.tsx` file. A project file that cannot be read or parsed still stops the walk
  where it is, rather than letting an ancestor's scripts run against a file that
  ancestor does not own. `hooks/README.md` and `lint-touched-file.sh`'s header
  both stated the old rule and were corrected with it.
- **`skills/python/pydantic-house-rules`** — the `Verify` block now carries an
  executable recipe. The old check walked `src/` for a `@dataclass` whose
  preceding line held the exemption comment, which approximated a rule nothing
  enforced; it is replaced by the ruff `banned-api` ban, a fixture proving the
  rule fires (exit 1, `TID251`), and an explicit statement of the four spellings
  that reach a real dataclass past it. The framework-adapter section gains the
  `# noqa: TID251  # framework adapter exception: <call>` spelling, and
  `ruff --select PGH004` rejects a bare `# noqa`. Check 6 (every Temporal
  client passes the converter) now matches any call whose target **ends with**
  `Client.connect`, rather than only the exact text `Client.connect`. The exact
  match missed `temporalio.client.Client.connect(...)` and an aliased
  `client.Client.connect(...)`, so a bare client written that way passed.
- **`.claude-plugin/plugin.json`** lists `./skills/messaging` so the new group
  loads. `version` is deliberately unchanged.

### Removed

- **Content and social media leave the plugin; it is engineering only.** The
  `content-writer` and `media-producer` agents, the `content` skill group
  (`short-form-posts`, `short-attention-media`), the profile template's
  `content:` block and `publication` gate, and the `launch` / `content`
  playbooks from the plan. The roster is seven agents. `ux-evidence` keeps the
  two recording rules it borrowed from `short-attention-media` (cut every wait,
  ≤ 30s per flow) inline. Dated specs and plans under `docs/` still describe the
  old roster and are left as the record of what was decided then.
