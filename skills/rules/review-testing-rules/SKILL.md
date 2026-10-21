---
name: review-testing-rules
description: Apply for planning, code review, tests, debugging, verification, refactoring, implementation plans, and quality gates.
---

# Review, Testing + Execution Rules

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
- A file past ~250 LOC signals a missing abstraction: split it along that abstraction.

## Where Work Lands

- Every task in its own git worktree and branch; never commit on the default branch in the main checkout. Once merged, remove the worktree and its branch.
- Scaffold with the official CLI and its current docs; never hand-write configs from memory.
- A new env var updates `.env.example` and the CI secrets doc in the same change.
- Deferred work (a follow-up, an unfixed finding, an owner-only step) is filed before you finish in the tracker or file the profile or CLAUDE.md names (in a graph run, `.graph/<run>/followups.md`), never only in a report, PR body or chat. An unrelated finding becomes a new item there, not part of this branch.

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
