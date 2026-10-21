---
name: frontend-rules
description: Apply for any frontend UI work (React, Flutter, SwiftUI, Compose, game UI), Tailwind, forms, routing, i18n, frontend architecture, components, pages, client API code, or design-system work.
---

# Frontend Rules

The first section applies to every UI stack. The rest is for React + Tailwind frontend work.

## Reusable components (every UI stack)

- One component per visual pattern. Before writing a widget, check the project's component library
  (kit, design system, `components/`); if the pattern exists, use it.
- A different look is a **variant of the same component**, never a copy: the component takes an optional
  style/art parameter (a token, theme role, skin role or variant name) that defaults to today's look.
  Seasonal or brand themes change those roles only, never component code.
- A missing variant or slot is a gap in the shared component: extend the component (new optional
  parameter, default unchanged) instead of hand-building the look at the call site.
- Shared components hold no product or game names; product-specific look lives in the theme/skin.
- Text-holding frames declare their content insets/padding in the theme, so swapped art never clips text.
- Reviewers flag a hand-built copy of an existing component, or a second copy of a new pattern, as
  Important.

## Edge states (every UI stack)

- Every query renders a loading, empty and error state; the empty state offers the next action.
- A submit control is disabled while its request is pending.
- Missing is not zero: a null value renders a no-value placeholder, never `0`.

## Defaults

- Mobile-first.
- Simple, sleek Apple-style design.
- Tailwind CSS for all styling.
- No inline styles, no `sx` prop, no CSS-in-JS.
- Colour and dark mode follow the `tailwind` skill: never hardcode a colour; every colour is a
  semantic token declared in the `@theme` preset (Tailwind v4, CSS-first; no `tailwind.config.js`).
  Tokens flip light/dark themselves, so components do not write `dark:` for colour; `dark:` is only
  for non-colour differences.
- Use logical properties: `ms-`, `me-`, `ps-`, `pe`; never left/right.
- Use `FC` for components.
- Remove unused imports and variables.
- Prefix interfaces with `I`, e.g. `IComponentProps`.

## Component Structure

```text
Component/
  Component.tsx
  Component.types.ts
  Component.utils.ts
  Component.constants.ts
  Component.hooks.ts
  Component.queries.ts
  Component.mutations.ts
  index.ts
```

## Libraries

- `react-hook-form` for forms.
- `@tanstack/react-query` for data fetching.
- TanStack Router for routing.
- `react-i18next` for i18n; catalogues and their paths follow the `forms-i18n` skill
  (`i18n/<ns>.<lng>.json`); update only the `en` catalogues unless explicitly asked.
- `lucide-react` for icons.
- `axios`; use `instance.ts`.

## Folders

Use: `pages/`, `components/`, `utils/`, `types/`, `constants/`, `hooks/`, `queries/`, `mutations/`, `api/`.

## Notes

- Ignore prettier spacing/line-break errors.
- Keep components small; split logic into hooks/utils/constants/types.
