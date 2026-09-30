---
description: Scan this repo and write a graph-engineering profile - the stack map, dependency-derived skill routing, risk table, rule paths, gates and local-agent overrides that every playbook run reads. `--upgrade` brings an existing profile to the current schema.
argument-hint: "[--force | --upgrade]"
disable-model-invocation: true
---

# /graph-init - write or upgrade this repo's graph profile

Produces `.claude/graph-profile.yaml` from the plugin's `templates/graph-profile.yaml` (`schema_version: 2`), plus three optional proposals: `.claude/graph-checks.json`, `.claude/settings.json` additions and a `.gitignore` line. Everything repo-specific comes from what this repo contains; nothing is written before the owner approves it.

## Steps

1. **Refuse to clobber.** If `.claude/graph-profile.yaml` exists and neither `--force` nor `--upgrade` was passed, print its stack list and its `schema_version` (absent means 1), suggest `--upgrade`, and stop. Silently overwriting a hand-edited profile is the one unrecoverable thing this command could do.

2. **Upgrade (`--upgrade`).** Bring the existing profile to the template's schema without regenerating it; the owner's values win.
   - Read `.claude/graph-profile.yaml` and `<plugin-root>/templates/graph-profile.yaml`.
   - Add every block the template has and the profile is missing, in the template's position, with the template's comment and default; nested keys too (a `gates` without `owner_classes` gains it). For a missing block a detection step fills (`runtime`, `deploy`, `infra`, `api`, `bootstrap`, `lanes`: step 4), run that step for that block only; what it cannot find keeps the empty default and is listed as a gap.
   - Run step 3 and add the derived routing rows the profile lacks. Never delete a row: an existing row that routes a framework skill no manifest declares is listed in the summary for the owner to drop.
   - Never change a value the profile already sets, even where it differs from the template.
   - Remove the stale keys `content` and `gates.publication` (dropped in 0.12). Print each removed key with its old value, so nothing leaves silently.
   - Set `schema_version: 2` as the first key.
   - Edit the file as text. A YAML load-and-dump drops every comment the owner wrote.
   - Write the result to a temp file and show `diff -u .claude/graph-profile.yaml <temp>` as a unified diff. Then run steps 9 to 13 and stop at step 14. Write only on approval; after writing, parse the file with the plugin's duplicate-key-rejecting loader (`graph_control.preflight.UniqueLoader` under `<plugin-root>/scripts`) and report the result.

