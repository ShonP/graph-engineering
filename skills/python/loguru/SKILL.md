---
name: loguru
description: Use when configuring logging for a Python service - the sink, the level, the stdlib-to-loguru bridge, per-record context keys, or anything that has to arrive in a log store parsed and correlated with a trace. Covers the one-direction InterceptHandler, the frame walk a Sentry patch breaks, uvicorn's log_config, why the default level is INFO, and testing a logger pytest's caplog cannot see.
license: MIT
---

# loguru

Written for **loguru 0.7.3** (PyPI, published 2024-12-06 — still the latest release, and the
version `forge-libs` pins with `==`; uvicorn 0.53.0, sentry-sdk 2.69.2). Fetched 2026-09-23,
HTTP 200, each pinned to that version:

- https://loguru.readthedocs.io/en/0.7.3/overview.html - "Overview"
- https://loguru.readthedocs.io/en/0.7.3/resources/migration.html#replacing-caplog-fixture-from-pytest-library
- https://github.com/Delgan/loguru/blob/0.7.3/README.md - the maintainer's own
  `InterceptHandler`, README lines 309-336
- https://github.com/encode/uvicorn/blob/0.53.0/uvicorn/config.py - `LOGGING_CONFIG`
  (`"propagate": False`) and `Config.configure_logging()`

Measured in-house, rung 1. **ADR 0018** is `Equival-io/forge-platform`
`docs/adr/0018-sdk-observability-contract.md` (a private repo): §2 (SP3 — one line, once,
five keys; VALIDATED), §3 (the Sentry attribution finding SP3 could not make), §5 (the
contract as shipped). **forge-libs** is `Equival-io/forge-libs` @ `552a9b9` (also private):
`src/forge_sdk/{logging,_intercept,_tracker}.py`. "Measured" = a row watched going red.

## When to apply

- The module that configures logging for a service, worker or job.
- Bridging stdlib `logging` (uvicorn, SQLAlchemy, Temporal, httpx, every library) into loguru.
- Adding a field that must appear on every record, or correlating logs with traces.
- Starting an ASGI server, where the framework installs logging of its own.
- Writing a test that asserts something was logged.
- Reviewing a diff that touches sinks, levels, `propagate`, or a log-adjacent `dictConfig`.

## Rules

### One sink, structured, on stderr

- **`logger.remove()` first, then add exactly one sink.** loguru ships a default stderr
  handler; adding yours without removing it gives every line twice (`overview.html`).
- **`serialize=True`.** A collector parses JSON; it does not parse your format string. An
  unparsed line still arrives, which is what makes this failure quiet — it lands as text
  under the pod's name with no level, no service and no trace id.
- **Write to the process's stderr and let the platform collect it.** A service does not own a
  log file, its rotation or its retention.
- **`backtrace=False` and `diagnose=False` outside local development.** `diagnose=True`
  renders the *values* of the frame's locals into the traceback: it is a security control,
  not a preference. Measured caveat (ADR 0018 §2, defect 3): `diagnose` renders the names on
  the **source line**, so a credential held in a local variable while the raise happens a
  line later does not leak — a hostile test row that puts the secret in a local and raises on
  the next line passes for the wrong reason. Put the value on the raising line.

### The level is INFO, and the reason is a bill

- **Default to `INFO`, never `DEBUG`**, with an environment variable to override. Measured
  (ADR 0018 §5): interception is global, so `DEBUG` is `DEBUG` for *every* library on the
  root logger. Six spike runs shipped **1585** lines, the overwhelming majority
  `httpcore._trace` DEBUG records — one per TLS handshake step, per request, each a full JSON
  record with five structured-metadata fields. At service scale that is the log bill and the
  retention window.

### The stdlib bridge goes ONE direction

- **Install loguru's `InterceptHandler` on the root logger** and let every stdlib logger
  propagate into it: `logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)`.
  Copy the handler from the maintainer's README rather than adapting it — the frame walk is
  easy to get subtly wrong.
- **Never install a handler that propagates loguru records back into stdlib.** Together with
  `InterceptHandler` the two are a loop. Measured: it does not hang and does not
  `RecursionError` — loguru's `Handler` refuses to re-enter its own lock from the same thread
  (the 0.6.0 deadlock guard), so the second pass raises, is caught, and unwinds. The
  observable is **exactly two** emissions per call, in process and in the log store. A
  duplicate that is bounded at 2 looks like a quirk, not a bug, which is why it survives.
  The configure function must have no parameter that installs one.
- **Keep a negative control.** A row that asserts one emission is only evidence if another row
  shows the loop producing two.

### The frame walk, and the patch that breaks it

Measured, ADR 0018 §3 — the finding a logging-only spike cannot make.

