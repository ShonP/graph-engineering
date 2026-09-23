---
name: ux-journey
description: Use before designing or building any user-facing feature or flow - grounds the design in captures of the real current UI, decides where each new element goes in the existing screens and why, maps the journey, states and tap budget, and writes an experience spec with testable UI acceptance rows that implementation, review and qa are held to. Experience first, mechanism second.
---

# UX Journey

The feature is the mechanism; the experience is the product. This runs BEFORE
planning or code for anything user-facing, and produces an **experience spec**
the implementation is held to.

The most common UX failure in agent-built features is not a bad flow - it is a
good component dropped in the wrong place: a button wherever the diff was
easiest, a new screen nobody can find, a fourth primary action on a toolbar
that had one. So this skill starts from the screens that exist, not from the
feature.

## Steps

1. **Restate the user's goal and moment.** Not the mechanism ("add export")
   but the job and context ("end of month, reconciling orders, needs them in a
   spreadsheet"). Name the emotional job: relief, pride, momentum, control.
   One paragraph, written first - everything below serves it.

2. **Ground it in the real UI (as-is).** Never design from the code alone.
   - **Capture** every screen the feature touches or attaches to, as it runs
     now: stand the app up from the profile's `runtime` (the `qa-verification`
     step 2 conventions, with the `GRAPH_RUN_ID` your dispatch names) and
     capture with the same tooling `ux-evidence` uses (Playwright for web,
     `simctl` / `adb` for mobile), at the viewport sizes the profile's
     platforms need, into `.graph/<run>/design/as-is/`. `runtime.none` or
     no runnable UI: read the screen components instead and say so in the
     spec - that is weaker evidence, and the owner should know.
   - **Inventory** each captured screen: its regions (header, toolbar, list,
     detail, footer, nav), the actions already there and their hierarchy
     (primary / secondary / overflow), and the navigation into and out of it.
     Then the reusable pieces: grep the design-system or components directory
     the profile's `rules` name for what already does the job (a menu, a
     sheet, an empty state, a toast). Reuse is the default; a net-new
     component needs a reason.
   - **Prior decisions:** grep earlier experience specs under
     `<docsPath>/ux/` (`*/experience.md`, and older `*-experience.md` files)
     for this area. A decision already made for a similar
     action is the consistency baseline.
   - **Walk the journey:** entry points → steps → exit, taps/inputs to goal,
     friction (dead ends, double entry, waits without feedback, decisions the
     app could make). Greenfield: the closest existing journey it attaches to.

3. **Pattern research.** How best-in-class products solve this exact moment.
   Steal interaction patterns, not pixels, and cite which pattern each
   decision borrows. When the research node already ran (`research/ux.md`,
   `research/competitor.md`), start from those reports.

4. **Decide placement.** For every new entry point, action or screen:
   - **Where:** screen, region, position relative to the existing actions
     (e.g. "orders list toolbar, secondary button right of Filter").
   - **Hierarchy:** primary, secondary or overflow - by how often it is used
     and how much it matters. One primary action per view; a new primary
     demotes the old one, and that is a decision to state, not a side effect.
   - **What it displaces:** anything moved, demoted, hidden or pushed below
     the fold.
   - **Consistency:** the existing screen or prior spec that places a similar
     action the same way (Jakob's law: users expect this app to behave like
     the rest of this app). A deviation says why.
   - **Discoverability (information scent):** does the label plus its location
     predict what happens? Would a user looking for this find it there?
   - **Alternatives:** at least two other placements considered, one line
     each on why they lost.

5. **Design the to-be journey.** Screen-by-screen storyboard: what the user
   sees, taps and feels at each beat.
   - **Tap budget:** the frequent path ≤ its current tap count; state
     before/after counts.
   - **Zero-thought defaults:** every input prefilled with the most likely
     value; typing is a last resort.
   - **State table:** one row per state - default, loading (skeleton), empty
     (with its CTA), error (with retry), success, disabled/permission-denied
     where it applies - naming what the user sees and which existing
     component shows it. Add the celebration beat where earned (respecting
     reduced-motion).
   - **Fluency devices:** optimistic UI, undo instead of confirm where
     reversible, progressive disclosure, momentum (what does the screen invite
     next?).
   - **Every platform the profile names** reads the same; platform-native
     affordances are enhancements, not divergences.
   - **To-be render:** for each changed screen, a picture of the decision,
     in the medium that suits it best among those available here - live-app
     injection, Storybook, an HTML mock, a Claude artifact, Claude Design or
     a generated sketch. `references/render-media.md` says how to check what
     is available and how to choose. Whatever the medium, a PNG of each
     changed screen goes to `to-be/` beside the spec and is committed with it
     by the first UI task; an interactive medium is linked in addition. The
     owner approves what they can see, not a paragraph describing it. What
     else is kept or dropped: the "Where things go" table in that reference.

6. **Write the experience spec** as `experience.md` in one self-contained
   folder - in a run, `.graph/<run>/design/`, with the captures and renders it
   shows under `as-is/` and `to-be/` beside it, linked by relative paths. The
   first UI task of the plan commits `experience.md`, `as-is/` and `to-be/`
   to `<docsPath>/ux/<date>-<feature>/` - never the rest of the folder (see
   "Where things go" in `references/render-media.md`) - so the spec and its images reach the PR
   together and the next feature's step 2 finds them. (Outside a run, write it
   there directly.) It holds:
   goal + emotional job; as-is captures and the inventory; the placement
   decision per element with its consistency citation and rejected
   alternatives; to-be renders; storyboard with tap counts; state table;
   component reuse list (existing, with paths, vs. net-new, with the reason);
   pattern citations; a11y/RTL notes; open questions for the owner; and
   **UI acceptance rows** - one testable line per placement and state
   decision ("on /orders, Export is a secondary button right of Filter";
   "with zero orders, the empty state shows 'No orders yet' and the Create
   order CTA"). Those rows are what the planner puts into tasks and what
   review and qa check.

7. **Hand off.** The spec goes to the plan node; the plan embeds its placement
   decisions, renders and acceptance rows, so the owner approves the design
   at the plan gate. Implementation follows it; a deviation is reported with a
   reason, never made silently.

## Rules

- Never start with UI ("a button that…"). Start with the moment, then the
  screens that exist, then the placement.
- Visual VALUES (colors, type, spacing) come from the repo's design system
  named in the profile's rules - this skill decides journeys and placement,
  never pixels.
- If research contradicts the requested mechanism, say so and propose the
  better journey. Don't silently comply, don't silently override.
- **Scale it** - this rule overrides the step list, and a design node's
  definition of done follows it:
  - **copy or message change** (text only, no layout): one acceptance row
    naming the exact string and where it shows. No stand-up, no renders.
  - **moved or added element** on an existing screen: steps 2 and 4 -
    capture that screen, placement with its consistency citation and one
    rejected alternative - one to-be render, and its rows.
  - **new flow, screen or feature**: everything above.
  Say which size you chose, and why, in the spec's first line.

## Anti-patterns

- Designing from the component code without looking at the running screen.
  Failure: the new button lands in a toolbar that is already full on mobile.
- "Add a button to the page" as the whole placement decision. Failure: the
  implementer picks the spot that was easiest to edit.
- A new primary action beside an existing one. Failure: two equal calls to
  action, and the frequent one loses.
- A net-new component where the design system has one. Failure: the app
  grows a second, slightly different menu.