3. **Derive routing from dependencies.** Framework skills route by what a manifest declares, never by a file extension: a `.ts` file in an Express service is not React.
   - Find every manifest outside vendored and generated trees (`node_modules/`, `.venv/`, `vendor/`, `build/`, `dist/`): `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Package.swift` or a `*.xcodeproj`, `build.gradle` / `build.gradle.kts`, `pom.xml`, `Gemfile`, `supabase/config.toml`.
   - Anchor each at its directory relative to the repo root and read the dependencies it declares.
   - Apply the dependency table: the commented `derived:` block under `routing:` in `templates/graph-profile.yaml`. It is the single source, rules included (merging rows with the same glob, the nearest manifest owns a file, a workspace root writes no stack row); follow it from there rather than from memory.
   - Add one `stacks` entry per manifest directory, with the glob that contains its code (`services/api/**`, `web/**`; at the root, the code directories, never `**`).
   - A language with no plugin stack skill (the table's `gap` row, or any manifest no row covers) gets rule packs only, `backend-rules` plus the `always` rows, and one gap line in the approval summary naming the language and its manifest. Never borrow another stack's skill.

4. **Detect the stacks no manifest declares.** GitOps, infra, QA and observability each route competencies nothing else does:

   | Look for | Stack it means |
   |---|---|
   | `argocd/` holding `kind: Application` or `ApplicationSet` | Argo CD; Argo renders Helm and kustomize, so both ride along |
   | `manifests/`, or whatever directory holds the plain Kubernetes YAML | kubectl, kustomize |
   | `**/Chart.yaml` (its `templates/` siblings come with it) | Helm |
   | `**/kustomization.yaml` / `.yml` | kustomize |
   | YAML with `apiVersion: postgresql.cnpg.io`, and the directory holding it | CloudNativePG. A glob cannot see file content, so record the DIRECTORY (for example `manifests/<app>-pg*`) |
   | YAML with `apiVersion: gateway.networking.k8s.io` or `gateway.envoyproxy.io`, and its directory | Envoy Gateway |
   | an `ai-gateway/`, `agent-router/` or `llm-gateway/` directory | agent-router (the Envoy AI Gateway successor) |
   | `.sops.yaml`, `**/*.enc.yaml` / `.enc.yml` | sops + age |
   | `playwright.config.ts`, `tests/**/*.spec.ts` | Playwright |
   | `**/*.bru`, `bruno.json` | Bruno |
   | `observability/`, `**/dashboards/**/*.json`, `**/*rule*.yaml` | PromQL, LogQL, TraceQL |

   Read the file, do not guess from the name: a directory called `gateway/` in a repo with no Gateway API CRDs is not the Envoy Gateway stack.

   **API surfaces.** Find where this repo's contract lives - FastAPI `APIRouter(` / `@app.get(`, NestJS `@Controller(`, Express `Router()`, Go `http.HandleFunc` / router registrations, Spring `@RestController`, Rails `config/routes.rb`, and any `openapi*` / `asyncapi*` / `swagger*` spec - with a content grep, not a name guess. Keep the template's API-surface rows that match, re-anchor them to the directories you actually found, and drop the rest; the `api-surface` risk row follows the same edits. Where a server's routes are TypeScript/JavaScript under `routes/` or `handlers/` (Express, Hono, Fastify), add a row anchored to that server's directory - the template leaves those out because the same names are frontend routing (TanStack, Remix, SvelteKit) or MSW mocks elsewhere. Never route `api-contract` onto a frontend directory. Find an existing Bruno collection (`bruno.json`) and set `api.collection` to its directory; if none exists, keep the default `bruno` and say the first API task will create it.

   **Infra.** When the GitOps rows survive, propose `infra.render` from the Argo CD Applications (one `helm template` / `kustomize build` per Application, with its own `valueFiles`), and `infra.policy` when a `policy/` directory of Rego exists. Propose `infra.cluster` with `kind` or `k3d` only if one is installed and there are at least ~2 GB free; name the cluster `ge-${GRAPH_RUN_ID}`. Never point `infra.cluster.context` at a cluster that already exists - list existing contexts in the summary so the owner sees what qa will never touch.

   **Deploy.** Propose the `deploy` block `post-deploy-verification` reads: `wait` from an Argo CD Application that tracks the default branch (`argocd app wait <app> --sync --health --timeout 600`) or a version endpoint, `startedAt` from the same Application, `bruEnv` from a non-local Bruno environment, and `checks` from existing recording or alert rules. None found: list `deploy` as a gap in the approval summary, saying every run's post-deploy node will report `SKIPPED` until it is filled.

   **Runtime.** A repo with nothing to stand up - a library, a CLI, a Claude Code plugin - gets `runtime.none: "<why>"` and no other runtime field; qa then verifies through its public surface instead of blocking. Otherwise propose the `runtime` block qa will use to stand the repo up, from what is there: a `compose.yaml` / `docker-compose.yml` (propose `docker compose -p ge-${GRAPH_RUN_ID:?} up -d --wait --wait-timeout <s>` and `docker compose -p ge-${GRAPH_RUN_ID:?} down -v` - never without `-p`, or qa reuses and then deletes the developer's own volumes. Then run `qa-verification`'s `compose_isolation.sh ge-probe <-f files>`: every line it prints is shared with the developer's stack, because `-p` does not rename it. Propose a committed `compose.qa.yaml` override - block-style YAML, since `${GRAPH_RUN_ID}` inside a `{ }` flow map does not parse - that renames each to `ge-${GRAPH_RUN_ID}_<name>`, drops the externals (`!override` on the service's list, `!reset null` on the top-level entry) and replaces host networking and outside bind mounts, and add `-f compose.yaml -f compose.qa.yaml` to both commands - and check every service it starts has a `healthcheck:` - `--wait` waits on healthchecks, so a service without one is reported ready the moment it starts), a `Taskfile.yml` `dev`/`up` task, a `package.json` `dev`/`start` script, a `pyproject.toml` script or `uv run uvicorn ...`, a kind/Tilt/Skaffold config. A repo-owned harness (login, throwaway users, cleanup) goes behind `runtime.command`; the plugin ships none. Take `health.url` and `health.expect` from the health route the code actually registers (its response body), `baseUrl` and `port` from the port it binds, and `api.schema` from where the app serves its OpenAPI/GraphQL schema - none served is a gap, because `api-contract` requires one. Look for a seed script or fixture loader for `seed`. Find how a local client gets a token (a seeded fixture user, a dev-only signer, a login the seed prints) and record the variable NAMES in `runtime.env` with a comment naming the source - never a value. Every field starts empty in the template; fill only what you detected. Anything you cannot find stays empty and is listed in the approval summary as a gap - qa returns `BLOCKED` on it rather than guessing.

   **Bootstrap.** Propose `bootstrap`, the commands each new task worktree runs before an agent works in it, from the lockfiles the repo commits (outside the vendored and generated trees of step 3). One command per lockfile; a lockfile below the root runs as `cd <dir> && <command>`, and a workspace installs once, at the lockfile. Install commands come before generators, which can need the installed tools.

   | Found | Command |
   |---|---|
   | `pnpm-lock.yaml` | `pnpm install --frozen-lockfile --offline` |
   | `package-lock.json` | `npm ci --offline` |
   | `yarn.lock` with a `__metadata:` key (Yarn 2 and later) | `yarn install --immutable` |
   | `yarn.lock` headed `# yarn lockfile v1` (Yarn classic) | `yarn install --frozen-lockfile` |
   | `bun.lock` or `bun.lockb` | `bun install --frozen-lockfile` |
   | `uv.lock` | `uv sync --frozen` |
   | `Gemfile.lock` | `bundle install` |
   | `go.sum` | `go mod download` |
   | `project.yml` holding an XcodeGen spec (top-level `targets:`) | `xcodegen generate` |

   The flags make a worktree install exactly what the lockfile pins and never touch the registry: with a cold store an offline install fails at once instead of fetching (spiked 2026-10-01: `pnpm install --frozen-lockfile --offline` on pnpm 10.33.3 and `npm ci --offline` on npm 11.12.1 each exit 1 in about 0.2 s on an empty store, 0 on a warm one). Read the yarn.lock header before picking its row: Yarn classic ignores `--immutable` and rewrites the lockfile (spiked on 1.22.22: exit 0, lockfile changed), while `--frozen-lockfile` there and `--immutable` on Yarn 4.9.2 both exit 1 on a drifted lockfile. Any other lockfile or generation step (`Cargo.lock`, `poetry.lock`, `Package.resolved`, a codegen script) gets no guessed command: list it as a gap in the approval summary for the owner to fill. Shown with the profile and written only on approval.

   **Lanes.** Propose `lanes`, the host resources that runs must take one at a time; the engine wraps each command that uses one with `scripts/lane-run.sh <lane> --slots <n> -- <command>`. Propose a lane only on this evidence, each with 1 slot:
   - `xcodebuild` when a `*.xcodeproj` or an XcodeGen `project.yml` exists: parallel Xcode builds contend for CPU, simulators and DerivedData.
   - `cluster` when `infra.cluster.create` is set (above): each throwaway cluster costs memory and about 1 GB of node image.
   - `local_db` when the command that stands the stack up (`runtime.up`, or `runtime.command` when a harness owns setup) does not contain `${GRAPH_RUN_ID`: the stack is not isolated per run, so two runs would share one database. Never when `runtime.none` is set.

   No evidence, no lane: an empty `lanes` serializes nothing. Say in the approval summary why each proposed lane is there. Shown with the profile and written only on approval.