- `InterceptHandler` walks back out of the `logging` machinery by comparing each frame's
  filename to `logging.__file__`. **Sentry's `LoggingIntegration` monkey-patches
  `logging.Logger.callHandlers`**, and that patch is not in `logging.__file__`, so the walk
  **stops on it**. With an error tracker initialised, every intercepted stdlib line is
  attributed to `sentry_sdk.integrations.logging:sentry_patched_callhandlers` — the code
  namespace, function and line number all naming Sentry's patch instead of the code that
  logged, for every uvicorn, SQLAlchemy and Temporal line in every service.
- **The fix is one line in the walk's condition:** skip `logging.__file__` *and* a named
  tuple of plumbing modules. Keep the verbatim walk available behind a flag so a test can
  measure **both directions in one process** — otherwise the control cannot fail.
- This is a deliberate deviation from a published recipe. Mark it as such in the source, or
  the next person "fixes" it back.

### Context keys

- **Stamp the per-record fields with `logger.configure(patcher=...)`**, read from the active
  span **at emit time**. The keys, exactly: **`trace_id`, `span_id`, `request_id`,
  `service`, `version`** (forge-libs `logging.py`, `EXTRA_KEYS`). A patcher runs per record;
  binding once at startup captures a span that has since ended.
- **Write into `record["extra"]` rather than replacing it**, so `logger.bind()` and
  `logger.contextualize()` keep working. `contextualize()` is the request-scope mechanism;
  a patcher that clears the dict deletes a documented feature to satisfy a key count.
- **Outside a span, emit the zero ids** (32 and 16 zeros; `request_id` is `""` outside a
  request, never `None`) rather than omitting the keys or
  writing empty strings. Measured: the collector's trace parser accepts the zero id and logs
  no operator error, while omitting the keys makes the key set four on some lines and five on
  others, and an empty string is unparsable in a field guarded on key presence.
- Know that a key a caller binds is a **sixth** key and reaches the log store as an unplanned
  structured-metadata field. That is a property to measure, not to silently allowlist away.

### The server undoes all of it - `log_config=None`

- **uvicorn is the duplicate-and-disappearance risk, not the propagating handler.** Measured
  (ADR 0018 §2; `config.py` at 0.53.0): `Config.configure_logging()` calls
  `dictConfig(LOGGING_CONFIG)`, which attaches uvicorn's own handlers to `uvicorn` and `uvicorn.access` and sets
  `propagate: False`. After a default `uvicorn.run()` the interception is simply **gone** —
  lines never reach the root logger, so they are not duplicated; they arrive as **unparsed
  text with no trace id and no severity**. Measured: **0** JSON lines with the default config,
  2 with `log_config=None`.
- **Start the server with `log_config=None`.** It belongs to whichever module calls
  `uvicorn.run`/`Server`, and it is part of the logging contract even though it is not in the
  logging module. A test suite that only exercises the library half is green while the
  deployed service logs nothing usable — that is one layer of two, and it is a defect.
- **`dictConfig` is sticky for the life of the process.** `logging.basicConfig(force=True)`
  clears the **root** logger only. Once anything has built a uvicorn `Config`, a later
  reconfiguration in the same process does not take on uvicorn's loggers. Refuse the
  combination rather than documenting an order.

### Configure logging FIRST, and quiet the noisy talkers

- **Logging is the first thing the process configures**, before tracing and error tracking.
  Those initialisers log about what they installed; whatever sink exists at that moment is
  where those lines go.
- **A log reader that logs is its own haystack.** Measured (ADR 0018 §2, defect 2): `httpx`
  emits one stdlib INFO line per request whose message is the full URL, query string
  included — so a poll that reads the log store finds its own previous poll. Remove the sink
  around a read path, or filter on an identifier this run minted.
