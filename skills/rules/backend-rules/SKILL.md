---
name: backend-rules
description: Apply for backend services, APIs, NestJS, FastAPI, Python, TypeScript backend, database, queues, workers, service architecture, or server-side refactors.
---

# Backend Rules
Harvested from the owner's global rule packs on 2026-09-10 (spec 4.3); the plugin copy is the portable one.

Use for NestJS, FastAPI, service, worker, API, DB, and backend TypeScript/Python work.

## Defaults

- Write self-descriptive code. No comments unless they clarify non-obvious domain decisions.
- Remove unused values and variables.
- Single object argument for TypeScript functions: `const fn = (args: { arg1: string; arg2: number }) => {}`.
- Think reusability and modularity by default.
- Never import directly across module internals; import from the root/barrel of the module.
- Work with interfaces first; prefix interfaces with `I`.
- Check if interfaces exist before creating new ones.
- Keep modules independent; avoid tight coupling between services.
- Use dependency injection for services and repositories.
- Log meaningful operations to trace flow and diagnose issues.
- Always use NestJS `ConfigModule` for configuration.
- Never use `any`; use types and interfaces.
- Always use UUIDv7 for identifiers.
- Always paginate; cursor-based using UUIDv7 where possible.

## Security / Correctness

- Keep OWASP security, scalability, performance, error handling, edge cases, SQL injection prevention, data validation, and idempotency in mind.
- Validate all external input with Pydantic/Zod/DTOs.
- Set explicit timeouts on network calls.
- Use DB transactions around coupled state changes.
- Unit tests use in-memory fakes; no network or real DB in unit tests.

## Libraries / Stack

- Python package management: `uv`.
- Retry: `tenacity` in Python.
- HTTP: `httpx` with timeout defaults in Python; axios instance in TS.
- Validation: Pydantic in Python; Zod in TS.
- API: FastAPI or NestJS.
- Queue: Redis, Kafka, SQS depending project context.
- Cache: Redis with proper TTL.
