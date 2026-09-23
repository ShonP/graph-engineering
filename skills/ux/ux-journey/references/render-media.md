# Picking how to show the design

`ux-journey` step 5 asks for a to-be render. There are six media to consider; the designer renders with four of them itself (live-app, HTML, artifact, generated sketch), drafts Storybook stories for the implementer, and briefs the engine for Claude Design.
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
| **Storybook story** - the repo's Storybook, one story per state from the state table | no: the component alone | yes: every state, controls | the change is a **new or reworked component** and the repo already runs Storybook. The stories are product code, so they are **implementer work**: the designer drafts them in `design/stories/` and the plan's UI task moves them in; the designer shows the states in another medium meanwhile | the repo has no Storybook (never add it for a design) |
| **Standalone HTML mock** - one self-contained `.html` built with the house design tokens and component markup | only if the surrounding screen is recreated | yes: clicks, hover, simple state | a **new screen or flow** with no screen to inject into, and no Storybook; or a layout comparison that needs live resizing | the change sits on an existing screen - recreating the page by hand loses the context the placement decision depends on |
| **Claude artifact** - a private claude.ai page (an HTML file published as an artifact) | as much as the page embeds: usually the as-is / to-be captures side by side, plus the flow | yes, and it opens on a phone | a **new flow** the owner should click through at the plan gate, step by step, with the rejected alternatives beside the chosen one; or the owner reviews away from the terminal | a single placement - the PNG pair says it faster. Never for anything the owner presented as sensitive |
| **Claude Design** - a canvas in Claude Design, built on the owner's design system; the designer writes a brief, the engine (which holds the connector) runs it at the plan gate | no: a canvas, not the running app | yes | **explore mode** (3-5 variants to compare), a new visual pattern the design system does not have yet, or the owner asked for it | the placement is on an existing screen (the engine skips the brief when no connector is present) |
| **Generated mockup image** - an image model draws the screen | no | no | a mood or concept sketch for a greenfield product with no UI yet, explicitly labelled as a sketch | anything the implementer will build against: generated screens invent components and misplace text |

## First: what is available here

Check before choosing, and list the result in the spec (`available: live-app,
html, artifact; not: storybook (no .storybook/), claude-design (brief; pending engine)`).
Choose only among what is available; the best-suited available medium wins.

| Medium | Available when |
|---|---|
| Live-app injection | the profile's `runtime` stands up and serves the screen (not `runtime.none`) |
| Storybook (draft stories for the implementer) | the repo has `.storybook/` |
| Standalone HTML mock | always |
| Claude artifact | your tool list has `Artifact` |
| Claude Design | the owner's session has a Claude Design connector - tools from that server, named `mcp__claude_ai_Claude_Design__*` or `mcp__claude-design__*` - which the engine checks at the plan gate. The designer writes the brief either way; the spec says it is pending the engine |
| Generated mockup image | the repo or user skills ship an image-generation skill with a working key |

## Choosing, in order

1. **Is there a screen to put it on?** Yes: live-app injection is the base,
   because placement is judged in context. No (new screen or flow): an HTML
   mock (with draft stories for the implementer when the repo has Storybook).
2. **Are the states the hard part?** Show each state as its own live-app
   capture or HTML state, and, when the repo has Storybook, also draft one
   story per state in `design/stories/` for the implementer.
3. **Is it a flow the owner must walk?** Add a Claude artifact that sequences
   the steps, before and after, with the alternatives that lost.
4. **Are you comparing variants?** Explore mode: an artifact or HTML page
   with the variants side by side, and a Claude Design brief for the engine
   when the owner's session may have the connector.
5. **Nothing runnable at all?** HTML mock from the design tokens, labelled as
   a mock in the spec's first line. A generated image only as a concept sketch,
   never as the thing the plan approves.

A step whose medium is not available falls to the next available one that
answers the same question, and the spec says so. Never block a design on a
medium: the committed PNG floor is always reachable.

## Where things go

Everything is written under `.graph/<run>/design/`, one folder per role, so
the committer never has to guess:

| Path | What | Ends up |
|---|---|---|
| `experience.md`, `as-is/`, `to-be/` | the spec, captures, to-be PNGs, and an HTML mock's source when the plan approves it as the reference | committed to `<docsPath>/ux/<date>-<feature>/` by the first UI task |
| `stories/` | draft Storybook stories | moved next to their component as product code by the UI task |
| `artifact/` | the HTML of a published artifact page | never committed; the spec links the artifact |
| `explore/` | explore-mode variants | never committed |
| `claude-design-brief.md` | what the engine asks Claude Design for | never committed; the engine adds the canvas link to `experience.md` when it runs the brief |
