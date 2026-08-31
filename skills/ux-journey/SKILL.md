---
name: ux-journey
description: Use before designing or building any user-facing feature or flow - maps the user's moment, journey, tap budget, and emotional beats into an experience spec that implementation is then held to. Experience first, mechanism second.
---

# UX Journey

The feature is the mechanism; the experience is the product. This runs BEFORE planning or code for anything user-facing, and produces an **experience spec** the implementation is held to.

## Steps

1. **Restate the user's goal and moment.** Not the mechanism ("add badges") but the job and context ("just finished a workout, phone in one hand, wants to feel progress"). Name the emotional job: relief, pride, momentum, control. One paragraph, written first - everything below serves it.
2. **Map the current journey (as-is).** If the flow exists, walk it screen by screen: entry points → steps → exit. Count taps/inputs to goal. Mark friction: dead ends, double entry, waits without feedback, decisions the app could make for the user. If greenfield, map the closest existing journey the feature will attach to.
3. **Pattern research.** Scan how best-in-class products in this domain solve this exact moment. Steal interaction patterns, not pixels. Cite which pattern each decision borrows.
4. **Design the to-be journey.** Screen-by-screen storyboard in words: what the user sees, taps, and feels at each beat. Requirements:
   - **Tap budget:** the frequent path ≤ its current tap count; state before/after counts.
   - **Zero-thought defaults:** every input prefilled with the most likely value; typing is a last resort.
   - **State beats:** loading (skeleton), empty (CTA), error (retry), success - plus the celebration beat where earned (respecting reduced-motion).
   - **Fluency devices:** optimistic UI, undo instead of confirm where reversible, progressive disclosure, momentum (what does the screen invite next?).
   - **Every platform the profile names:** the journey must read identically across them; platform-native affordances are enhancements, not divergences.
5. **Write the experience spec** to the profile's `docsPath` under `ux/<date>-<feature>-experience.md`: goal + emotional job, as-is map with tap counts, to-be storyboard, pattern citations, a11y/RTL notes, open questions for the owner.
6. **Hand off.** The spec is input to the plan node; review and QA check the built flow against its tap budget and state beats.

## Rules

- Never start with UI ("a button that…"). Start with the moment and work back to UI.
- Visual VALUES (colors, type, spacing) come from the repo's design system named in the profile's rules - this skill decides journeys and placement, never pixels.
- If research contradicts the requested mechanism, say so and propose the better journey. Don't silently comply, don't silently override.
- Scale it: a moved button needs a two-sentence placement check, not this full run. A new flow/screen/feature gets everything.
