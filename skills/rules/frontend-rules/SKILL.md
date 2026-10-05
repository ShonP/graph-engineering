---
name: frontend-rules
description: Apply for React, frontend UI, Tailwind, forms, routing, i18n, frontend architecture, components, pages, client API code, or design-system work.
---

# Frontend Rules

Use for React + Tailwind frontend work.

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
