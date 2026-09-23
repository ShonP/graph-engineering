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
  on a live cluster rather than from vendor-docs digests. Each claim carries the
  ADR section that measured it and a vendor URL with a version and a date.
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
  `**/{bus,events,messaging}/**`; `loguru` on `**/logging*.py`.
- **A uv-workspace fixture** under `hooks/tests/fixtures/workspace` — a root
  owning the three script names and a member declaring none.

### Changed

- **`hooks/scripts/resolve_touched_project.py` walks past a project file that
  declares neither `lint` nor `typecheck`**, continuing until one does or the
  project directory is reached. Previously it stopped at the nearest project
  file; in a uv workspace that is the member's scriptless `pyproject.toml`, so
  every edit under `packages/*/src/` resolved to a project with no scripts and
  the PostToolUse hook exited 0 **in silence** — the whole library quietly
  unlinted. A project file that cannot be read or parsed still stops the walk
  where it is, rather than letting an ancestor's scripts run against a file that
  ancestor does not own. `hooks/README.md` and `lint-touched-file.sh`'s header
  both stated the old rule and were corrected with it.
- **`skills/python/pydantic-house-rules`** — the `Verify` block now carries an
  executable recipe. The old check walked `src/` for a `@dataclass` whose
  preceding line held the exemption comment, which approximated a rule nothing
  enforced; it is replaced by the ruff `banned-api` ban, a fixture proving the
  rule fires (exit 1, `TID251`), and an explicit statement of the four spellings
  that reach a real dataclass past it. The framework-adapter section gains the
  `# noqa: TID251  # framework adapter exception: <call>` spelling.
- **`.claude-plugin/plugin.json`** lists `./skills/messaging` so the new group
  loads. `version` is deliberately unchanged.
