---
name: web-interface-guidelines
description: Use when building or reviewing web UI (HTML, CSS, React, any web framework) - keyboard and focus, forms, states, animation, layout, content, accessibility, performance, theming - or when an experience spec needs an interaction floor. Vercel's Web Interface Guidelines, pinned.
---

# Web Interface Guidelines

`AGENTS.md` beside this file is Vercel's Web Interface Guidelines, vendored byte for byte at a pinned commit (`SOURCE.md`). Its MUST / SHOULD / NEVER lines are the interaction and polish floor for a web interface. Read the sections your change touches; the whole file is about 2,000 tokens.

## Precedence

- The repo's design tokens and design system win over any colour, font, radius, spacing or palette value here or in any other skill. These rules say *what must hold* (a visible focus ring, a 24px hit area); the repo's tokens say *what it looks like*.
- House rule over `AGENTS.md` on contrast: the gate is WCAG 2.2 (4.5:1 text, 3:1 large text and UI edges). `AGENTS.md` prefers APCA, but the WCAG 3 draft has not chosen a contrast algorithm and audits check WCAG 2.x. APCA may be a second opinion on dark themes, never the gate.

## Where it applies

| Surface | Use |
|---|---|
| Web (`*.html`, `*.css`, `*.tsx`, `*.jsx`, `*.vue`, `*.svelte`) | as written |
| Native (SwiftUI, Compose, Flutter) | the stack-neutral groups only: Forms, State & Navigation, Feedback, Content & Accessibility, Content Handling, Design; map each rule to the platform's own control and accessibility API, and drop the DOM, CSS and hydration specifics |

## In each role

- **Design** (`ux-journey`): every state an `AGENTS.md` rule implies (empty, loading, error, long content, disabled with a reason) gets a row in the spec's state table.
- **Implement**: check each touched component against its sections before you report.
- **Review**: cite a finding as `WIG <section>: <rule>`; a broken MUST or NEVER is Important, a SHOULD is Minor unless the spec names it.
