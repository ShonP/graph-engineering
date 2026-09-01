---
name: react-rules
description: Use when writing or reviewing React code - waterfalls, bundle size, client-side data fetching, re-render optimization in the React Compiler era, rendering and JS performance, and React 19 patterns. Rule IDs match Vercel's react-best-practices pack.
---

# React Rules

Condensed from Vercel's react-best-practices pack (https://github.com/vercel-labs/agent-skills, v1.0.0); rule IDs match the source. Server-only sections (RSC, server actions, hydration) are dropped - re-check the source when working in an RSC/SSR app. **House rules of the consuming repo win on every conflict**; framework-integration detail lives in the tanstack-query-rules and tanstack-router skills.

## 1. Eliminating Waterfalls - CRITICAL

- **1.1** Check cheap sync conditions before awaited flags/queries: `if (cond) { const flag = await getFlag() }`, never `await` first when a local guard can short-circuit.
- **1.2** Defer `await` into the branch that uses it; early-return paths must not pay for fetches they don't use.
- **1.3** Partial dependencies: start independent promises immediately, chain dependents off the promise (`userPromise.then(u => fetchProfile(u.id))`), then one `Promise.all`. No `better-all` dependency - plain promise composition.
- **1.4** Multi-step async flows (repository methods, route loaders, RPC wrappers): kick off independent operations before the first `await`; never a sequential `await` chain of independent calls. (Coupled multi-table writes belong in one server-side transaction, not client-side sequencing.)
- **1.5** Independent async operations run under `Promise.all`, not sequential awaits. Distinct queries only - never per-item request fan-out; batch server-side.
- **1.6** Don't block a whole route on one slow query: give each section its own query + skeleton (or Suspense boundary with `useSuspenseQuery`) so the shell paints immediately. Skip for layout-critical data or when it causes layout shift.

## 2. Bundle Size - CRITICAL

- **2.1** Heavy third-party barrel imports: only act on measured build/dev cost (modern bundlers tree-shake prod). Respect the repo's own barrel conventions.
- **2.2** Load large data/modules only when the feature activates (`import()` on toggle), not in the initial bundle.
- **2.3** Analytics/error-tracking init deferred until after first paint (dynamic `import()`), never in the critical path.
- **2.4** Heavy components (charts, editors, camera/scanner) load via `React.lazy` + route-level or interaction-level `import()` - not in the main chunk.
- **2.5** Dynamic import paths must be statically analyzable by Vite: literal paths or an explicit map of `() => import('./x')` thunks - never `import(variable)`.
- **2.6** Preload on intent: hover/focus triggers `import()` of the heavy chunk; use the router's intent preloading for routes.

## 4. Client-Side Data Fetching - MEDIUM-HIGH

- **4.1** N component instances must share one global listener (keydown, resize): module-level registry (Map of callbacks) + single `addEventListener`, not a listener per hook instance.
- **4.2** Touch/wheel/scroll listeners that don't `preventDefault()` get `{ passive: true }`.
- **4.3** Server state lives in the query library (TanStack Query or equivalent) - never `useEffect` + fetch-and-`setState`. Query dedup/caching comes free; retry/staleTime config is central.
- **4.4** localStorage: versioned key constants, minimal fields only, every `getItem`/`setItem` in try/catch (Safari private mode throws). Never tokens/PII. Server state never mirrors into localStorage - it belongs to TanStack Query.

## 5. Re-render Optimization - MEDIUM

**Compiler-era posture (repos that adopt React Compiler v1.0+):** write pure
components; the compiler auto-memoizes every component/hook it compiles, as precise or better than
hand-written `useMemo`/`useCallback`/`memo` (it tracks fine-grained dependencies per-expression, not
per-hook-call). A hand-written `useMemo`/`useCallback`/`memo` is no longer the default reflex for
"this might re-render too often" - reach for one only with a measured reason (a `react-scan`-visible
hot spot, an intentionally stable ref identity for an external subscription, etc.), and say why in a
comment. **The rules below don't go away** - the compiler's memoization is only correct if the
component is actually pure, so 5.1 (derived-values-in-render, not `useState`+`useEffect`), 5.4
(no-component-in-component), 5.7 (primitive effect deps), and 5.11 (functional `setState`) are load-bearing:
violate them and the compiler can silently cache a stale value exactly like a hand-written
`useMemo` with a wrong dependency array would. The rest of this section (5.2–5.3, 5.5–5.6, 5.8–5.15)
still applies where it targets something the compiler doesn't do at all (derived subscriptions,
`useRef` vs `useState`, `startTransition`, `useDeferredValue`, lazy `useState` initializers, etc.).

