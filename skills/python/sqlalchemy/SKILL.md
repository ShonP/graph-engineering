---
name: sqlalchemy
description: Use when writing or reviewing async SQLAlchemy - engine and session wiring, the transaction a request runs in, a test fixture that rolls writes back, Alembic migrations, psycopg3 connection and TLS, or a table polled by a relay or worker. Covers session discipline, create_savepoint, libpq keyword DSNs and their two refusals, lock_timeout, the cursor trap that loses rows, and instrumenting an async engine.
license: MIT
---

# SQLAlchemy (async, psycopg3, Alembic)

Written for **SQLAlchemy 2.0.54** (PyPI, published 2026-09-15), **psycopg 3.3.6**
(2026-09-18), **alembic 1.20.0** (2026-09-11) and
**opentelemetry-instrumentation-sqlalchemy 0.65b0** — the versions `forge-libs` pins
with `==`. Docs fetched 2026-09-23, all HTTP 200:

- https://docs.sqlalchemy.org/en/20/orm/session_transaction.html - "Transactions and Connection Management"
- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html - "Asyncio Integration"
- https://docs.sqlalchemy.org/en/20/core/engines.html - "Engine Configuration"
- https://docs.sqlalchemy.org/en/20/core/pooling.html - "Connection Pooling"
- https://www.psycopg.org/psycopg3/docs/api/conninfo.html - "psycopg.conninfo"
- https://www.postgresql.org/docs/current/libpq-ssl.html - "SSL Support"
- https://www.postgresql.org/docs/current/functions-admin.html - "System Administration Functions"
- https://alembic.sqlalchemy.org/en/latest/cookbook.html - "Cookbook"
- https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html

Measured in-repo, rung 1 — these are verdicts from live runs, not docs claims:
`docs/adr/0016-outbox-relay-under-crash.md` §§5, 10 (the cursor trap and the poll);
`docs/adr/0017-sdk-integration-tier.md` §3 (psycopg3 on CNPG certificates, with libpq's
exact refusals) and §4 (the async savepoint recipe);
`docs/adr/0018-sdk-observability-contract.md` §5 (instrumenting an async engine).

## When to apply

- Building or changing an engine, a session, or the transaction a request runs in.
- A pytest fixture that must leave the database as it found it.
- Any Alembic migration, `env.py`, or the job that runs `upgrade head`.
- A connection string, TLS material, or a certificate-authenticated role.
- A table polled by a relay, worker or scheduler.

## Rules

### Session and transaction discipline

- **One transaction per unit of work**, opened with `AsyncSession.begin()`: it commits when
  the block exits cleanly and rolls back when it raises. Do not hand-roll commit/rollback
  around a bare session. https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- **`expire_on_commit=False` on an async session.** With the default, an attribute read after
  commit triggers a lazy refresh on a closed session, which in async SQLAlchemy surfaces as
  `MissingGreenlet` a long way from its cause.
  https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **A FastAPI `yield` dependency commits AFTER the response is on the wire.** The exit stack
  closes once the route's response has been sent, so a serialization failure, a deferred
  constraint or the database going away between the last statement and the COMMIT leaves the
  caller holding a 200 for work that did not land. This is the mainstream pattern and it is
  fine for writes the caller need not confirm; **a handler whose caller must be told the
  commit succeeded opens its own session inside the handler body** and returns after the
  block. Know which one you are writing.
- **Never swallow the exception in a session dependency.** `except: await session.rollback()`
  with no `raise` turns a failed write into a success at the call site. Roll back and re-raise,
  or let the context manager do both.
- **Session-scoped state on a pooled connection is the next request's problem.** Anything set
  with `SET` rather than `SET LOCAL` outlives the transaction and the next caller served by
  that connection inherits it. For `set_config`, the third argument `is_local` must be `true`.
  https://www.postgresql.org/docs/current/functions-admin.html
- **Bind every value, including ones that are not attacker-chosen today.** `text()` with an
  f-string or `%` is an injection the day something else flows into it; a bound parameter is
  a value forever. A useful house check is a grep for `f"` and `%` near `text(` that has to
  come back empty — a rule that needs a judgement call about which interpolation is safe is
  not a rule.

### Rolling writes back in tests - `create_savepoint`

Measured, ADR 0017 §4 (VALIDATED).

