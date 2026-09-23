# Picking how to show the design

`ux-journey` step 5 asks for a to-be render. There are six ways to make one.
The designer picks per decision, not per run: one run can show a placement as
a live-app capture and its new flow as a clickable page. Write the choice and
the one-line reason in the spec, next to each render.

## The floor: every render ships a committed PNG

Whatever the medium, each changed screen ends up as a PNG under `to-be/`,
beside `as-is/`, at the viewport sizes the profile's platforms need. That
file is what the plan gate embeds, what git keeps, and what qa compares the
built screen against. An interactive medium is shown **in addition to** it,
never instead: a link can expire, a canvas can be edited after approval, a
PNG in the PR cannot.

## The media

| Medium | Shows the element in the real screen? | Interactive? | Pick it when | Skip it when |
|---|---|---|---|---|
| **Live-app injection** - Playwright opens the running app on seeded data and inserts the new element with the house components' classes, then captures | yes: real data, real neighbours, real viewport | no (a capture) | the question is *where it goes*: a button, a field, a banner, a menu item on an existing screen. The default for placement | there is no runnable UI (`runtime.none`), or the element is a whole new screen with nothing to inject into |
| **Storybook story** - a story in the repo's Storybook (`.storybook/` present) for the new or changed component, one story per state from the state table | no: the component alone | yes: every state, controls | the change is a **new or reworked component**; its states are the hard part; the repo already runs Storybook. The stories are real code the implementer keeps, so this is not throwaway | the repo has no Storybook (never add it just for a design), or the change is placement only |
| **Standalone HTML mock** - one self-contained `.html` built with the house design tokens and component markup | only if the surrounding screen is recreated | yes: clicks, hover, simple state | a **new screen or flow** with no screen to inject into, and no Storybook; or a layout comparison that needs live resizing | the change sits on an existing screen - recreating the page by hand loses the context the placement decision depends on |
| **Claude artifact** - a private claude.ai page (an HTML file published as an artifact) | as much as the page embeds: usually the as-is / to-be captures side by side, plus the flow | yes, and it opens on a phone | a **new flow** the owner should click through at the plan gate, step by step, with the rejected alternatives beside the chosen one; or the owner reviews away from the terminal | a single placement - the PNG pair says it faster. Never for anything the owner presented as sensitive |
| **Claude Design** - a canvas in Claude Design, built on the owner's design system | no: a canvas, not the running app | yes | **explore mode** (3-5 variants to compare), a new visual pattern the design system does not have yet, or the owner asked for it | the placement is on an existing screen, or the Claude Design connector is not available in this session |
| **Generated mockup image** - an image model draws the screen | no | no | a mood or concept sketch for a greenfield product with no UI yet, explicitly labelled as a sketch | anything the implementer will build against: generated screens invent components and misplace text |

## First: what is available here

Check before choosing, and list the result in the spec (`available: live-app,
html, artifact; not: storybook (no .storybook/), claude-design (not connected)`).
Choose only among what is available; the best-suited available medium wins.

| Medium | Available when |
|---|---|
| Live-app injection | the profile's `runtime` stands up and serves the screen (not `runtime.none`) |
| Storybook | the repo has `.storybook/` and its `storybook` script starts |
| Standalone HTML mock | always |
| Claude artifact | your tool list has `Artifact`; if not, write the page and hand its path to the engine to publish at the plan gate |
| Claude Design | your tool list has the Claude Design connector's tools (`mcp__claude-design__*`) and a call to it succeeds |
| Generated mockup image | the repo or user skills ship an image-generation skill with a working key |

## Choosing, in order

1. **Is there a screen to put it on?** Yes: live-app injection is the base,
   because placement is judged in context. No (new screen or flow): an HTML
   mock, or Storybook when the new screen is mostly one new component and the
   repo has Storybook.
2. **Are the states the hard part?** Add Storybook stories when the repo has
   Storybook; otherwise show each state as its own capture or HTML state.
3. **Is it a flow the owner must walk?** Add a Claude artifact that sequences
   the steps, before and after, with the alternatives that lost.
4. **Are you comparing variants?** Explore mode: Claude Design when it is
   connected, otherwise an artifact or HTML page with the variants side by side.
5. **Nothing runnable at all?** HTML mock from the design tokens, labelled as
   a mock in the spec's first line. A generated image only as a concept sketch,
   never as the thing the plan approves.

A step whose medium is not available falls to the next available one that
answers the same question, and the spec says so. Never block a design on a
medium: the committed PNG floor is always reachable.

## Where things go

- Committed with the spec (`to-be/`): the PNGs, and the source of an HTML mock
  when the plan approves it as the reference.
- Committed as product code, by the implementer: Storybook stories.
- Never committed: explore variants, artifact pages, Claude Design canvases -
  the spec links them, and the PNG keeps what was approved.