5. **Detect existing agents.** List `.claude/agents/*.md`. Where a local agent plainly covers a plugin role for a stack, propose it as a `localAgents` override (it runs instead of the plugin agent); where it adds a view beside the plugin agent (a visual reviewer beside the code reviewer), propose it under `localLanes`. This is the additive contract: the engine defers to what the repo already has and supplies only the legs it lacks.

6. **Detect rule packs.** Glob `.claude/rules/*.md` and any nested `CLAUDE.md`. Record them under `rules`.

7. **Detect the docs convention.** If the repo has no `docs/` but has another specs directory, set `docsPath` to it rather than assuming.

8. **Build the routing table and the risk table,** keeping only rows whose files actually occur in this repo. A row for a stack the repo does not contain is a lie about what is here, and it will route an agent to a competency that cannot help it. Keep `**/{chart,charts}/**/templates/**/*.{yaml,yml,tpl}` only when a `Chart.yaml` was found, and re-anchor it if this repo keeps its charts somewhere other than `chart/` or `charts/`: the anchor is what stops it matching every other meaning of `templates/`. Keep every `risk` id (the gates name them) but narrow its `paths` to this repo's directories, and ask the owner which pages and templates are `public-copy`. Check a row you are unsure about with `wcmatch.glob.globmatch(path, key, flags=GLOBSTAR | BRACE | DOTGLOB)` and not with `git ls-files`, whose pathspec globs have no brace expansion.