- The 2.0 recipe: open an `AsyncConnection`, begin a transaction on it, bind an
  `AsyncSession` to that connection with **`join_transaction_mode="create_savepoint"`**, and
  roll the **outer** transaction back in teardown. The session's own
  begin/commit/rollback become SAVEPOINTs, so a test may roll back and write again and the
  outer transaction survives. https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- **No `after_transaction_end` listener.** The 2.0 docs say those handlers "are no longer
  required"; the older recipe most tutorials still show re-introduces the bug class the
  library fixed.
- **The docs give the recipe in its SYNC form only.** Every step of the async version must be
  awaited, and the failure when one is not is
  `AsyncContextNotStarted: AsyncTransaction context has not been started and object has not
  been awaited.` (SQLAlchemy discussion #10126). Keep a live test row that asserts this
  **error type** — not merely that something raised — so the warning cannot go stale.
- **Prove the teardown with a control.** A row asserting "the next test sees 0 rows" means
  nothing unless another row proves a committed write IS visible; otherwise a broken count
  query passes both. And count the leak from a **separate connection**, after the raising
  one is closed.

### psycopg3, DSNs and TLS

- **One driver for both engines.** psycopg3 serves the async engine and Alembic's sync one
  because libpq keywords pass straight through. asyncpg needs a hand-built
  `ssl.SSLContext` and, being asyncio-only, forces a second driver for `alembic upgrade head`
  (ADR 0017 §3).
- **Build the DSN from keywords, never by splicing a string** —
  `psycopg.conninfo.make_conninfo(**params)`. https://www.psycopg.org/psycopg3/docs/api/conninfo.html
- Certificate auth is `sslmode=verify-full` with `sslrootcert`, `sslcert`, `sslkey` and
  `connect_timeout`, and **no password**. https://www.postgresql.org/docs/current/libpq-ssl.html
- **libpq refuses a group-readable private key**, which is exactly what a Kubernetes Secret
  volume gives you at its default 0644. Copy the key to a **0600** file at startup and point
  `sslkey` at the copy. Do not "fix" it with `defaultMode` in the manifest: that hides the
  requirement rather than meeting it, and production has to do the copy anyway.
- **Assert the SPECIFIC libpq text, never a bare `except`.** The two measured refusals
  (ADR 0017 §3), verbatim:
  - wrong `sslrootcert`: `SSL error: certificate verify failed`
  - 0644 key: `private key file "..." has group or world access; file must have permissions
    u=rw (0600) or less if owned by the current user, or permissions u=rw,g=r (0640) or less
    if owned by root`
  A row that passes on any exception proves nothing: pointed at a *missing* root certificate
  the first case raises `root certificate file "..." does not exist`, and against a
  nonexistent database the second raises `FATAL: database "..." does not exist`. Both used to
  be reported as refusals that proved something.
- **Re-raise the SDK's own error AFTER leaving the `except` block.** libpq's text carries the
  server address and the key's path, and an error tracker serialises the whole chain.
  `raise ... from None` is not enough: it sets `__suppress_context__` while `__context__`
  still holds the object. Build the message inside the block, leave it, then raise.
- `pool_pre_ping=True` so a connection killed by a failover or an idle timeout is discovered
  and replaced rather than raised at the caller.
  https://docs.sqlalchemy.org/en/20/core/pooling.html

### Alembic

- **`SET lock_timeout` before any migration runs.** A migration that needs an ACCESS
  EXCLUSIVE lock otherwise queues behind a long read and blocks every writer behind it; with
  a timeout, PostgreSQL cancels the statement instead and the deploy fails fast and loud.
  Put it in `env.py`, on the connection, before `run_migrations()`.
  https://www.postgresql.org/docs/current/runtime-config-client.html
- When it fires, PostgreSQL raises SQLSTATE `lock_not_available` and **the migration's
  transaction is aborted** — report which backend held the lock rather than just the timeout.
- `env.py` opens **one sync psycopg connection over the same DSN** as the app's async engine.
  Same driver, same keywords, same TLS material.
- Migrations run as their own job before the app starts, not from application startup.

### Polling a table - the cursor trap

Measured, ADR 0016 §5, and the reason this section exists at all.

- **Never add `AND id > :last_seen` to a poll.** Transaction A inserts a lower id and stays
  open; B inserts a higher id and commits; the poll publishes B and advances the cursor past
  A; A then commits and **is never seen by anything, ever**. Measured as a row that goes from
  green to permanently lost.
- **UUIDv7 does not save you.** The id is minted in the application, before COMMIT, exactly
  as a sequence value is — time ordering of ids is not commit ordering.
- **Poll by STATE, not by cursor**, and let the row's own columns say whether it is done:
  `WHERE published_at IS NULL AND dead_at IS NULL AND next_attempt_at <= now()
  ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED`. Put the comment naming this trap at the
  query site, pointing at the measurement.
- Index the predicate the poll actually uses — a **partial** index matching the WHERE clause
  keeps the tick an index scan instead of a seq scan that grows with every completed row.
- Guard each terminal write on the row's own state (`WHERE id = :id AND published_at IS
  NULL`) so a superseded worker changes nothing.
- `SKIP LOCKED` gives you concurrency and takes ordering: **across workers there is no order
  at all**, and after a crash a batch is re-read from the top, so consumers must be
  order-independent as well as idempotent (ADR 0016 §8).

### Logging and instrumentation

- **Instrument `engine.sync_engine`, not the `AsyncEngine`.** Passing the async engine
  instruments nothing **and raises nothing** — the failure is silent and the first symptom is
  an empty trace (ADR 0018 §5):
  `SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)`.
- **SQLAlchemy's `Engine` logger prints every statement AND its bound parameters at INFO.**
  SQLAlchemy sets that logger's level itself at import, but only `if rootlogger.level ==
  logging.NOTSET`, once, and never again — so a service that later configures logging from a
  dict, or a test that restores a level snapshot, silently turns statement logging back on.
  With a root-level interceptor installed, every bound parameter becomes a structured log
  line in the log store. Keep an idempotent `logging.getLogger("sqlalchemy").setLevel(WARNING)`
  and call it after SQLAlchemy is loaded.
- `echo=True` is the same leak with a friendlier name. Not in any shipped configuration.

## Anti-patterns

- **`AND id > :last_seen` in a relay or poll.** Silently drops rows committed out of id
  order. There is no version of this that is safe with UUIDv7.
- **A session dependency that rolls back and does not re-raise.** Turns a failed write into a
  200.
- **`expire_on_commit` left at its default on an async session.** `MissingGreenlet`, far from
  the cause.
- **`except Exception: pass` (or any bare assertion) on a TLS or connection test.** Two
  different misconfigurations both "pass". Assert the substring.
- **`raise SdkError(...) from None` around a libpq error.** `__context__` still holds the
  original, and a serialiser that walks the chain publishes the DSN and the key path.
- **`sslmode=require`.** It encrypts and verifies nothing; `verify-full` is the only setting
  that authenticates the server.
- **A Secret volume `defaultMode` instead of a 0600 copy.** Hides a requirement production
  still has.
- **Migrations with no `lock_timeout`.** One long-running read turns a deploy into an outage.
- **`SQLAlchemyInstrumentor().instrument(engine=async_engine)`.** No spans, no error.
- **`echo=True`, or trusting SQLAlchemy to keep its logger quiet.** Bound parameters — which
  are caller data — into the log store.

## Verify

```bash
# 1. Versions the rules were written against.
uv run python -c 'import sqlalchemy, psycopg, alembic; print(sqlalchemy.__version__, psycopg.__version__, alembic.__version__)'
# expect: 2.0.54 3.3.6 1.20.0

# 2. No cursor trap anywhere. Expect no output.
grep -rn 'id > :\|id > %' src/

# 3. No SQL built by interpolation. Expect no output.
grep -rnE 'text\(\s*f"|text\(\s*".*%' src/

# 4. The async engine is instrumented through its sync engine. Expect sync_engine on the line.
grep -rn 'SQLAlchemyInstrumentor().instrument' src/
# expect: ...instrument(engine=<engine>.sync_engine...)

# 5. Statement logging is off, so bound parameters cannot reach the log store.
uv run python -c 'import logging, sqlalchemy; import <your_package>.db; print(logging.getLogger("sqlalchemy").level)'
# expect: 30 (WARNING). 0 means NOTSET and every statement is being logged at INFO.

# 6. Migrations set a lock timeout before running. Expect a hit in env.py.
grep -rn 'lock_timeout' alembic/env.py

# 7. The savepoint fixture really rolls back: run the suite twice in one session.
uv run pytest tests/ -q
# expect identical results both times; a row count that grows between runs means the
# outer transaction is being committed somewhere.
```
