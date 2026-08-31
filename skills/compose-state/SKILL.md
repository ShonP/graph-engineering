---
name: compose-state
description: Jetpack Compose state - where state lives, hoisting, state holders versus ViewModels, derivedStateOf, deferred reads, and collecting flows safely in a lifecycle-aware way. Use when writing or reviewing any composable that holds, receives or observes state.
---

# Compose state

Most Compose performance bugs are state bugs wearing a costume. The question
is almost never "is this slow" but "what reads this, and when does that read
happen".

## The decisions that matter

**Where does it live.** Hoist state to the lowest common ancestor that needs
it. A composable that owns state it does not use is untestable and forces
recomposition on children that do not care.

**Stateless where possible.** A composable taking `value` and `onValueChange`
is previewable, testable and reusable. One reaching into a ViewModel is none
of those.

**State holder versus ViewModel.** UI state that dies with the screen belongs
in a plain state holder class. A ViewModel is for surviving configuration
change and holding business state. Reaching for a ViewModel by reflex puts
screen-local concerns on the wrong lifecycle.

**`derivedStateOf` is narrower than it looks.** It is for when a frequently
changing state produces a rarely changing result - a scroll offset becoming
"is the FAB visible". Wrapping a cheap transformation in it costs more than it
saves. See `references/choosing-derivedstateof.md`.

**Defer the read.** Passing a lambda that reads state, rather than the value,
moves the read from composition to layout or draw. This is the single highest
leverage change for scroll and animation performance, and the one most often
missed. Two references cover it from different angles:
`references/compose-state-deferred-reads.md` and
`references/deferring-state-reads.md`.

**Collect flows lifecycle-aware.** `collectAsStateWithLifecycle`, not
`collectAsState`, unless you have a specific reason. The plain version keeps
collecting while the UI is in the background.
See `references/collecting-flows-safely.md`.

## References

- `compose-state-authoring.md` - where and how to declare state
- `compose-state-hoisting.md` - the hoisting pattern and its limits
- `compose-state-holder-ui-split.md` - state holder versus ViewModel
- `choosing-derivedstateof.md` - when it pays and when it costs
- `compose-state-deferred-reads.md`, `deferring-state-reads.md` - deferring reads
- `collecting-flows-safely.md` - lifecycle-aware collection

## Reviewing

- Does any composable own state that only its caller uses?
- Is a value read at composition that could be read at layout or draw?
- Is `derivedStateOf` wrapping something that is not expensive?
- Is a flow collected without lifecycle awareness?
