---
name: forms-i18n
description: Use when writing or reviewing React forms or user-facing copy - react-hook-form 7 with zod 4 through @hookform/resolvers 5, an accessible Field (label, aria-invalid, aria-describedby, errors from formState), validation messages as i18n keys, react-i18next 17 + i18next 26 init with namespaces and typed keys, keys-not-sentences, and the DOM-walk test that catches hard-coded copy.
---

# Forms and i18n - keys, not sentences

Written for **react-hook-form 7.88.0** (npm, 2026-09-11), **@hookform/resolvers 5.9.1**
(2026-08-17), **zod 4.6.5** (2026-09-13), **i18next 26.4.2** (2026-09-03), **react-i18next
17.0.15** (2026-09-21), React 19.3.0, TypeScript 6.0.3. Rules marked *measured* were run on
2026-09-24 against those exact versions (node + jsdom 30.1.1 + Testing Library 16.3.3 for the DOM
ones, `tsc` 6.0.3 for the typing ones) - rung 1.

Sources (fetched 2026-09-24):
- https://github.com/react-hook-form/resolvers/blob/v5.9.1/README.md (Zod section, input/output types)
- https://react-hook-form.com/docs/useform, `/docs/useform/getfieldstate`, `/advanced-usage`
  (Accessibility) - `react-hook-form/documentation` @ `3ac1fe025494`
- https://zod.dev/error-customization - `colinhacks/zod` @ `2bf7b0630d53`
- https://www.i18next.com/overview/configuration-options - `i18next/i18next-gitbook` @ `ea65e2028dc1`
- https://react.i18next.com/latest/usetranslation-hook - `i18next/react-i18next-gitbook` @ `0c8bde5e7659`
- https://www.i18next.com/overview/typescript (`CustomTypeOptions`)

## When to apply

- Any form, field, validation schema, or visible string in a `*.tsx`.
- Any catalogue under `i18n/` or `locales/`, and the i18n init.

## Rules

### Imports - which path moved, and which did not

- The resolver is `import { zodResolver } from '@hookform/resolvers/zod'`. **That path has not
  changed across resolver majors** - identical in the README at v1.0.0, v2.0.0, v3.0.0, v4.0.0,
  v5.0.0 and v5.9.1 (read at each tag). The plan note "the resolver import path changed across
  majors" is wrong for the resolver.
- **What moved is zod's own entry point.** zod 3.25.x shipped v4 at `zod/v4`; zod 4.x serves v4
  at the root `zod` and keeps legacy v3 at `zod/v3`. *Measured* on 4.6.5: `zod` and `zod/v4`
  export the same `object`. Write `import { z } from 'zod'`. `@hookform/resolvers` 5.9.1 peers
  `zod ^3.25.0 || ^4.0.0` and types against `zod/v4/core`.
- Resolvers 5 infer the schema's **input and output types separately**. Do not pass one generic
  to `useForm<T>` - let it infer from `resolver`, or pass all three:
  `useForm<z.input<typeof S>, unknown, z.output<typeof S>>`. A `.default()` or `z.coerce` field
  is where a single generic breaks (resolvers README, Zod section).

### Validation messages are i18n keys

- Every rule carries a key, never a sentence: `z.string().trim().min(1, { error:
  'hello:form.name.required' })`. *Measured:* `zodResolver` passes it through unchanged as
  `errors.name.message`, with `type: 'too_small'`.
- zod's built-in messages are English sentences (*measured*: `"Too small: expected number to be
  >=10"`). Catch every rule you did not key with a global fallback, set once at module level in
  the app's boot: `z.config({ customError: () => 'common:form.invalid' })`. *Measured:* a
  per-rule `error` still wins; everything else becomes the fallback key.
  https://zod.dev/error-customization
- The component renders `t(error.message)`. Because the message is a runtime string, typed keys
  cannot check it - the test under Verify asserts each schema key exists (`i18n.exists`).

### The accessible `Field`

One component owns the wiring so no form re-derives it:

```tsx
type FieldProps = { name: string; label: string; hint?: string; children: ReactElement<Record<string, unknown>> };

// label and hint arrive translated: the caller writes label={t('form.name.label')}, so the key is typed there.
export function Field({ name, label, hint, children }: FieldProps) {
  const { t } = useTranslation();
  const { register, getFieldState } = useFormContext();
  const formState = useFormState({ name });            // subscribe to this field only
  const { error } = getFieldState(name, formState);
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;
  return (
    <div>
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, { id, ...register(name), 'aria-invalid': error ? true : undefined,
                                'aria-describedby': describedBy })}
      {hint && <p id={hintId}>{hint}</p>}
      {/* a runtime key from the schema: untyped by nature, so the Verify test proves it exists */}
      {error?.message && <p id={errorId}>{t(error.message as never)}</p>}
    </div>
  );
}
```

- *Measured* with the pins above: before submit `aria-invalid` is absent and
  `aria-describedby` names only the hint; after an invalid submit `aria-invalid="true"`,
  `aria-describedby` names hint **and** error, the error text is the translated key, and focus
  is on the first invalid input (`shouldFocusError`, default on).
- `getFieldState(name, formState)` needs the `formState` argument unless formState was already
  read through `useForm`/`useFormContext`/`useFormState` - passing `useFormState({ name })`
  satisfies it and scopes re-renders to the field. https://react-hook-form.com/docs/useform/getfieldstate
- A real `<label htmlFor>`; never a placeholder as the label. `noValidate` on the `<form>` so the
  browser's untranslated bubbles never show; the schema is the validator.
