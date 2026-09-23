---
name: nats
description: Use when publishing to or consuming from NATS JetStream, binding a durable consumer, writing a subject allow-list or per-user permissions block, or reviewing anything that dedupes, acks or replays messages. Covers Nats-Msg-Id and duplicate_window, why stream= is mandatory on every subscribe, per-stream ack subjects, the _INBOX rule, order-independent handlers, and why a denied JetStream call looks exactly like a timeout.
license: MIT
---

# NATS JetStream

Written against **NATS Server 2.14.6**, **nats-py 2.16.0** (PyPI, published 2026-09-16) and
**natscli 0.4.0** — the versions the measurements below were taken on. Fetched 2026-09-23,
HTTP 200. docs.nats.io is unversioned, so its pages are pinned to the `nats.docs` commit
current on that date (`f115bec`, 2026-08-24, i.e. the 2.14 docs); source is pinned to tags:

- https://github.com/nats-io/nats.docs/blob/f115becf6563e3bbe16bb94cbf87bfceb84199c1/nats-concepts/jetstream/streams.md
- https://github.com/nats-io/nats.docs/blob/f115becf6563e3bbe16bb94cbf87bfceb84199c1/running-a-nats-service/configuration/securing_nats/authorization.md
- https://github.com/nats-io/nats.py/blob/v2.16.0/nats/src/nats/js/client.py - nats-py 2.16.0
- https://github.com/nats-io/nats-architecture-and-design/blob/02f151ed4918978ec35593f22be6c5e6eb909ca3/adr/ADR-1.md
  - the `$JS.API` subject namespace

Measured in-house, rung 1 — every rule marked "measured" was run against a live 2.14.6 server
and most were watched going red first. **ADR 00nn** is `Equival-io/forge-platform`
`docs/adr/00nn-*.md` (a private repo): 0004 "Per-user permissions" and "What SP1's proposal
got wrong, measured on a real 2.14.6 server"; 0016 §§8, 10, 11.

## When to apply

- Publishing, subscribing, acking or replaying on JetStream.
- Writing or reviewing a `permissions` block, a subject allow-list, or a new identity.
- Adding a stream or consumer, or a relay that drains a table onto the bus.
- Debugging a client that "hangs", times out, or silently receives nothing.

## Rules

### Publishing and deduplication

- **The message id goes in a header, not a keyword.** nats-py has no `msg_id=` argument:
  `await js.publish(subject, body, headers={"Nats-Msg-Id": str(event_id), **headers})`.
- **`Nats-Msg-Id` only dedupes inside the stream's `duplicate_window`.** Outside it, a
  redelivered copy is stored as a new message. The window is a stream config value and it is
  the *only* thing making a publish idempotent — pick it deliberately against how long a
  crashed producer might take to come back (`streams.md`, `DuplicateWindow`).
- **A JetStream publish is a request.** `js.publish` is `nc.request` under the hood: the
  `PubAck` comes back on the client's own inbox, which is why `_INBOX.>` is not optional (see
  Authorization).
- **Deduplicate on the consumer side too**, in the same transaction as the effect:
  `INSERT INTO processed_events (event_id) VALUES (...) ON CONFLICT DO NOTHING`, and skip the
  body when the rowcount is 0. The broker's window is a bounded optimisation; this is the
  guarantee (ADR 0016 §10).

### Subscribing - `stream=` is mandatory

Measured, ADR 0004: the sharpest failure in this file.

- **Always pass `stream=` explicitly.** Read from the nats-py 2.16.0 wheel:
  `JetStreamContext.subscribe` and `.pull_subscribe` call
  `find_stream_name_by_subject(...)` when `stream=` is omitted, and that helper publishes to
  **`$JS.API.STREAM.NAMES`**. Under any real allow-list no service holds that subject, so a
  handler that names only a subject **dies at subscribe time with `nats: timeout`** and no
  mention of permissions anywhere but the server log.
- Granting `STREAM.NAMES` is the wrong fix: it is an account-wide subject-to-stream oracle,
  and passing the stream name costs nothing.
- **`pull_subscribe_bind(durable=..., stream=...)`, not `pull_subscribe`.** The second
  *creates* the consumer; in a GitOps repo the consumer is a declared resource and a service
  identity holds no create right.
- **Ask `consumer_info` before binding.** `pull_subscribe_bind` makes no API call — it is a
  core `subscribe` on a fresh inbox (`client.py:625-689` at v2.16.0) — so a typo
  in the durable name binds to nothing and the pod idles forever looking healthy. Worse,
  `fetch` cannot tell the two 404s apart — nats-py's `_is_temporary_error` (`client.py:707`)
  reads the status code only, so `404 Consumer Not Found` is swallowed exactly like `404 No Messages`.
  Distinguish up front: 404 is a permanent misconfiguration, **503** is JetStream not ready
  yet (a rolling restart, no meta leader) and is worth retrying with a bounded count.