9. **Propose `.claude/graph-checks.json`.** The Stop and lint hooks do nothing without it (version 1, shape in `<plugin-root>/templates/graph-checks.json`, every block optional). This is the detection that used to run inside the hooks on every stop and edit; it now runs once, here, where the owner sees it. Look at the repo root, since the hooks run each argv from there. The file holds one `test` and one `lint`: when several rows match, show them all and recommend the one that covers every package (a root task runner usually does). `<pm>` comes from the lockfile: `pnpm-lock.yaml` pnpm, `yarn.lock` yarn, `bun.lock` or `bun.lockb` bun, otherwise npm.

   | Found | Block | argv | extensions |
   |---|---|---|---|
   | `pyproject.toml` with `test` under `[project.scripts]` | test | `["uv", "run", "test"]` | |
   | pytest configured (`[tool.pytest.ini_options]` in `pyproject.toml`, `pytest.ini`, `[tool:pytest]` in `setup.cfg`, or `pytest` in a dependency group), no `poetry.lock` | test | `["uv", "run", "pytest"]` | |
   | pytest configured, `poetry.lock` | test | `["poetry", "run", "pytest"]` | |
   | `package.json` with `scripts.test` | test | `["<pm>", "run", "test"]` | |
   | `Taskfile.yml` with a `test` task | test | `["task", "test"]` | |
   | `Makefile` with a `test` or `check` target | test | `["make", "<target>"]` | |
   | `go.mod` | test | `["go", "test", "./..."]` | |
   | `Cargo.toml` | test | `["cargo", "test"]` | |
   | `Package.swift` | test | `["swift", "test"]` | |
   | `gradlew` wrapper | test | `["./gradlew", "test"]` | |
   | `mvnw` wrapper | test | `["./mvnw", "test"]` | |
   | `pom.xml`, no `mvnw` | test | `["mvn", "test"]` | |
   | eslint configured, pm pnpm | lint | `["pnpm", "exec", "eslint", "{file}"]` | `[".ts", ".tsx", ".js", ".jsx"]` |
   | eslint configured, pm npm | lint | `["npm", "exec", "--no", "--", "eslint", "{file}"]` | `[".ts", ".tsx", ".js", ".jsx"]` |
   | eslint configured, pm yarn | lint | `["yarn", "run", "eslint", "{file}"]` | `[".ts", ".tsx", ".js", ".jsx"]` |
   | eslint configured, pm bun | lint | `["bun", "run", "eslint", "{file}"]` | `[".ts", ".tsx", ".js", ".jsx"]` |
   | ruff configured (`[tool.ruff]`, `ruff.toml`) | lint | `["uv", "run", "ruff", "check", "{file}"]` | `[".py"]` |
   | swiftlint configured (`.swiftlint.yml`) | lint | `["swiftlint", "lint", "{file}"]` | `[".swift"]` |
   | `runtime` uses docker or compose | precheck | `["docker", "info"]` | |

   A linter is configured when its config file exists and, for eslint and ruff, the manifest declares it. Go gets no `lint` row: `go vet` and golangci-lint check a package, not a file, so a per-file run reports the package's other files as missing; `go test ./...` already runs a subset of `go vet`. `lint.argv` holds exactly one `{file}` element and `lint.extensions` is required. npm assumes `--yes` when stdin is not a terminal, and the hooks close stdin, so a bare `npm exec eslint` would fetch and run eslint from the registry wherever it is not installed; `--no` makes it fail instead. `pnpm exec` and `bun run` only run local binaries (spiked 2026-09-30 on npm 11.12.1, pnpm 10.33.3, bun 1.3.6: each ran a local eslint with the file and none fetched a missing one). Leave `timeout_seconds` at the defaults unless the suite is known to run longer.

