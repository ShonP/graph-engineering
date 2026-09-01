---
name: compose-performance
description: Diagnose and fix Jetpack Compose recomposition and stability problems - stability inference, strong skipping, unstable types, lazy layout performance, subcomposition pitfalls, and the tooling for measuring recomposition. Use when a Compose screen janks, over-recomposes, or before optimising by guesswork.
---

# Compose performance

The rule that saves the most time: **measure first**. Compose performance
intuition is unreliable, the tooling is good, and most "obvious" optimisations
are either no-ops or pessimisations. Nearly every reference here is about
seeing what is actually happening before changing it.

## Stability, which is what this is really about

A composable skips recomposition only when Compose can prove its parameters
are unchanged. That proof depends on **stability**: a type is stable if
equality is well defined and its public properties do not change without
notifying composition.

The usual culprits are collection interfaces (`List` is unstable, the
implementation is not), classes from modules the compiler cannot see, and
`var` properties in data classes.

**Strong skipping** changes this materially and is on by default in current
versions: composables with unstable parameters can now skip using instance
equality. It does not make stability irrelevant - it changes which problems
are worth chasing. See `references/using-strong-skipping-correctly.md` before
adding `@Stable` annotations by reflex.

## Measure in this order

1. **Release build with R8.** Debug-build Compose performance numbers are
   meaningless. See the `compose-build-and-test` skill.
2. **Layout Inspector recomposition counts** - which composable, how often.
3. **Compiler stability reports** - which parameters are unstable and why.
4. **Traces** for what is happening inside a frame.

References: `auditing-compose-performance.md`,
`debugging-recompositions.md`, `tracing-recompositions-at-runtime.md`,
`visualizing-recomposition-cascades.md`,
`using-stability-analyzer-ide-plugin.md`.

## Fixing

- `understanding-stability-inference.md` - how the compiler decides
- `diagnosing-compose-stability.md`, `compose-stability-diagnostics.md` - reading the reports
- `stabilizing-compose-types.md` - immutable collections, `@Immutable`, `@Stable`, wrapper types
- `compose-recomposition-performance.md` - the general model

## Lazy layouts

`optimizing-lazy-layouts.md` for keys, content types and stable item state;
`configuring-lazy-prefetch.md` for prefetch tuning;
`avoiding-subcomposition-pitfalls.md` for why nesting scrollables and
measuring children twice is expensive.

Stable `key`s on lazy items are the highest-value single fix and the most
commonly missing.

## Reviewing

- Was a claim of "slow" measured, in a release build?
- Are lazy items keyed?
- Is an annotation asserting stability that the type does not actually have? A false `@Stable` is a correctness bug, not just a performance one.
