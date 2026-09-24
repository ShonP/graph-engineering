---
name: tailwind
description: Use when writing or reviewing Tailwind CSS v4 styling - the @theme token preset, semantic CSS-variable tokens with light and dark values, @tailwindcss/vite setup, @source for workspace packages, the no-literal-colour rule and its check, and cn() with clsx + tailwind-merge (including the custom-token merge trap). Covers shadcn-style copied components onto house tokens.
---

# Tailwind CSS v4 - tokens, not colours

Written for **tailwindcss 4.3.3** + **@tailwindcss/vite 4.3.3** (npm, 2026-07-16),
**tailwind-merge 3.7.0**, **clsx 2.1.1**, shadcn CLI 4.21.0. Rules marked *measured* were run on
2026-09-24 with `@tailwindcss/cli` 4.3.3 (same engine and scanner as the Vite plugin; the plugin
itself was not run) and tailwind-merge 3.7.0 in node - rung 1. `tailwindcss.com/docs` is
unversioned, so it is pinned by its source repo commit.

Sources (fetched 2026-09-24):
- https://tailwindcss.com/docs/installation/using-vite - `tailwindlabs/tailwindcss.com` @ `7f92c2213315`
- https://tailwindcss.com/docs/theme - same commit (`@theme`, `inline`, `static`, `--color-*: initial`)
- https://tailwindcss.com/docs/dark-mode - same commit (`prefers-color-scheme`, `@custom-variant`)
- https://tailwindcss.com/docs/detecting-classes-in-source-files - same commit (`@source`)
- https://ui.shadcn.com/docs/theming - `shadcn-ui/ui` @ `98a1fe67b439` (the `:root`/`.dark` + `@theme inline` token shape)
- https://github.com/dcastil/tailwind-merge/blob/v3.7.0/docs/configuration.md (`extendTailwindMerge`)

## When to apply

- Any `*.css` file, and any `className` in a `*.tsx`.
- Adding a token, a component, a copied shadcn component, or dark-mode behaviour.

## Rules

### Setup: Vite plugin, CSS-first, one import

- Vite: `import tailwindcss from '@tailwindcss/vite'` and `plugins: [tailwindcss(), react()]`.
  No `tailwind.config.js`, no `postcss.config.js`, no `autoprefixer` - v4 is configured in CSS.
  https://tailwindcss.com/docs/installation/using-vite
- **Exactly one `@import "tailwindcss"`** per compiled stylesheet, and it lives in the token
  preset (`@forge/config/tailwind.css` in the house layout). An app's entry CSS imports the
  preset only. *Measured:* importing `tailwindcss` in both the app CSS and the preset emits
  preflight twice (9,280 vs 5,186 bytes for the same classes).
- `packages/config` exports the preset (`"exports": { "./tailwind.css": "./tailwind.css" }`); the
  app writes `@import "@forge/config/tailwind.css";`. *Measured:* resolved through the pnpm
  workspace symlink.

### `@source`: workspace packages are not scanned by default

- Automatic detection skips `node_modules` and git-ignored paths. A component package reached
  through a workspace symlink is therefore **invisible**: *measured*, a class used only in
  `packages/ui/src` generated no CSS in the app until the app's entry CSS added
  `@source "../../../packages/ui/src";`. A missing `@source` fails silently - the element just
  renders unstyled. https://tailwindcss.com/docs/detecting-classes-in-source-files
- Rule: each app's entry CSS carries one `@source` line per workspace package whose components it
  renders, relative to that CSS file.

### Tokens: semantic names, CSS variables, light and dark

- Tokens are Tailwind **theme variables** in `@theme`; each `--color-<name>` produces
  `bg-<name>`, `text-<name>`, `border-<name>` and friends. https://tailwindcss.com/docs/theme
- **Semantic names only**: `bg`, `fg`, `muted`, `accent`, `danger`, `border`, ... - never a hue
  (`blue`, `coral`). Radius, spacing and the type scale are tokens too (`--radius-*`,
  `--spacing`, `--text-*`).
- **Reset the default palette**: `--color-*: initial;` first in the `@theme` block. *Measured:*
  after the reset, `bg-red-500` generates nothing, so a palette colour cannot ship by accident.
  It also fails **silently**, which is why the check under Verify exists.
- Light values go in `@theme`; dark values **override the same variables** outside it, both
  system-driven and by class (`.dark` on `<html>` for a manual toggle):

  ```css
  @import "tailwindcss";
  @theme {
    --color-*: initial;
    --color-bg: oklch(0.99 0 0);
    --color-fg: oklch(0.21 0.01 260);
    --color-danger: oklch(0.58 0.22 27);
    --radius-md: 0.5rem;
  }
  :root { color-scheme: light dark; }
  @media (prefers-color-scheme: dark) {
    :root:not(.light) { --color-bg: oklch(0.18 0.01 260); --color-fg: oklch(0.96 0 0); }
  }
  .dark { color-scheme: dark; --color-bg: oklch(0.18 0.01 260); --color-fg: oklch(0.96 0 0); }
  .light { color-scheme: light; }
  ```

  Tailwind emits `@theme` into `@layer theme`; the overrides are unlayered, so they win.
