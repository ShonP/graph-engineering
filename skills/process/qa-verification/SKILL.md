---
name: qa-verification
description: Use when verifying that shipped work actually does what its acceptance criteria claim - end-to-end UI checks, API contract checks, production smoke tests. Evidence-based; a criterion without captured evidence is not verified.
---

# QA Verification

Review reads code; QA runs it. This skill verifies acceptance criteria against a **running system**, and its output is evidence, not opinion.

## Protocol

1. **Read the acceptance criteria** from the task/plan. Each becomes one checklist row. No criteria = `NEEDS_SETUP` (ask the planner, do not invent criteria).
2. **Stand the system up** the way the repo says to (its README / CLAUDE.md / profile rules). Seeded, deterministic data - never verify against empty or random state.
3. **Verify each criterion end-to-end**, choosing the cheapest sufficient probe:
   - **UI flow**: drive the real browser (Playwright script, or chrome automation tools). Walk the journey a user would, not the shortcut a developer would.
   - **API contract**: curl the endpoint; assert status, shape, and the VALUES that matter, not just 200.
   - **Data effects**: query the store after the action; verify the write, and verify what must NOT have changed.
4. **Capture evidence per criterion**: a screenshot for UI, the response body for API, the query result for data. Save into the run directory.
5. **Probe one level beyond the happy path** per criterion: the empty state, the double-submit, the invalid input, the refresh mid-flow. One good hostile probe each - this is verification, not a test suite.

## Report

One row per criterion:

```
criterion | VERIFIED / FAILED / BLOCKED | evidence path | note
```

- `FAILED` rows: exact reproduction steps and what happened instead. Never soften a failure into a note.
- `BLOCKED` (could not stand the system up, missing seed, missing env): say exactly what is missing. Do not mark VERIFIED anything you could not run.

## Rules

- **Exit code 0 is not evidence.** A green command whose output you did not read proves nothing - read the output, look at the screenshot.
- Verify through the public surface (UI, API), not by calling internals - internals passing is how broken features ship.
- You write test scripts and evidence files only. Never patch the product code; a failure goes back to the fix loop.
