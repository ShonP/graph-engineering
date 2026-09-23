---
description: Scan this repo and write a graph-engineering profile - the stack map, skill routing table, rule paths, gates and local-agent overrides that every playbook run reads.
argument-hint: "[--force]"
disable-model-invocation: true
---

# /graph-init - write this repo's graph profile

Produces `.claude/graph-profile.yaml` from `templates/graph-profile.yaml`.

## Steps

1. **Refuse to clobber.** If `.claude/graph-profile.yaml` exists and `--force` was not passed, print its current stack list and stop. Silently overwriting a hand-edited profile is the one unrecoverable thing this command could do.

2. **Detect stacks.** Look for `package.json` (read `dependencies` for react, next, nest), `pyproject.toml` / `uv.lock` / `.python-version`, `go.mod`, `*.xcodeproj` / `Package.swift`, `build.gradle.kts`, and `supabase/` or `migrations/`. Map each hit to the glob that actually contains it. In a monorepo that is `apps/*/web/**`, not `**`.

   Also detect the GitOps, Temporal, QA and observability stacks, because each one routes competencies nothing else does:

   | Look for | Stack it means |
   |---|---|
   | `argocd/` holding `kind: Application` or `ApplicationSet` | Argo CD; Argo renders Helm and kustomize, so both ride along |
   | `manifests/`, or whatever directory holds the plain Kubernetes YAML | kubectl, kustomize |
   | `**/Chart.yaml` (its `templates/` siblings come with it) | Helm |
   | `**/kustomization.yaml` / `.yml` | kustomize |
   | YAML with `apiVersion: postgresql.cnpg.io`, and the directory holding it | CloudNativePG. A glob cannot see file content, so record the DIRECTORY (forge: `manifests/forge-pg*`) |
   | YAML with `apiVersion: gateway.networking.k8s.io` or `gateway.envoyproxy.io`, and its directory | Envoy Gateway |
   | an `ai-gateway/`, `agent-router/` or `llm-gateway/` directory | agent-router (the Envoy AI Gateway successor) |
   | `.sops.yaml`, `**/*.enc.yaml` / `.enc.yml` | sops + age |
   | `**/{workflows,activities}/**/*.py`, or `temporalio` in `pyproject.toml` | Temporal |
   | `**/agents/**/*.py`, or `agent-framework` / `pydantic-ai` in `pyproject.toml` | agents |
   | `playwright.config.ts`, `tests/**/*.spec.ts` | Playwright |
   | `**/*.bru`, `bruno.json` | Bruno |
   | `observability/`, `**/dashboards/**/*.json`, `**/*rule*.yaml` | PromQL, LogQL, TraceQL |

   Read the file, do not guess from the name: a directory called `gateway/` in a repo with no Gateway API CRDs is not the Envoy Gateway stack.

   **API surfaces.** Find where this repo's contract lives - FastAPI `APIRouter(` / `@app.get(`, NestJS `@Controller(`, Express `Router()`, Go `http.HandleFunc` / router registrations, Spring `@RestController`, ASP.NET `[ApiController]`, Laravel `Route::` in `routes/api.php`, Rails `config/routes.rb`, and any `openapi*` / `asyncapi*` / `swagger*` spec - with a content grep, not a name guess. Keep the template's API-surface rows that match, re-anchor them to the directories you actually found, and drop the rest. Where a server's routes are TypeScript/JavaScript under `routes/` or `handlers/` (Express, Hono, Fastify), add a row anchored to that server's directory - the template leaves those out because the same names are frontend routing (TanStack, Remix, SvelteKit) or MSW mocks elsewhere. Never route `api-contract` onto a frontend directory. Find an existing Bruno collection (`bruno.json`) and set `api.collection` to its directory; if none exists, keep the default `bruno` and say the first API task will create it.

   **Runtime.** A repo with nothing to stand up - a library, a CLI, a Claude Code plugin - gets `runtime.none: "<why>"` and no other runtime field; qa then verifies through its public surface instead of blocking. Otherwise propose the `runtime` block qa will use to stand the repo up, from what is there: a `compose.yaml` / `docker-compose.yml` (propose `docker compose -p ge-${GRAPH_RUN_ID} up -d --wait --wait-timeout <s>` and `docker compose -p ge-${GRAPH_RUN_ID} down -v` - never without `-p`, or qa reuses and then deletes the developer's own volumes. Then run `docker compose -p ge-probe config --format json` through the isolation check in `qa-verification` (with `p=ge-probe`): any volume or network with its own `name:`, any `container_name:` and anything `external: true` is shared with the developer's stack, because `-p` does not rename them. Propose a committed `compose.qa.yaml` override - block-style YAML, since `${GRAPH_RUN_ID}` inside a `{ }` flow map does not parse - that renames each to `ge-${GRAPH_RUN_ID}_<name>` and drops the externals (`!override` on the service's list, `!reset null` on the top-level entry), and add `-f compose.yaml -f compose.qa.yaml` to both commands - and check every service it starts has a `healthcheck:` - `--wait` waits on healthchecks, so a service without one is reported ready the moment it starts), a `Taskfile.yml` `dev`/`up` task, a `package.json` `dev`/`start` script, a `pyproject.toml` script or `uv run uvicorn ...`, a kind/Tilt/Skaffold config. Take `health.url` and `health.expect` from the health route the code actually registers (its response body), `baseUrl` and `port` from the port it binds, and `api.schema` from where the app serves its OpenAPI/GraphQL schema - none served is a gap, because `api-contract` requires one. Look for a seed script or fixture loader for `seed`. Find how a local client gets a token (a seeded fixture user, a dev-only signer, a login the seed prints) and record the variable NAMES in `runtime.env` with a comment naming the source - never a value. Every field starts empty in the template; fill only what you detected. Anything you cannot find stays empty and is listed in the approval summary as a gap - qa returns `BLOCKED` on it rather than guessing.

3. **Detect existing agents.** List `.claude/agents/*.md`. Where a local agent plainly covers a plugin role for a stack, propose it as a `localAgents` override. This is the additive contract: the engine defers to what the repo already has and supplies only the legs it lacks.

4. **Detect rule packs.** Glob `.claude/rules/*.md` and any nested `CLAUDE.md`. Record them under `rules`.

5. **Detect the docs convention.** If the repo has no `docs/` but has another specs directory, set `docsPath` to it rather than assuming.

6. **Build the routing table,** keeping only rows whose files actually occur in this repo. A row for a stack the repo does not contain is a lie about what is here, and it will route an agent to a competency that cannot help it. Keep `**/{chart,charts}/**/templates/**/*.{yaml,yml,tpl}` only when a `Chart.yaml` was found, and re-anchor it if this repo keeps its charts somewhere other than `chart/` or `charts/`: the anchor is what stops it matching every other meaning of `templates/`. Check a row you are unsure about with `wcmatch.glob.globmatch(path, key, flags=GLOBSTAR | BRACE | DOTGLOB)` and not with `git ls-files`, whose pathspec globs have no brace expansion.

7. **Print the Playwright permission recommendation** whenever the QA row survived step 6. Say this, verbatim:

   > The vendored Playwright skills declare `allowed-tools: ... Bash(npx:*) Bash(npm:*)`, and `npx <package>` fetches and runs arbitrary registry code. A skill's `allowed-tools` is granted whenever that skill is active, and workspace trust never gates it ([Configure permissions](https://code.claude.com/docs/en/permissions)). The binding control is a host permission rule in this repo's `.claude/settings.json`, because "a matching ask or deny rule still aborts the invocation regardless of `allowed-tools`" ([Skills](https://code.claude.com/docs/en/skills)):
   >
   > ```json
   > { "permissions": { "ask": ["Bash(npx:*)", "Bash(npm:*)"] } }
   > ```
   >
   > That restores the prompt on the two commands worth prompting on and leaves the skills fully usable. `ask` rules only restrict, so unlike `allow` rules they apply without the workspace trust dialog. Do not edit the vendored skill: that breaks its refresh contract and its Apache-2.0 provenance.

8. **Show the proposed profile and stop for approval.** Write only after the owner approves. Then tell them to run `/graph-ship`.
