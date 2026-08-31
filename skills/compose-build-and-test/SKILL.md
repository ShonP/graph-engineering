---
name: compose-build-and-test
description: Jetpack Compose build and test configuration - baseline profiles, R8 and minification, enforcing stability in CI, Compose UI testing patterns, and why performance must be measured in release mode. Use when setting up Compose CI, writing UI tests, or investigating a performance number that came from a debug build.
---

# Compose build and test

## Measure in release, always

Debug builds run Compose without R8, with extra instrumentation and without
the optimisations that make the real app fast. **A performance number from a
debug build is not a slower version of the truth, it is a different number.**
This is the single most common way Compose performance work is wasted.

`references/testing-compose-in-release-mode.md`.

## Baseline profiles

Ahead-of-time compilation hints for the paths users actually take. They
measurably improve cold start and first-scroll jank, and they are one of the
few optimisations that are close to free once generated.

`references/generating-baseline-profiles.md`.

## R8

`references/configuring-r8-for-compose.md` for keep rules and the
configuration Compose needs. Getting this wrong shows up as reflection
failures at runtime in release only, which is the worst place to find them.

## Stability in CI

Stability regressions are invisible until a screen is slow. Compiler stability
reports can be generated and diffed in CI so that a newly unstable parameter
fails the build rather than being discovered by a user.

`references/enforcing-stability-in-ci.md`.

Introduce this as a ratchet against the current measurement, not as a hard
gate on day one, or the first run fails on pre-existing debt and gets
disabled.

## UI testing

`references/compose-ui-testing-patterns.md` for the semantics tree, finders,
synchronisation and the idling problem.

Test through semantics rather than through structure. A test asserting on node
hierarchy breaks on every refactor; one asserting on content description and
role survives them and also checks the thing a screen reader sees.
