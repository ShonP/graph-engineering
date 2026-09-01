---
name: kotlin-concurrency
description: Kotlin structured concurrency and flows - scopes, cancellation, supervision, exception handling, and modelling state versus events with StateFlow and SharedFlow. Use when writing or reviewing coroutine code, flow pipelines, or anything with a lifecycle and a cancellation story.
---

# Kotlin concurrency

## Structured concurrency

The whole model rests on one idea: **a coroutine's lifetime is bounded by its
scope**, so work cannot outlive the thing that started it. Most coroutine bugs
come from escaping that - a `GlobalScope` launch, a scope that is never
cancelled, or work launched in a scope whose lifetime is longer than the work's
relevance.

What to get right:

- **Cancellation is cooperative.** A tight loop with no suspension point never
  notices it was cancelled. Check `isActive` or call a suspending function.
- **`CancellationException` is control flow, not failure.** A blanket
  `catch (e: Exception)` around suspending code swallows cancellation and
  breaks the model. Catch it and rethrow, or catch narrower.
- **`coroutineScope` versus `supervisorScope`.** The first fails all children
  when one fails; the second isolates them. Choosing by accident produces
  either lost work or unkillable failures.
- **`withContext` for dispatching, not for parallelism.** Two independent
  awaits belong in `async`/`awaitAll`, not sequential `withContext` calls.

`references/kotlin-coroutines-structured-concurrency.md`.

## Flows: state versus events

The distinction that prevents a whole class of bug:

- **State** is a current value with a conflatable history. `StateFlow`. A late
  subscriber wants the latest value and does not care what it missed.
- **Events** are things that happened exactly once. A `SharedFlow` with the
  right replay, or a channel. A late subscriber must not re-receive them.

Modelling a one-shot event as `StateFlow` produces the classic bug where a
navigation or a snackbar fires again after rotation. Modelling state as an
event produces a screen that renders blank until something changes.

`references/kotlin-flow-state-event-modeling.md`.

## Reviewing

- Is anything launched in a scope that outlives its relevance?
- Does a catch block swallow `CancellationException`?
- Is a one-shot event modelled as state?
- Are independent suspending calls actually concurrent, or accidentally sequential?