- Libraries that log caller data at INFO (SQLAlchemy's `Engine` logs bound parameters) are
  silenced explicitly, because interception is global.
- **`sentry_sdk.errors` gets `propagate = False`** (with its filters cleared and one scrubbing
  handler). When the tracker refuses an envelope, that logger's ERROR carries the refusal
  body — **the raw DSN key** — and through `InterceptHandler` it reaches the sink and the log
  store; it also becomes a new event that is itself refused: **1124 envelopes in 3 s**. Both
  measured live (forge-libs `_tracker.py:163-190`).

### Testing a loguru logger

- **`caplog` does not see loguru** (loguru 0.7.3 `migration.html`, "Replacing `caplog`").
  pytest's fixture attaches a handler to the stdlib root
  logger; loguru writes to its own sinks and never goes through stdlib in that direction. A
  test asserting `caplog.text` against a `logger.info()` call fails, and — worse — a test
  asserting *absence* passes for the wrong reason.
- **Add a sink that appends to a list** for the duration of the test (`logger.add(sink,
  serialize=True)`, remove it in teardown) and assert on the records. That is also the only
  way to assert the JSON shape and the extra keys.
- `caplog` remains the right tool for **stdlib** records — asserting what a library logged
  before interception, or that an intercepted logger is still propagating.
- **Assert the sink, not the call order.** A test that checks `configure()` was called before
  `init_otel()` asserts the implementation; a test that reads the sink asserts the claim.

## Anti-patterns

- **Adding a sink without `logger.remove()`.** Every line twice, from line one.
- **A handler propagating loguru back into stdlib.** Exactly two of everything, bounded by an
  internal deadlock guard rather than by anything anyone notices.
- **`diagnose=True` in a deployed service.** Local variable values, including credentials,
  rendered into tracebacks.
- **`DEBUG` as the default level.** Global interception makes it every library's DEBUG; the
  log bill is the measurement.
- **`uvicorn.run(app)` with the default `log_config`.** Interception gone, every server line
  unparsed and uncorrelated, and the library's own tests still green.
- **Binding trace context once at startup.** A patcher reads the span at emit time; a bind
  captures whatever was active during configuration.
- **A patcher that replaces `record["extra"]`.** Breaks `bind()` and `contextualize()`.
- **Omitting trace keys outside a span.** A key set that varies per line breaks parsers
  guarded on key presence; use the zero ids.
- **`caplog` on loguru output.** Green for the wrong reason on absence assertions.
- **Initialising tracing or error tracking before logging.** Their own startup lines land
  unparsed.

## Verify

```bash
# 1. The pinned version.
uv run python -c 'import loguru; print(loguru.__version__)'
# expect: 0.7.3

# 2. Exactly one sink, and no handler propagating back to stdlib. The second grep matches a
#    class DEFINITION or a logging.getLogger(...).handle call, not prose that says "propagate".
grep -rn --include='*.py' 'logger.remove()\|logger.add(' src/
grep -rnE --include='*.py' '^\s*class \w*Propagat|getLogger\([^)]*\)\.handle\(' src/ \
  || echo "no propagating handler"

# 3. The server disables uvicorn's own logging config: expect log_config=None at the call.
grep -rn --include='*.py' 'log_config=' src/

# 4. The frame walk skips the error tracker's patch as well as logging itself.
grep -rn --include='*.py' 'logging.__file__' src/
# expect the comparison, plus a plumbing-module check beside it

# 5. One line, once, the five keys, attributed to the code that logged - on a SINK, not
#    caplog. loguru names a record after the module of the frame that CALLED logging, so
#    the probe logs from a real module (from __main__ the name proves nothing), with
#    sentry's callHandlers patch installed so a walk that stops on it can be seen failing.
uv run python - <<'PY'
import json, logging, pathlib, sys, tempfile
import sentry_sdk
from loguru import logger
from forge_sdk.logging import EXTRA_KEYS, configure_logging  # <- this project: swap in yours
from forge_sdk.settings import ForgeSettings
probe = tempfile.TemporaryDirectory()
pathlib.Path(probe.name, "probe_caller.py").write_text(
    'import logging\ndef emit():\n    logging.getLogger("uvicorn").info("probe")\n')
sys.path.insert(0, probe.name)
import probe_caller
sentry_sdk.init(dsn=None)  # installs the patch the frame walk must step over
assert logging.Logger.callHandlers.__module__ == "sentry_sdk.integrations.logging"
configure_logging(ForgeSettings(service="probe", env="home"))
lines = []
logger.remove()  # only the list sink, so stdout is the verdict
logger.add(lines.append, serialize=True, level="INFO")
probe_caller.emit()  # a STDLIB line, through the bridge
rec = json.loads(lines[0])["record"]
print("emissions:", len(lines), "| extra keys:", sorted(rec["extra"]),
      "| attributed to:", f'{rec["name"]}:{rec["function"]}')
assert len(lines) == 1 and sorted(rec["extra"]) == sorted(EXTRA_KEYS)
assert rec["name"] == "probe_caller", "the walk stopped on a plumbing frame"
PY
# expect: emissions: 1 | extra keys: [request_id, service, span_id, trace_id, version]
#         | attributed to: probe_caller:emit
# With the verbatim walk (forge-libs: InterceptHandler(sentry_aware=False)) it prints
#   attributed to: sentry_sdk.integrations.logging:sentry_patched_callhandlers, exit 1

# 6. The negative control has been seen failing. Temporarily install the
#    propagating handler, re-run step 5, confirm "emissions: 2", then revert.
#    A one-emission green whose two has never been observed is not evidence.
```
