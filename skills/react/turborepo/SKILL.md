---
name: turborepo
description: Use when writing or reviewing a pnpm + Turborepo workspace - turbo.json task pipelines, dependsOn and ^build, outputs and cache correctness, remote cache kept off, pnpm --filter and turbo --filter, packageManager pinning, --frozen-lockfile, and the four root scripts (test, lint, typecheck, e2e) that graph-engineering's hooks call.
---

# Turborepo (with pnpm workspaces)

Written for **turbo 2.11.3** (npm, 2026-09-22) and **pnpm 12.6.0**. Rules marked *measured* were
run on those two versions on 2026-09-24 in a two-package scratch workspace (rung 1); the rest cite
the docs. `turborepo.dev/docs` is the current line, which on the fetch date was 2.11.3 (released
two days earlier). The per-version hosts (`v2-11-3.turborepo.dev`) sit behind Vercel SSO -
*measured*: an anonymous request gets `302` to `vercel.com/sso-api` - so they are not citable, and
a `$schema` pointing there cannot be fetched by an editor.

Sources (fetched 2026-09-24, turbo 2.11.3 current):
- https://turborepo.dev/docs/crafting-your-repository/configuring-tasks
- https://turborepo.dev/docs/reference/configuration
- https://turborepo.dev/docs/reference/run
- https://turborepo.dev/docs/core-concepts/remote-caching
- https://pnpm.io/cli/install and https://pnpm.io/filtering (pnpm docs, current = 12.x)
- Vercel's own agent skill, `vercel/turborepo` `skills/turborepo/` @ `53629a02b776` (the 2.11.3
  release commit, MIT) - the general manual; this file is the house subset. Read it for watch
  mode, boundaries, env modes and CI recipes this file does not cover.

## When to apply

- Any edit to `turbo.json` (root or a package-level one with `"extends": ["//"]`),
  `pnpm-workspace.yaml`, or a `package.json` in the workspace (scripts, `packageManager`,
  `workspace:*` dependencies).
- Adding a package or app, adding a task, or wiring CI (`pnpm install --frozen-lockfile`,
  `turbo run ...`).

## Rules

### The four house scripts are root `turbo run` targets

- The root `package.json` declares exactly the contract graph-engineering's hooks key on:
  `test`, `lint`, `typecheck`, `e2e`, each `turbo run <task>` (plus `build`). The Stop hook runs
  `pnpm run test` at the root; the PostToolUse hook runs `pnpm run lint <file>` and
  `pnpm run typecheck` from the **nearest** `package.json` that declares them
  (`hooks/scripts/lint-touched-file.sh`).
- **Every workspace package declares its own `lint` and `typecheck`** (and `test` where it has
  tests). *Measured:* when a package declares neither, the hook walks up to the root and runs
  `pnpm run lint /abs/path/file.tsx`, which becomes `turbo run lint /abs/path/file.tsx` and fails
  with ``Could not find task `/abs/path/file.tsx` in project``. The hook informs, never blocks,
  so this failure is silent unless you read it.
- Task logic lives in the package scripts; the root only delegates. Never `turbo build` (the
  shorthand) in a script or CI file - always `turbo run build` (Vercel skill, "Secondary Rule").
  Never chain `turbo run a && turbo run b`; list both tasks in one `turbo run a b`.

### Pipelines: `dependsOn`, `outputs`, `cache`

- `"dependsOn": ["^build"]` means "the `build` of every workspace package **this one depends
  on** first"; `"dependsOn": ["build"]` (no caret) means this package's own `build` first;
  `"web#build"` pins one package's task.
  https://turborepo.dev/docs/crafting-your-repository/configuring-tasks
- A task that reads a dependency's **built output** (`typecheck` against a package's emitted
  `.d.ts`, `test` importing `dist/`) gets `^build`. A task that reads only source (`lint`) does
  not - it would serialise for nothing.
- Every task that writes files declares them in `outputs` (Vite / tsc: `["dist/**"]`); a task
  that writes nothing declares `"outputs": []` explicitly so a reviewer can tell "nothing" from
  "forgot". Missing `outputs` means a cache hit restores logs but no files.
  https://turborepo.dev/docs/reference/configuration
- `tsc --noEmit` with `incremental: true` still writes `.tsbuildinfo`; declare it or turn
  `incremental` off for `typecheck` (Vercel skill, "Missing outputs").
- Tasks that must never be replayed - `dev`, `e2e` against a live server - set `"cache": false`;
  long-running ones add `"persistent": true`.
- Env vars a task's output depends on go in that task's `env` (or `globalEnv`); otherwise a
  changed `VITE_*` value replays a stale build. Default `envMode` is `strict`.
  https://turborepo.dev/docs/reference/configuration
- Paths in `inputs`/`outputs` are package-relative; never `../` out of the package.

The house `turbo.json`:

```json
{
  "$schema": "https://turborepo.dev/schema.json",
  "remoteCache": { "enabled": false },
  "tasks": {
    "build":     { "dependsOn": ["^build"], "outputs": ["dist/**"] },
    "lint":      { "outputs": [] },
    "typecheck": { "dependsOn": ["^build"], "outputs": [] },
    "test":      { "dependsOn": ["^build"], "outputs": [] },
    "e2e":       { "dependsOn": ["build"], "cache": false }
  }
}
```

### Remote cache: off, and said so

