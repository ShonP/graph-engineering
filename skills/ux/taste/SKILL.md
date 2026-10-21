---
name: taste
description: Use when choosing a visual direction, designing or reviewing how a screen or page looks, or when UI reads generic, templated or AI-made. Routes to the upstream Taste Skill plugin and holds the stack-neutral generic-tells check.
---

# Taste

Taste Skill ([tasteskill.dev](https://www.tasteskill.dev/), `github.com/Leonxlnx/taste-skill`, MIT) is art direction for coding agents: it deals researched directions (composition, type, palette, imagery) from a library built on a study of 247 curated sites, bans the ornaments generators default to, checks the result in a real browser with Node 22 and Chrome, and fixes from its own screenshots. It is maintained upstream as a Claude Code plugin, so this plugin points at it rather than copying it.

## Use the upstream skill

One-time install in the consumer repo:

```
/plugin marketplace add Leonxlnx/taste-skill
/plugin install taste-skill@taste-skill
```

Then invoke `taste-skill:design-taste-frontend` with the Skill tool when the task sets a new look, restyles a page or app screen, or a review says it reads generic. It has a page run and an app-screen run (`references/app-screens.md`); pick by whether people read the screen or work in it. Not in the skill listing: put the install lines in your report and apply the check below.

## Precedence

- The repo's design tokens and design system win over every palette, typeface, radius and spacing value Taste deals. With a design system, run its existing-brand mode (`--keep palette,type`) and take composition only.
- Where Taste and `web-interface-guidelines` disagree on style (Taste bans shadows at rest; the guidelines suggest layered shadows), the repo's design system decides; with none, shadows only on what floats (menus, dialogs, popovers).
- `ux-journey` owns placement, journey and states; Taste owns how it looks.

## Generic-tells check

Stack-neutral; for design specs, implementation self-checks and review. Each line is a tell and its replacement.

| Tell | Instead |
|---|---|
| Decorative gradients, glows, glass panels, blobs | flat surfaces from the tokens; a real image |
| Rows of identical icon-topped cards | a composition that fits the content: list, table, one large figure |
| Eyebrow labels or pill badges above headings; tiny uppercase tracked labels | put it in the heading or the first sentence, in sentence case |
| Hairline dividers and outlined boxes everywhere; shadows on things at rest | space and a tone step between surfaces |
| More than two typefaces, or many near-equal sizes | one family, few sizes with clear contrast between them |
| Monospace or index numbers (01, 02) as decoration | the text face; a real ordered list when order matters |
| Placeholder data: grey bars, lorem numbers, a fake dashboard | real or realistic data that adds up, or nothing |
| Several accent colours | one accent, on the primary action and at most one other thing |
| Headlines over two lines, centred everything | cut words; left-aligned, centre at most one moment |

Review: cite a finding as `taste: <tell>`. Minor by default; Important when the experience spec's chosen direction names it or the screen is a first impression (landing, onboarding, store listing).
