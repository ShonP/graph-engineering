---
name: review-testing-rules
description: Apply for planning, code review, tests, debugging, verification, refactoring, implementation plans, and quality gates.
---

# Review, Testing + Execution Rules
Harvested from the owner's global rule packs on 2026-09-10 (spec 4.3); the plugin copy is the portable one.

Use when planning, reviewing, debugging, testing, or verifying changes.

## Think Before Coding

- Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them; don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop and name the ambiguity.

## Simplicity First

- Minimum code that solves the problem.
- No unrequested features.
- No abstractions for single-use code.
- No flexibility/configurability that wasn't requested.
- No impossible-scenario error handling.
- If 200 lines could be 50, rewrite it.

## Goal-Driven Execution

Define success criteria and loop until verified.

- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix bug" → write a test/probe that reproduces it, then make it pass.
- "Refactor X" → ensure targeted checks pass before and after.

For multi-step tasks, use brief plans with verification handles:

1. Step → verify: command/artifact.
2. Step → verify: command/artifact.
3. Step → verify: command/artifact.

## Review Bias

- Look for root-cause fixes, not symptom patches.
- Check security, data validation, idempotency, concurrency, and observability.
- Prefer targeted verification over broad test runs when project context says broad tests are wasteful.
- Never use `--no-verify` or suppress failing checks to make progress.