- `"remoteCache": { "enabled": false }` in the root `turbo.json`. No `TURBO_TOKEN`, no
  `TURBO_TEAM`, no `turbo login` / `turbo link` in docs, CI or scripts. *Measured:* with the
  setting present, a run with `TURBO_TOKEN=fake TURBO_TEAM=x` exported prints
  `Remote caching disabled (in configuration)` and makes no remote call.
- Why explicit when there is no token: `remoteCache.enabled` defaults to `true` ("still requires
  the user to login"), and `false` "will disable all remote cache operations, even if the repo has
  a valid token" (configuration reference). Without it, one developer's `turbo login` + `turbo link`
  starts uploading build artefacts to Vercel - a third-party data flow nobody reviewed.
  https://turborepo.dev/docs/reference/configuration and
  https://turborepo.dev/docs/core-concepts/remote-caching
- Local cache lives in `.turbo/` (root and per package); `.gitignore` carries `.turbo/`, `dist/`
  and `node_modules/` so neither the cache nor build output is ever committed.

### pnpm: pinned, frozen, filtered

- Root `package.json` has `"packageManager": "pnpm@12.6.0"` (exact, no range) and `turbo`
  pinned exact in `devDependencies`. *Measured:* without it `turbo run` exits 1 with "Could not
  resolve workspace. Missing `devEngines.packageManager` or legacy `packageManager` field" - turbo
  2.11.3 calls the field legacy but still accepts it, and pnpm and corepack read it; keep it.
- `pnpm-workspace.yaml` lists `apps/*` and `packages/*`; internal deps use `"workspace:*"`.
- CI and every README first-run line use `pnpm install --frozen-lockfile`. *Measured* on pnpm
  12.6.0: exit 1 with "Headless installation requires a pnpm-lock.yaml file" when the lockfile is
  missing, and exit 1 `ERR_PNPM_OUTDATED_LOCKFILE` after a dependency was added to a
  `package.json` without re-locking - which is the point.
  Commit `pnpm-lock.yaml`. https://pnpm.io/cli/install
- Running one package: `pnpm --filter web run test` (pnpm runs the script directly, no turbo, no
  cache) or `pnpm exec turbo run test --filter=web` (turbo, cached, with its `dependsOn`; *measured*: scope
  `web`, 2 tasks - its own `test` plus the upstream `build`). Pick turbo
  when the task has upstream `^build` needs. https://pnpm.io/filtering
- Turbo filter syntax: `--filter=web...` = web **and its dependencies**;
  `--filter=...@scope/config` = the package **and its dependents** (both *measured* with
  `--dry=json`); `--filter=[origin/main]` = changed since a ref (docs, not run).
  https://turborepo.dev/docs/reference/run
- A Docker build stage installs only the app's graph: `pnpm install --frozen-lockfile --filter
  hello-web...` (pnpm filter selectors apply to `install`; https://pnpm.io/filtering, not run here).

### Structure

- Shared code is a package under `packages/`, never a relative import across `apps/`.
- Each package's `package.json` names what it exports (`exports`); an app imports
  `@scope/ui`, not `../../packages/ui/src`.
- Root `devDependencies` hold only repo tools (`turbo`, the formatter); a package's runtime
  deps live in that package.

## Anti-patterns

- A package with no `lint`/`typecheck` script (the hook falls through to `turbo run lint <file>`).
- `turbo build` or `npx turbo ...` written into a script or workflow.
- `"dependsOn": ["^build"]` on `lint` - serialises the graph for a task that reads source.
- A file-producing task with no `outputs`; a non-cacheable task (`e2e`, `dev`) without
  `"cache": false`.
- `remoteCache` absent, or `TURBO_TOKEN` anywhere in the repo or CI secrets.
- `pnpm install` without `--frozen-lockfile` in CI; `packageManager` missing or a range.
- `--parallel` to "speed up" - it ignores the dependency graph (Vercel skill, "Using `--parallel`").

## Review focus

- Does every new package declare `lint`, `typecheck` and `test`? Does every new file-writing
  task declare `outputs`?
- Does a new env var that reaches the bundle appear in the task's `env`?
- Is the remote cache still off, and the lockfile committed with the change?

## Verify

```bash
# 0. Versions the rules above were written for.
pnpm --version                        # expect 12.6.0 (from packageManager)
pnpm exec turbo --version             # expect 2.11.3

# 1. The lockfile is authoritative.
pnpm install --frozen-lockfile        # expect exit 0 and no lockfile diff: git diff --exit-code pnpm-lock.yaml

# 2. The pipeline graph is what you meant (no execution).
pnpm exec turbo run build --dry=json | python3 -c 'import sys,json; d=json.load(sys.stdin); print([(t["taskId"], t["dependencies"]) for t in d["tasks"]])'

# 3. Remote cache is off.
pnpm test 2>&1 | grep -i "remote caching disabled"   # expect one line

# 4. The cache is correct: a second run with no change is a full hit.
pnpm test >/dev/null && pnpm test 2>&1 | grep -E "Cached:|FULL TURBO"   # expect "N cached, N total"

# 5. Every package carries the hook contract.
node -e 'let bad=0; for (const f of process.argv.slice(1)) { const s=require(require("path").resolve(f)).scripts||{};
  const miss=["lint","typecheck"].filter(k=>!s[k]); if (miss.length) { console.log(f, "missing", miss.join(",")); bad=1 } }
  process.exit(bad)' apps/*/package.json packages/*/package.json   # expect no output, exit 0
```
