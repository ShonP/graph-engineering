---
name: compose-ui
description: Jetpack Compose UI construction - modifier order and the Modifier.Node API, layout style, slot APIs, animations, focus and navigation, and side effects. Use when building or reviewing composable UI structure and behaviour.
---

# Compose UI

## Modifiers

**Order is semantics, not style.** `padding().background()` and
`background().padding()` produce different pixels. Modifier chains read
outside-in for layout and are applied in order; a chain that looks tidy but
orders `clickable` after `padding` gives an unclickable gap.

`references/ordering-modifier-chains.md` covers the ordering rules.
`references/compose-modifier-and-layout-style.md` covers layout idiom.
`references/migrating-to-modifier-node.md` covers the `Modifier.Node` API,
which replaces `composed {}` - the old form allocates per composition and
defeats skipping.

## Slot APIs

A composable taking `content: @Composable () -> Unit` is more reusable than
one taking fifteen configuration parameters, and it keeps the caller in
control of what is drawn. `references/compose-slot-api-pattern.md`.

## Side effects

The effect APIs are not interchangeable and choosing wrongly produces bugs
that look random: `LaunchedEffect` for suspending work tied to composition,
`DisposableEffect` for anything needing cleanup, `SideEffect` for publishing
to non-Compose code, `rememberUpdatedState` for a value a long-running effect
must see without restarting.

The most common defect is an effect keyed wrongly - keyed on something that
changes every recomposition, so it restarts constantly, or keyed on `Unit`
when it should restart.

`references/compose-side-effects.md` and `references/using-efficient-effects.md`.

## Animation and focus

`references/compose-animations.md` for the animation APIs and when each fits.
`references/compose-focus-navigation.md` for focus order, traversal and
keyboard and accessibility navigation - the part usually discovered late,
when someone tries the app with a keyboard or a screen reader.

## Reviewing

- Does the modifier order produce the intended hit target, not just the intended look?
- Is `composed {}` used where `Modifier.Node` belongs?
- Is every effect keyed on exactly what should restart it?
- Does focus traversal follow the visual order?