- Submit state from `formState.isSubmitting` or the mutation's `isPending` (react-rules 6.11),
  never a hand-rolled `useState`.
- The server's field errors (problem+json) map back with `setError(field, { message: key })`,
  where the key comes from the error code, not the server's English `detail`.

### i18n init (i18next 26 + react-i18next 17)

```ts
await i18n.use(initReactI18next).init({
  lng: 'en', fallbackLng: 'en',
  ns: ['common', 'hello'], defaultNS: 'common',
  resources: { en: { common, hello } },   // bundled JSON; no HTTP backend
  returnNull: false,
  interpolation: { escapeValue: false },  // React already escapes
});
```

- Init completes **before** the first render (the app shell awaits it), so no Suspense fallback
  flashes untranslated keys.
- `returnNull: false` - *measured* on 26.4.2 it is already the default (a `null` value falls back
  to the key, and the typings default `returnNull` to `false` too); set it anyway so the intent
  survives a major. `returnEmptyString` defaults to `true` (*measured*: `""` renders as `""`):
  never commit `""` as a placeholder translation.
  https://www.i18next.com/overview/configuration-options
- **One namespace per app or package** (`common` for the shared UI package, `hello` for the
  hello app); files `i18n/<ns>.<lng>.json`. A component reads its own namespace with
  `useTranslation('hello')`; to reach another, request both - `useTranslation(['hello',
  'common'])` then `t('common:retry')` or `t('retry', { ns: 'common' })`. *Measured:* with typed
  keys, `t('common:retry')` from `useTranslation('hello')` alone is a type error.
  https://react.i18next.com/latest/usetranslation-hook
- Typed keys make a misspelt key a compile error (*measured*: `t('titel')` fails `tsc` with "Did
  you mean 'title'?"):

  ```ts
  import 'i18next';
  import type common from './common.en.json';
  import type hello from './hello.en.json';
  declare module 'i18next' {
    interface CustomTypeOptions { defaultNS: 'common'; resources: { common: typeof common; hello: typeof hello } }
  }
  ```

### Keys, not sentences

- No visible copy in a component: text nodes, `aria-label`, `placeholder`, `title`, `alt` all come
  from `t()`. Only `en` is written unless a task says otherwise.
- Keys name the **place and purpose** (`hello:form.name.required`), never the English text
  (`"Enter a name"` as a key). Interpolate values (`"Hello {{name}}"`), never concatenate
  translated fragments - word order differs by language. Plurals use i18next's `_one`/`_other`
  suffixes with `count`.
- User data (a name, a greeting the API returned) is not copy; wrap its container in
  `data-i18n-ignore` so the DOM walk skips it.
- No PII in keys, catalogue values or test fixtures.

## Anti-patterns

- `useForm<FormValues>()` with a single generic next to `zodResolver` on a schema with
  `.default()`/`coerce`.
- An English sentence in a zod rule, or no global `customError` fallback.
- A `Field` without `aria-describedby` to its error, or `aria-invalid="false"` on every
  untouched input.
- `t` called with a sentence; string concatenation around `t()`; `""` in a catalogue.
- A `useState` mirror of form values (react-hook-form owns them).

## Review focus

- Every new string: a key in the right namespace, present in the catalogue, typed.
- Every new form field: through `Field`, its schema rule keyed, its error reachable by a screen
  reader (`aria-describedby`), and a test for the error state.

## Verify

The DOM-walk test (*measured*: passes on a clean form, and reports `["Click here"]` when a
literal is added) - one per rendered state, in the component's Vitest file:

```ts
// catalogue values become matchers; {{vars}} match anything
export function catalogueMatchers(i18n: I18n, lng = 'en'): RegExp[] {
  const out: RegExp[] = [];
  const walk = (v: unknown) => typeof v === 'string'
    ? out.push(new RegExp('^' + v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\\\{\\\{[^}]+\\\}\\\}/g, '.+') + '$'))
    : v && typeof v === 'object' && Object.values(v).forEach(walk);
  walk(i18n.store.data[lng]);
  return out;
}
export function literalsNotInCatalogue(root: Element, matchers: RegExp[]): string[] {
  const found: string[] = [];
  const check = (s: string | null) => { const v = s?.trim(); if (v && !matchers.some((m) => m.test(v))) found.push(v); };
  const w = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  for (let n: Node | null = w.currentNode; n; n = w.nextNode()) {
    const el = n.nodeType === Node.TEXT_NODE ? n.parentElement : (n as Element);
    if (el?.closest('[data-i18n-ignore]')) continue;
    if (n.nodeType === Node.TEXT_NODE) check(n.nodeValue);
    else for (const a of ['aria-label', 'placeholder', 'title', 'alt']) check((n as Element).getAttribute(a));
  }
  return found;
}
// in each state's test:
expect(literalsNotInCatalogue(container, catalogueMatchers(i18n))).toEqual([]);
// and for each schema:
expect(schemaKeys.filter((k) => !i18n.exists(k))).toEqual([]);
```

It cannot tell a hard-coded `"Retry"` from `t('common:retry')` when the two strings are equal;
the typed keys and review cover that case.

```bash
pnpm typecheck      # typed keys: a misspelt or foreign-namespace key fails here
pnpm test           # the DOM walk, the schema-key test, the Field error-state tests
pnpm -r ls --depth 0 react-hook-form @hookform/resolvers zod i18next react-i18next
# expect 7.88.0, 5.9.1, 4.6.5, 26.4.2, 17.0.15
```
