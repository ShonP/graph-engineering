# Changelog

Notable changes to the graph-engineering plugin. Skills vendored from upstream
keep their own `CHANGELOG.md` beside them; this file covers the plugin.

Releasing is the owner's: bump `version` in `.claude-plugin/plugin.json` and move
the entries below under that number. An entry sitting in Unreleased has not
shipped to any install yet — `claude plugin update` compares versions, not
commits.

## [Unreleased]

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