10. **Propose `.claude/settings.json` additions.** Merge into the existing file, keeping every key and rule already there, and show the diff:

    ```json
    {
      "env": {
        "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "2",
        "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "8"
      },
      "permissions": {
        "deny": [
          "Bash(docker system prune -a*)",
          "Bash(git filter-branch*)",
          "Bash(git filter-repo*)",
          "Bash(git push --force origin <default>*)",
          "Bash(git push -f origin <default>*)",
          "Bash(supabase db reset*)",
          "WebFetch(domain:x.com)", "WebFetch(domain:*.x.com)",
          "WebFetch(domain:twitter.com)", "WebFetch(domain:*.twitter.com)",
          "WebFetch(domain:linkedin.com)", "WebFetch(domain:*.linkedin.com)",
          "WebFetch(domain:instagram.com)", "WebFetch(domain:*.instagram.com)",
          "WebFetch(domain:facebook.com)", "WebFetch(domain:*.facebook.com)"
        ]
      }
    }
    ```

    Depth 2 lets the engine's leads spawn leaves and stops leaves from spawning further; 8 caps concurrent subagents below the host default of 20. `<default>` is the default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`, without `origin/`). Propose `Bash(supabase db reset*)` only when a `supabase/` directory exists. A prefix rule matches only the spelling it names; the plugin's destructive-command guard asks, with evidence, on force pushes, volume deletes and `rm -rf` on roots however they are spelled. The social domains are login-walled, so a fetch returns a login page; a deny rule costs no hook process, and each domain needs its `*.` twin because `domain:linkedin.com` does not match `www.linkedin.com`.

11. **Propose the `.gitignore` line** `.graph/`, when it is missing: run state, ledgers and evidence drafts live there and never belong in a commit.

12. **Print the notes.** Two, printed and never written:
    - When this repo's auto memory (`~/.claude/projects/<project>/memory/MEMORY.md`, shared by every worktree of the repo) is over 4 KB: only the main session loads it, because subagents never get it (the memory docs; a fork is the one exception), so every main turn pays for it and no worker benefits. Keep it an index of one-line entries and move detail into topic files.
    - The skill-listing controls the owner has are `skillListingMaxDescChars` (caps each listed description), `claude --disable-slash-commands` (a session with no skills or commands), and `skillOverrides` for their own personal and project skills. `skillOverrides` does not affect plugin skills.

13. **Print the Playwright permission recommendation** whenever the QA row survived step 8. Say this, verbatim:

    > The vendored Playwright skills declare `allowed-tools: ... Bash(npx:*) Bash(npm:*)`, and `npx <package>` fetches and runs arbitrary registry code. A skill's `allowed-tools` is granted whenever that skill is active, and workspace trust never gates it ([Configure permissions](https://code.claude.com/docs/en/permissions)). The binding control is a host permission rule in this repo's `.claude/settings.json`, because "a matching ask or deny rule still aborts the invocation regardless of `allowed-tools`" ([Skills](https://code.claude.com/docs/en/skills)):
    >
    > ```json
    > { "permissions": { "ask": ["Bash(npx:*)", "Bash(npm:*)"] } }
    > ```
    >
    > That restores the prompt on the two commands worth prompting on and leaves the skills fully usable. `ask` rules only restrict, so unlike `allow` rules they apply without the workspace trust dialog. Do not edit the vendored skill: that breaks its refresh contract and its Apache-2.0 provenance.

14. **Show the proposals and stop for approval.** The profile (or, with `--upgrade`, its diff), each proposal from steps 9 to 11, and the gaps. The owner approves each file separately; write only what was approved. Then tell them to run `/graph-ship`.
