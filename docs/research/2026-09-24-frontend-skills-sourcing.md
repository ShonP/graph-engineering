# Frontend skills sourcing: tailwind, forms-i18n, turborepo

**Mode:** tech (the GE spec 4.1 sourcing pass, one dedicated search per skill)
**For:** forge-platform plan 7, task 35 (branch `plan-7/frontend-skills`)
**Date:** 2026-09-24

## Question

For each of the three competencies plan 7's frontend tasks need, is there a
plugin-shaped upstream to depend on (spec 4.2) or a licensed bare tree to vendor
by SHA? If neither, the skill is written from vendor docs plus what was measured,
each claim carrying its source.

## Answer

None adopted. Every candidate was either a general manual that needs a house
sibling to say the things plan 7 depends on (so the sibling would be the skill
anyway), or plugin-shaped and missing those facts. All three are written from
pinned vendor sources plus rung-1 measurements on the exact plan-7 pins; each
skill's header lists its sources and marks the measured rules.

## Reuse check (GE itself)

GE 0.13.1 already ships `react-rules`, `tanstack-query-rules`, `tanstack-router`,
`frontend-rules`, `ux-evidence`, the Playwright trio, `bruno`, `api-contract`,
`schemathesis`. `frontend-rules` names Tailwind, react-hook-form and
react-i18next in one line each, with no version and no mechanics. Nothing in GE
covers Tailwind v4 tokens, the form/i18n wiring, or Turborepo.

## Per skill

GitHub repository search, 2026-09-24 (`api.github.com/search/repositories`):
`turborepo skill` 43 hits, `tailwind skill claude` 217, `tailwindcss v4 skill`
48, `react-hook-form skill` 74, `react-i18next skill` 4, `i18next agent skill` 3;
vendor orgs searched directly (`tailwindlabs`, `react-hook-form`, `i18next`,
`vercel`, `vercel-labs`).

### turborepo

| Candidate | Shape | Verdict |
| --- | --- | --- |
| [vercel/turborepo](https://github.com/vercel/turborepo) `skills/turborepo/` @ `53629a02b776` (the 2.11.3 release commit, 2026-09-22), MIT | bare tree in the product repo, no `.claude-plugin/`; `metadata.version: 2.11.3` | **Rejected as a vendor, cited as the manual.** 951-line SKILL.md plus 20 reference files; Vercel-remote-cache-first (`turbo login`, `TURBO_TOKEN` in its CI recipes). Vendoring it needs a house sibling for remote cache off, pnpm, the hook contract - which is this skill. Its versioned `$schema` host is behind Vercel SSO (measured: 302 to `vercel.com/sso-api`). |
| [vercel/vercel-plugin](https://github.com/vercel/vercel-plugin) | plugin-shaped | no turborepo skill (a `turbopack` one only) |
| [secondsky/claude-skills](https://github.com/secondsky/claude-skills) @ `a0994f733b66`, `plugins/turborepo` 3.9.0, MIT | plugin-shaped | **Rejected.** A copy of Vercel's skill at `2.8.3-canary.4` - older than the upstream above, same gaps; author `maintainers@example.com`. |

### tailwind

| Candidate | Shape | Verdict |
| --- | --- | --- |
| secondsky `plugins/tailwind-v4-shadcn` @ `a0994f733b66` (574 lines), MIT | plugin-shaped | **Rejected, gap measured** (below). shadcn's own `:root` + `@theme inline` shape with a React `ThemeProvider`; `tailwind-merge ^3.3.1` range. |
| [jezweb/claude-skills](https://github.com/jezweb/claude-skills) @ `e875a6bfff80`, `plugins/frontend/skills/tailwind-theme-builder`, MIT | plugin-shaped marketplace | **Rejected.** A theme generator workflow, not rules for writing with a preset. |
| `tailwindlabs` org | - | no agent skill |

Gap measurement - lines in the candidate's SKILL.md mentioning each fact a plan-7
task depends on:

| fact | secondsky tailwind-v4-shadcn |
| --- | --- |
| `--color-*: initial` (palette reset) | 0 |
| `@source` (workspace packages are not scanned) | 0 |
| `extendTailwindMerge` (custom `text-*` tokens) | 0 |
| `prefers-color-scheme` (system dark without JS) | 0 |

### forms-i18n

| Candidate | Shape | Verdict |
| --- | --- | --- |
| secondsky `plugins/react-hook-form-zod` (734 lines) and `plugins/internationalization-i18n` (101 lines) @ `a0994f733b66`, MIT | plugin-shaped | **Rejected.** Forms: 0 lines on `z.input`/`z.output` generics, `aria-describedby`, `getFieldState`, or keyed messages. i18n: a generic multi-library overview, 0 on `returnNull`, `CustomTypeOptions`, namespaces. |
| [i18next/i18next-cli](https://github.com/i18next/i18next-cli) `skills/i18next-localization` @ `f470a2800d61` (i18next-cli 1.74.1), MIT; also shipped in [locize/locize-agents](https://github.com/locize/locize-agents) (plugin-shaped) | maintainer-authored | **Rejected, cited.** A one-time migration flow (hardcoded strings -> `t()`) driven by `npx i18next-cli` under `allowed-tools: Bash(npx i18next-cli *)`; the plugin bundles a remote Locize MCP server (OAuth, third-party data flow). Nothing on forms, typed keys, or a test that catches hard-coded copy. |
| `react-hook-form` org | - | no agent skill |

## Spiked (rung 1, 2026-09-24, exact plan-7 pins)

| Claim | Verdict | Edge case tried |
| --- | --- | --- |
| Remote cache off by config | VALIDATED | `TURBO_TOKEN=fake` exported: "Remote caching disabled (in configuration)" |
| A package without `lint` breaks the PostToolUse hook | VALIDATED | root `pnpm run lint <file>` -> "Could not find task `<file>`" |
| Root untracked files bust the turbo cache | **INVALIDATED** | a stray root file left all 3 tasks cached; the claim was dropped |
| `--frozen-lockfile` refuses drift | VALIDATED | missing lockfile and an unlocked new dependency, both exit 1 |
| `--color-*: initial` removes the palette | VALIDATED | `bg-red-500` emits nothing; arbitrary `bg-[#ff0000]` still emits |
| Workspace UI package needs `@source` | VALIDATED | class only in `packages/ui/src`: absent until `@source` added |
| `@theme inline` defeats dark overrides | VALIDATED | inline bakes `oklch(...)`; plain `@theme` emits `var(--color-bg)` |
| tailwind-merge drops a colour next to a custom `text-*` size | VALIDATED | `twMerge('text-fg text-body')` -> `text-body`; fixed by `extend.theme.text` |
| "The resolver import path changed across majors" (plan text) | **INVALIDATED** | `@hookform/resolvers/zod` identical at v1.0.0 through v5.9.1; zod's own entry moved |
| `returnNull: false` needed | PARTIAL | already the default on i18next 26.4.2; kept for intent |
| Field wiring + DOM walk | VALIDATED | jsdom: `aria-describedby` gains the error id; a literal "Click here" is reported |