**Verify, don't just trust:** after touching a re-render-sensitive screen, profile it with
`react-scan` (dev dependency, not wired into the app bundle - run it against the dev server locally,
e.g. via its CLI/browser extension against localhost) and look for components flashing on
unrelated state changes. Compiler-memoized code can still re-render more than expected if a prop
passed in is referentially unstable for a reason outside the compiler's reach (e.g. a new object
literal coming from a parent the compiler didn't compile, such as a library component from
`node_modules`).

**Known incompatibility - react-hook-form `useController`/`fieldState` (found adopting P4):**
components that call `useController` **directly** (not via `<Controller render={...}>`) and read
`.fieldState.error` can render a stale (never-updating) error: react-hook-form doesn't guarantee a
new `fieldState` reference on every relevant change, and only `formState.errors` (not
`useController`'s own `fieldState`) got an upstream fix for this in react-hook-form 7.79.0. Repro:
a field's validity depends on a sibling field (e.g. "enter a size once a label is entered") and the
user never directly types into the field showing the error - the compiled component's cached JSX
never re-evaluates the `fieldState.error` check. Confirmed **not** an issue for the
`<Controller control={control} name="x" render={renderXField} />` render-prop pattern (`Controller`
itself lives in `node_modules`, uncompiled; a lowercase `renderXField` callback isn't recognized as
a component by the compiler's naming heuristic either) - only the direct-`useController`-in-a-
component shape is affected. Fix: add a `'use no memo'` directive as the first statement in the
affected component - never disable the compiler repo-wide for a single component's library quirk. Revisit once react-hook-form ships the `useController` equivalent of its 7.79.0 fix.

- **5.1** Derived values computed during render - never `useState` + `useEffect` to sync a value computable from props/state.
- **5.2** State only read inside callbacks shouldn't be subscribed to - read on demand in the handler (e.g. `window.location.search` / router state getters) instead of a hook subscription.
- **5.3** No `useMemo` around simple primitive expressions (`a || b`, arithmetic) - the hook costs more than the expression.
- **5.4** Never define a component inside another component - new type every render = full remount (lost focus/state). Extract and pass props.
- **5.5** Memoized components with non-primitive default params: hoist the default (`const NOOP = () => {}`) to module scope or memoization breaks.
- **5.6** Expensive subtree work goes into a `memo`ized child so parent early-returns (loading/empty) skip it entirely.
- **5.7** Effect deps are primitives (`user.id`), not objects (`user`); derive booleans outside the effect so it fires on transitions, not every value change.
- **5.8** User-action side effects live in the (named) event handler, not in state + `useEffect` watching that state.
- **5.9** One `useMemo`/`useEffect` per concern: split computations/effects with different dependency sets instead of one combined hook that reruns everything.
- **5.10** Subscribe to derived booleans (`useMediaQuery('(max-width: 767px)')`), not continuous values (raw width) that re-render every pixel.
- **5.11** setState depending on current state uses the functional form (`setItems(curr => ...)`) - stable callbacks, no stale closures.
- **5.12** Expensive `useState` initializers use the lazy function form (`useState(() => build())`), especially JSON.parse/localStorage/index building.
- **5.13** Frequent non-urgent updates (scroll trackers, background syncs) wrapped in `startTransition`.
- **5.14** Expensive renders derived from fast-changing input: `useDeferredValue(query)` + `useMemo` on the deferred value (search/filter over large lists).
- **5.15** Frequently-changing values that don't drive UI (mouse position, interval counters, transient flags) go in `useRef`, not `useState`.

## 6. Rendering Performance - MEDIUM

- **6.1** Animate a wrapper `<div>`, not the `<svg>` element itself (GPU acceleration).
- **6.2** Long scrolling lists: `content-visibility: auto` + `contain-intrinsic-size` on items (as a token/utility class, not inline styles).
- **6.3** Static JSX (skeleton rows, big static SVGs) hoisted to module-level constants.
- **6.4** SVG assets run through SVGO with reduced precision.
- **6.7** Expensive show/hide toggles preserve state with React `<Activity mode=...>` (React 19.2+; verify availability) instead of unmounting.
- **6.8** Any third-party `<script>` in `index.html` carries `defer` or `async`.
- **6.9** Numeric conditionals in JSX use explicit comparison (`count > 0 ? x : null`), never bare `{count && x}` which renders `0`.
- **6.10** Known-next resources: `preconnect`/`preload`/`preloadModule` from `react-dom` (e.g. the storage/CDN origin, next-route chunks on hover).
- **6.11** Action-pending UI from `useTransition`'s `isPending` or TanStack `mutation.isPending` - never a hand-managed `isLoading` `useState`.

## 7. JavaScript Performance - LOW-MEDIUM (hot paths)

- **7.1** Batch DOM writes, then reads - never interleave style writes with `offsetWidth`/`getBoundingClientRect`. Prefer class toggles.
- **7.2** Repeated `.find()` by key over a list → build a `Map` once, O(1) lookups.
- **7.3** Hoist invariant property chains and `arr.length` out of hot loops.
- **7.4** Pure functions called repeatedly with the same input during render (slugify, formatters) → module-level `Map` cache.
- **7.5** Cache `localStorage`/cookie reads in a module Map; invalidate on `storage` events and visibility changes.
- **7.6** Multiple `.filter()`/`.map()` passes over the same array → one loop distributing into buckets.
- **7.7** Non-critical post-action work (analytics, prefetch, recent-items persistence) deferred via `requestIdleCallback` (with `setTimeout` fallback).
- **7.8** Expensive array comparisons check `length` inequality first.
- **7.9** Return early once the result is determined; no accumulate-then-check loops.
- **7.10** No `new RegExp(...)` in render - hoist to module scope or `useMemo` on its inputs; beware `/g` `lastIndex` state.
- **7.11** `.map().filter(Boolean)` → single-pass `.flatMap()`.
- **7.12** Min/max via a single loop (or `Math.min/max` for small arrays), never sort-then-take-first.
- **7.13** Repeated membership checks use `Set`/`Map`, not `array.includes` in a loop.
- **7.14** Never `.sort()`/`.reverse()`/`.splice()` props or state arrays - use `.toSorted()`/`.toReversed()`/`.toSpliced()` (or spread-then-sort).

## 8. Advanced Patterns - LOW

- **8.1** Functions from `useEffectEvent` never appear in dependency arrays - call them from effects, don't depend on them.
- **8.2** App-wide one-time init (SDKs, observability) guarded at module level, not in a component effect that reruns per mount (StrictMode double-invokes).
- **8.3** Subscriptions needing the latest callback without re-subscribing: keep the handler in a ref updated on render; subscribe once with a stable wrapper.
- **8.4** Prefer React 19's `useEffectEvent` for reading latest props/state inside long-lived effects without widening the dependency array.

## Review focus

- **Waterfalls (§1) and re-renders (§5) are the highest-value checks.** Verify independent awaits actually run under `Promise.all`; derived values computed in render, not synced through `useState` + `useEffect`; no component defined inside another component.
- **Heavy components** (charts, scanner, camera, editors) load via `React.lazy` plus a statically-analyzable `import()`, never from the main chunk (§2.2-2.6).
- **React-Compiler purity** (where adopted): components must be pure - the compiler's memoization is only correct on pure components. A hand-written `useMemo`/`useCallback`/`memo` signals a DELIBERATE, measured decision; one appearing without a stated reason is the finding.