- **Handlers must be order-independent as well as idempotent.** Measured (ADR 0016 §8):
  within one tick you get id order; across workers `SKIP LOCKED` gives you none; and after a
  mid-batch crash a batch is republished from the top, so a consumer sees ids it has already
  seen and the second copy sits at a *later* stream sequence than events that logically
  follow it. Stream-sequence order and event-id order are different orders.

### Authorization - the part that fails silently

Subjects are the only vocabulary. Once a user has an allow-list, anything "that has not been
_allow listed_ ... fails and is logged at the server" (`authorization.md`, verbatim), and
**a user with no `permissions` block — and no `default_permissions` — can do anything on
the server** (ADR 0004, measured: such a user could purge `forge-events`).

- **`*` is ONE WHOLE TOKEN, so `forge-*` matches nothing.** Measured: a list written as
  `$JS.API.CONSUMER.MSG.NEXT.forge-*.>` reads as if it grants every `forge-` stream and
  grants none of them — the token is the literal string `forge-*`. Name each stream.
- **`_INBOX.>` on every subscribe allow-list** (`authorization.md`: "you need to add rules
  for the `_INBOX.>` pattern"). Without it every JetStream publish times out,
  and a relay reads a timeout as a failure and eventually marks the row dead (ADR 0016 §11).
- **Scope ack subjects per stream: `$JS.ACK.<stream>.>`, never `$JS.ACK.>`.** The ack subject
  embeds stream and consumer, so a blanket grant lets any holder settle **another identity's**
  in-flight message. Measured: under `$JS.ACK.>`, one `+ACK` from an unrelated identity took a
  WorkQueue stream from 1 message to 0 — an *allowed* publish, with nothing in the server log.
  On a work queue an ack is a deletion, not an eavesdrop.
- **Spell two-token verbs out per stream.** `$JS.API.CONSUMER.*.*.<stream>.>` reads as if the
  stream were pinned; it is not. The modern create is
  `CONSUMER.CREATE.<stream>.<consumer>.<filter>`, so the first `*` eats `CREATE`, the second
  eats **the stream name**, and the literal position lines up with the consumer. Measured
  against exactly that list, a raw request created a durable **on a production stream** from a
  test identity. Use `$JS.API.CONSUMER.DURABLE.CREATE.<stream>.>` and
  `$JS.API.CONSUMER.MSG.NEXT.<stream>.>`. The rule: **count the tokens of the specific verb
  before wildcarding any of them.**
- **`add_consumer()` takes the LEGACY `$JS.API.CONSUMER.DURABLE.CREATE` path.** A list built
  by tracing `pull_subscribe` denies it, because that call publishes the modern
  `CONSUMER.CREATE` subject instead. Measured: 37 red rows against a spike whose create,
  publish, purge and delete all worked. **A trace is only evidence about the call you traced.**
- `$JS.API.INFO` and `$SYS.REQ.USER.INFO` are needed for account/identity probes; without the
  latter `nats account info` silently drops its `Account:` line and still exits 0.
- `$JSC.CI.<account>.<stream>.<consumer>` belongs to the server's own internal client. No user
  needs it; granting it is a permission nobody could watch being used.
- **Within one account, stream-create is stream-read, and no subject list closes it.** A
  `$JS.API.STREAM.CREATE.<name>` body may carry `sources` or `mirror`; the copy is performed
  by the server's internal client, which is **not** evaluated against the caller's
  permissions. Measured end to end: an identity allowed to create its own scratch stream
  sourced a production stream into it and read the contents. The boundary that closes this is
  a **separate account**, not a cleverer allow-list. Name the residual where you grant it.
- **A test identity, not a widened service identity.** When a test needs stream-create, give
  it its own user with literal scratch stream names, rather than putting create rights on the
  identity production code runs as.

### Diagnosing a denial

- **A denied `$JS.API` call reads as a TIMEOUT, not as a permission error.** Every `$JS.API`
  call is a request, so the denied publish is dropped and the caller waits out its deadline:
  `could not pick a Stream to operate on: context deadline exceeded`. The violation text
  exists in exactly two places — **the server log**
  (`Publish Violation - Subject "$JS.API.STREAM.PURGE.<stream>"`) and the CLI's own output
  when the denied operation is a **core** publish or subscribe.
- **So test a permission through a raw `$JS.API` subject with a core publish**, not through
  the SDK call that wraps it. Asserting on a timeout asserts nothing: a slow server, a wrong
  stream name and a denial are the same observable.
- When a row is red and you need to know which subject was refused, read the server log.

### Operational invariants

- **Every bcrypt hash in a NATS config must carry the `$2a$` prefix.** Measured, and it cost
  a live outage: the server's config lexer special-cases the literal prefix `2a$` so a hash is
  not re-read as a nested variable reference. A `$2b$` hash crash-loops the server at startup
  every time (`variable reference for '2b$11$...' can not be found`). **Python's `bcrypt`
  emits `$2b$`; Go's — and therefore `nats server passwd` — emits `$2a$`.** The two differ
  only for passwords at or past 256 bytes, so rewriting a short-password hash's prefix is the
  fix. Assert the prefix on every hash in the live Secret, comparing and never printing.
- **Purge is not delete-and-recreate.** Measured on 2.14.6: after `purge_stream`, republishing
  the same `Nats-Msg-Id` inside the window returns `duplicate=True` with `messages=0`, while
  after delete-and-recreate the same publish is stored. Purge leaves the message-id map and
  the ack floor in place — swapping one for the other changes what a test measures.
- **Two streams in one account may not have overlapping subjects** (`subjects overlap with an
  existing stream (10065)`). Plan subject roots before adding a stream, including test streams.
- A subject covered by **no** stream makes a publish fail deterministically with
  `NoStreamResponseError` — useful as a poison-message fixture that needs no fault injection.

## Anti-patterns

- **Subscribing with a subject and no `stream=`.** Fails as `nats: timeout` with the real
  reason only in the server log.
- **`pull_subscribe` where a declared consumer exists.** Creates a second consumer, or is
  denied and looks like a timeout.
- **Binding without `consumer_info` first.** A typo becomes a permanently idle, healthy pod.
- **`forge-*` (or any `prefix-*`) in a subject.** Matches nothing; reads as if it matches
  everything.
- **`$JS.ACK.>`.** Lets one identity delete another's in-flight work-queue message, as an
  allowed publish with no log line.
- **`$JS.API.CONSUMER.*.*.<stream>.>`.** The stream is not pinned; measured to allow creating
  a durable on a production stream.
- **Building an allow-list from a protocol trace of one call.** `add_consumer` and
  `pull_subscribe` use different create subjects.
- **Omitting `_INBOX.>`.** Every publish times out; a relay marks good rows dead.
- **Asserting a denial by catching a timeout.** Indistinguishable from a slow server.
- **A `$2b$` bcrypt hash in a NATS config.** Server crash-loops at startup.
- **Assuming `sources`/`mirror` can be denied by subject.** They are body content on an
  allowed subject; only an account boundary closes it.
- **A handler that assumes ordering or at-most-once delivery.** Neither is on offer.

## Verify

```bash
# 1. Server and client versions the rules were measured against.
nats server info --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["version"])'
uv run python -c 'import importlib.metadata as m; print(m.version("nats-py"))'
# expect: 2.14.6 and 2.16.0   (nats-py has no nats.__version__; it is an AttributeError)

# 2. Every JetStream subscribe names its stream. A grep hits the docstrings that WARN about
#    it and misses a stream= on the next line; this reads the AST. Expect no output.
uv run python - src <<'PY'
import ast, pathlib, sys
JS = {"pull_subscribe", "pull_subscribe_bind"}  # `.subscribe` counts only on a js receiver
for f in sorted(pathlib.Path(sys.argv[1]).rglob("*.py")):
    for n in ast.walk(ast.parse(f.read_text())):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        name, receiver = n.func.attr, ast.unparse(n.func.value).lower()
        if (name in JS or (name == "subscribe" and "js" in receiver)) \
                and not any(k.arg == "stream" for k in n.keywords):
            print(f"{f}:{n.lineno}: {ast.unparse(n.func)}(...) without stream=")
PY
# On `js.pull_subscribe("s", durable="d")` and `js.subscribe("s")` it prints one line each.

# 3. Binding, not creating, and info before bind.
grep -rn 'pull_subscribe_bind\|consumer_info' src/

# 4. No prefix wildcard and no blanket ack grant in any allow-list. Expect no output.
grep -rnE '"[^"]*-\*[.>]|\$JS\.ACK\.>' argocd/ manifests/

# 5. Two-token verbs are spelled out per stream, so the stream sits at a literal position.
grep -rn 'JS.API.CONSUMER' argocd/ manifests/
# expect DURABLE.CREATE.<stream>.> and MSG.NEXT.<stream>.>, never CONSUMER.*.*

# 6. _INBOX is on every subscribe allow-list.
grep -rn '_INBOX' argocd/ manifests/
# expect one per user that publishes to JetStream

# 7. Every bcrypt hash is $2a$. Compares, never prints.
kubectl get secret <nats-auth> -n <ns> -o json |
  python3 -c 'import base64,json,sys
d=json.load(sys.stdin)["data"]
bad=[k for k,v in d.items() if k.endswith("bcrypt") and not base64.b64decode(v).decode().startswith("$2a$")]
print("non-2a keys:", bad or "none")'
# expect: none   (any name here crash-loops the server on its next restart)

# 8. A permission denial, asserted through a RAW api subject with a core publish,
#    because the SDK call would only ever report a timeout.
nats pub '$JS.API.STREAM.PURGE.<a-stream-this-identity-must-not-touch>' '{}' --user <svc> ...
# expect the CLI to print a permissions violation; a timeout here proves nothing
```