- **Plain `@theme`, not `@theme inline`, for anything dark mode overrides.** *Measured:* with
  `inline` the utility bakes the literal (`background-color: oklch(0.99 0 0)`) and the dark
  override is ignored; with plain `@theme` it is `var(--color-bg)`. `inline` is only for a
  theme variable that references another variable (the shadcn shape below).
- Because the tokens flip, **components do not write `dark:` for colour.** `dark:` remains for
  non-colour differences (an image swap). By default `dark:` follows `prefers-color-scheme` only
  and ignores a `.dark` class unless `@custom-variant dark (&:where(.dark, .dark *));` is declared.
  https://tailwindcss.com/docs/dark-mode
- Each dark token pair meets WCAG AA contrast (4.5:1 text, 3:1 large text and UI boundaries) in
  **both** schemes; check the pair, not the colour.

### No literal colour, anywhere in components

- Components and apps never contain a colour value: no hex (`#fff`, `#FFFFFF`, `#ffffff80`), no
  `rgb()`/`hsl()`/`oklch()`, no arbitrary colour (`bg-[#f00]`, `text-[oklch(...)]` -
  *measured*: arbitrary values still compile after the palette reset), no palette utility
  (`bg-red-500`), no `style={{ color: ... }}`. Colours exist in one file: the preset.
- A one-line grep misses uppercase, 3-, 4- and 8-digit hex, functional colours, named colours
  (`bg-[red]`, `backgroundColor: 'red'`), `text-white` and the 4.3 palettes (`mauve`, `olive`,
  `mist`, `taupe`), and flags `border-t-bg`, `ring-offset-bg`, `placeholder-shown:` and `#1234` in
  a comment. Use the shipped script under Verify; its fixtures cover every one of those.

### Copied shadcn components onto house tokens

- shadcn's v4 theming declares raw variables in `:root`/`.dark` (`--background`, `--primary`)
  and maps them with `@theme inline { --color-background: var(--background); }`, so its
  components use `bg-primary`, `text-primary-foreground`. https://ui.shadcn.com/docs/theming
- After `shadcn add`, rewrite the component's colour classes to the house token names (or add
  the shadcn names as tokens in the preset - pick one, repo-wide). A class naming an undeclared
  token (a leftover `bg-primary`) compiles to nothing and the button renders transparent.
- The copied file is owned: keep its `cva` variants, remove what the house does not use.

### `cn()`: clsx + tailwind-merge, configured for the tokens

```ts
import { clsx, type ClassValue } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

// Every custom --text-* size and --color-* token the preset defines, by name.
const twMerge = extendTailwindMerge({
  extend: { theme: { text: ['caption', 'body', 'title'], color: ['bg', 'fg', 'muted', 'accent', 'danger'] } },
});
export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
```

- **Why the config is not optional** - *measured* on tailwind-merge 3.7.0: the default
  `twMerge('text-fg text-body')` returns `text-body`, silently dropping the colour, because an
  unknown `text-*` is read as a colour and two colours conflict. With `extend.theme.text` it
  returns `text-fg text-body`. Every new `--text-*` token is added to this list in the same
  change. https://github.com/dcastil/tailwind-merge/blob/v3.7.0/docs/configuration.md
- `cn()` is for merging a component's defaults with a caller's `className`; the caller's classes
  come last so they win.

## Anti-patterns

- `@theme inline` for tokens that dark mode overrides.
- A second `@import "tailwindcss"`; a `tailwind.config.js` in a v4 repo.
- An app without `@source` for the workspace UI package it renders.
- A colour literal or palette utility in `src/`; `dark:bg-...` on a component whose token already
  flips.
- Plain `twMerge` (or `cn` without the token config) over a class list that uses a custom
  `text-*` size.
- A shadcn component committed with `bg-primary`-style names the preset does not define.

## Review focus

- Is every colour a token that exists in the preset? Does a new token have a dark value and a
  contrast check in both schemes?
- Does a new `--text-*` or `--color-*` token also appear in `cn()`'s merge config?
- Does a new UI package appear in each consuming app's `@source`?

## Verify

`scripts/check-no-literal-colours.sh` in this skill's directory (bash; node does the parsing).
The preset is the first argument and the only exemption; its `--color-*` declarations are the
token list, so a class naming anything else - a palette colour, `text-white`, a leftover shadcn
`bg-primary` - is reported. Paths are separate arguments: zsh does not word-split `$SRC`, and
the script exits 2 on a missing path, a preset with no token, or nothing to scan, so a mis-split
list fails instead of passing on nothing. Tested by `tests/test_check_no_literal_colours.sh`
against good and bad fixtures (run by the plugin's `scripts/check-skill-scripts.sh`).

```bash
# No literal colour outside the preset: hex, functional and named colours, arbitrary colour
# values, colour-bearing style props, and colour utilities that name no declared token.
bash "<this skill's dir>/scripts/check-no-literal-colours.sh" packages/config/tailwind.css apps packages
# expect: no output, exit 0 (1 = violations as file:line: match; 2 = usage error)

# Versions the rules were written for.
pnpm -r ls --depth 0 tailwindcss @tailwindcss/vite tailwind-merge   # expect 4.3.3, 4.3.3, 3.7.0
```
