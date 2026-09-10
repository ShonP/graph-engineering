---
name: frontend-rules
description: Apply for React, frontend UI, Tailwind, forms, routing, i18n, frontend architecture, components, pages, client API code, or design-system work.
---

# Frontend Rules
Harvested from the owner's global rule packs on 2026-09-10 (spec 4.3); the plugin copy is the portable one.

Use for React + Tailwind frontend work.

## Defaults

- Mobile-first.
- Simple, sleek Apple-style design.
- Tailwind CSS for all styling.
- No inline styles, no `sx` prop, no CSS-in-JS.
- Use `dark:` variants for dark mode.
- Never hardcode colors; use design tokens/theme via Tailwind config.
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
- `react-i18next` for i18n; update only `en.json` unless explicitly asked.
- `lucide-react` for icons.
- `axios`; use `instance.ts`.

## Folders

Use: `pages/`, `components/`, `utils/`, `types/`, `constants/`, `hooks/`, `queries/`, `mutations/`, `api/`.

## Notes

- Ignore prettier spacing/line-break errors.
- Keep components small; split logic into hooks/utils/constants/types.
