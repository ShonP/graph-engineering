---
name: architecture-resilience-rules
description: Apply for architecture, distributed systems, APIs, reliability, idempotency, retries, circuit breakers, queues, events, caching, concurrency, workflows, and data consistency.
---

# Architecture + Resilience Rules
Harvested from the owner's global rule packs on 2026-09-10 (spec 4.3); the plugin copy is the portable one.

Use when designing or changing service architecture, APIs, distributed workflows, queue consumers, event systems, or external dependency handling.

## Idempotency

- Every mutating operation must be idempotent: POST, message handler, job processor.
- Use idempotency keys generated per logical operation.
- Store key + result in the same DB transaction as the side effect.
- Concurrent retries: atomic insert with `IN_PROGRESS` marker and unique constraint.
- Reject same key with different payload using body fingerprint: 409 Conflict.
- TTL records around 24h.
- Consumer-side dedup on `event_id`.

## Retry / Timeout / Circuit Breaker

- Never retry tight loops. Use exponential backoff with full jitter.
- Retry only transient errors: 5xx, timeouts, connection errors; 408/429 if appropriate.
- Honor `Retry-After`.
- Always set max attempts and an overall deadline.
- Always set per-attempt timeouts.
- Retry budget around 10% to prevent retry storms.
- Breakers are per dependency; don't count 4xx failures.
- Order: fallback → bulkhead → circuit breaker → retry → timeout → downstream.

## Bulkhead + Degradation

- Use per-dependency pools/semaphores.
- Fast-fail when a bulkhead is full; don't queue indefinitely.
- Degrade gracefully: fresh → stale cache → static default.
- Use feature flags as kill switches.

## Data Consistency

- Never dual-write DB + message bus separately.
- Use transactional outbox: write events in the same transaction as business data.
- Poll with `FOR UPDATE SKIP LOCKED`.
- Partition Kafka by `aggregate_id` for per-entity ordering.
- Use CDC/Debezium only when sub-second latency justifies it.

## API Design

- Resources as nouns, HTTP methods as verbs, proper status codes.
- Always paginate: cursor for feeds/large data, offset for admin panels.
- Rate limit from day one.
- Version with `/v1/` from the start.
- Add optional fields only within a version; bump version for breaking changes.
- Include standard headers: `X-RateLimit-*`, `Retry-After`, `Deprecation`, `Sunset`.

## Concurrency

- Single-row guard: atomic `UPDATE ... WHERE condition`.
- Rare conflicts: optimistic locking with version column + retry.
- Common/high-contention conflicts: pessimistic lock with `SELECT ... FOR UPDATE`.
- Acquire locks in consistent order to avoid deadlocks.

## Long-Running Work

- Accept request quickly, enqueue, worker processes async.
- Visibility timeout + heartbeat.
- DLQ after bounded retries.
- Backpressure: reject/throttle when queue exceeds max size.
- Idempotency keys on job creation.
- Progress in Redis with TTL.

## Events

- Events are immutable facts in past tense: `OrderPlaced`, `PaymentCaptured`.
- Include `event_id`, `version`, `timestamp`, `source_service`.
- Design for at-least-once delivery; consumers idempotent.
- Tolerate out-of-order where possible.
- Schema evolution: add optional fields; new event type for breaking changes.
- Monitor DLQ and consumer lag.
