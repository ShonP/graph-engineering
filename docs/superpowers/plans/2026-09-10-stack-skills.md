# Stack skills: python, agents, k8s-gitops, temporal, qa, observability, rules

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to run this plan task by task. Dispatch the `graph-engineering` roster: `implementer-simple` for tasks marked `small`, `implementer` for `standard`, `reviewer` after each task. REQUIRED skills are printed under every task heading and are not optional; an implementer that cannot load one returns `NEEDS_SETUP`. Vendored trees are copied, never edited; written skills are written from the cited vendor doc pages, fetched during the task, never from memory.

**Goal:** Give the plugin the competencies forge plan 5 and every future Python, GitOps, Temporal, QA and observability task need, so a `/graph-ship` run on those files resolves every routing row to an existing skill and no leg returns `NEEDS_SETUP`.

**Architecture:** Markdown only, no code, no build step. Six new skill groups under `skills/` plus a `rules` group holding the harvested house packs. Adopted vendor skills are vendored byte-identical at a pinned commit with the license and a `SOURCE.md` alongside; house adaptations live in separate skills so the vendored tree stays diffable. Written skills follow the house shape (`skills/react/react-rules`, `skills/react/tanstack-router`) and cite their vendor doc pages at the top. The routing template, `/graph-init`, the agent fallback tables and the README learn the new rows. A spec amendment records the vendoring rule for bare and untagged upstreams, and a `hooks/hooks.json` gives every consuming repo lint-on-edit, test-before-stop and handoff-on-start. A final dry dispatch proves resolution.

**Spec:** `docs/superpowers/specs/2026-08-31-graph-engineering-plugin-design.md` sections 2.2, 2.3, 3.1, 4.1 to 4.5, 7, 10, 12, 13 and the two amendments. **Sourcing report:** `docs/research/2026-09-10-stack-skills-sourcing.md` (20 rows). **Dependencies spike:** `docs/superpowers/spikes/2026-08-31-plugin-dependencies.md`, superseded on one point below.

**Profile:** none in this repo (`.claude/graph-profile.yaml` absent; owner to run `/graph-init`). This plan matches tasks against the stack map in Global Constraints, which is what `/graph-init` should write for this repo.

---

## Prior art

```
Reuse candidates :
  pydantic/skills (plugins pydantic, ai, pydantic-ai-harness; MIT)     -> adopt, vendored; pydantic also ADAPTED via a house overlay
  fastapi/fastapi in-repo skill (MIT)                                  -> adopt, vendored
  temporalio/skill-temporal-developer v0.6.2 (MIT)                     -> adopt, vendored
  grafana/skills promql, loki, tempo (Apache-2.0)                      -> adopt, vendored
  microsoft/playwright playwright-cli, -trace, -component-testing      -> adopt, vendored (Apache-2.0)
  superpowers:writing-skills                                           -> adopt as the authoring process for every written skill
  owner's global rule packs (backend, architecture-resilience,
    agent-workflow, review-testing)                                    -> harvest into skills/rules per spec 4.3
  uv, Microsoft Agent Framework, Helm, Argo CD, kubectl, kustomize,
    CloudNativePG, Envoy Gateway, agent-router, Bruno, SOPS/age        -> no adequate vendor or community skill exists (report rows 1,5-12,14,15); write from vendor docs
  neonwatty/qa-skills, voidmatcha/e2e-skills, agentmantis/test-skills  -> reject: less current than the vendor's own Playwright skills
  langchain-ai/langchain-skills                                        -> reject: LangGraph-scoped, wrong framework
  pydantic logfire plugin                                              -> not in this ask; note for a later observability pass
Looked at        :
  sourcing report 2026-09-10 (rung 4, our researcher, every row has a URL and a last-commit date)
  code.claude.com/docs/en/plugin-dependencies (rung 2, fetched 2026-09-10): version constraints resolve
    against git tags named `{plugin-name}--v{version}` for github/url/git-subdir sources; a relative-path
    plugin with no matching tag installs the marketplace's CURRENT copy and checks the constraint at
    load (it floats, it does not fail); cross-marketplace dependencies are blocked unless the root
    marketplace lists the target in `allowCrossMarketplaceDependenciesOn`
  code.claude.com/docs/en/plugins-reference (rung 2, 2026-09-10): skill invocation name = frontmatter
    `name`, fallback directory basename; `claude plugin validate <path>` exists and exits 0/1/2
  GitHub API on 2026-09-10 (rung 1): pydantic/skills 0 tags 0 releases (marketplace.json present,
    plugin versions 0.1.0); grafana/skills 0 tags (marketplace.json present); temporalio/
    skill-temporal-developer tags v0.1.0..v0.6.2, no .claude-plugin; envoyproxy/ai-gateway
    full_name now theagentrouter/agent-router, Apache-2.0, latest release v1.1.0 on 2026-08-21
  ~/projects/forge-platform tree and .claude/graph-profile.yaml (rung 1): argocd/**, manifests/**,
    observability/**, .sops.yaml, *.enc.yaml, kustomization.yaml present; no Chart.yaml, *.py,
    *.spec.ts or *.bru yet; mise.toml pins argocd 3.5.2, helm 3.21.4, kubectl 1.35.8, sops 3.13.3,
    age 1.3.2; Envoy Gateway chart v1.9.1; CNPG chart 0.29.0 (appVersion 1.29.1)
  docs/HANDOFF.md in forge (rung 1): plan 5 = Temporal helm on CNPG, codec server, Envoy AI Gateway
    with the Entra backend policy, per-caller LLM cost labels, Temporal UI OIDC SecurityPolicy
  code.claude.com/docs/en/hooks (rung 2, 2026-09-10): `hooks/hooks.json` at the plugin root; `PostToolUse`
    matcher `Edit|Write`; `SessionStart` input `source` is startup | resume | clear | compact | fork;
    `Stop` input carries `stop_hook_active` as the loop guard; exit 2 blocks on events that can block;
    `${CLAUDE_PLUGIN_ROOT}` resolves inside hook commands; `tool_input.file_path` is always absolute
Borrowed         : grafana/skills' `license:` frontmatter field for written skills; tanstack-router's
                   SKILL.md + rules/ split for anything over ~250 lines; forge's plan header convention
Rejected         : plugin.json `dependencies` for the adopted plugins (no `--v` tags exist, so a semver
                   constraint cannot resolve; spec 4.2 rule 4 forbids a bare name); a Python vendoring
                   script (plugin is markdown only, the recipe is documented instead)
Spiked           :
  "pydantic/skills is a marketplace-installable tagged release" -> INVALIDATED (marketplace.json yes,
    git tags 0, `pydantic--v0.1.0` absent)
  "envoyproxy/ai-gateway moved to theagentrouter/agent-router" -> VALIDATED (API redirect, v1.1.0)
  "every doc URL the written skills cite is live" -> VALIDATED 46/46 HTTP 200 on 2026-09-10; edge
    case: cloudnative-pg.io/documentation/current/* is a meta-refresh to docs/devel, so the skill
    cites the versioned docs/1.29 or docs/1.30 path instead
  "fastapi skill is at fastapi/.agents/skills/fastapi" -> PARTIAL: it is at
    fastapi/fastapi/.agents/skills/fastapi (7 files); path corrected below
  "TestDino/playwright-skill exists" -> not re-run; the report's 404 stands, citation dropped
  "Claude Code overrides a Stop hook after eight consecutive blocks" -> VALIDATED: hooks reference,
    "Stop input": "Claude Code overrides the hook and ends the turn after 8 consecutive blocks";
    "Stop decision control" calls it the 8-consecutive-continuation cap (an earlier grep of mine was
    truncated and reported PARTIAL; corrected 2026-09-10 in the pre-gate review)
```

## Decisions: dependency versus vendor, one line each

| Source | Decision | Why |
|---|---|---|
| `pydantic/skills` (pydantic, ai, pydantic-ai-harness) | **vendor**, SHA `9e9390ee24d44b32cf5379c58acaebd7563f5f86` (2026-09-01) | marketplace.json exists but zero git tags; as relative-path sources with no `pydantic--v*` tag a `dependencies` entry would install the current copy and only check `~0.1.0` at load: it checks but does not pin (A1) |
| `fastapi/fastapi` in-repo skill | **vendor**, SHA `50113da16fec53b66b80d75e80a89296de4fa5a5` (2026-09-01) | bare skill inside a monorepo, no plugin manifest |
| `temporalio/skill-temporal-developer` | **vendor**, tag `v0.6.2` = SHA `2d7fda32ffbf71106c65c98478ee1031aca1b65b` (2026-09-04) | tagged but not a plugin (no `.claude-plugin`), tag form is `vX.Y.Z` not `temporal-developer--vX.Y.Z` |
| `grafana/skills` promql, loki, tempo | **vendor**, SHA `51d33e71e191b409bbd25fc7be2684c610d18166` (2026-08-18) | marketplace.json exists, zero git tags |
| `microsoft/playwright` three skills | **vendor**, SHA `af74c938e45f3e759dc2521993f201389eb16cb6` (2026-09-10) | bare skills inside the monorepo |
| owner's four global rule packs | **harvest** (copy into `skills/rules`) | spec 4.3; they are already generic |
| everything else | **write** from vendor docs | no adequate skill exists (report) |

**Assumption A1 (owner can reject):** a `version` field in a marketplace.json without a `{name}--v{version}` git tag does not count as a "tagged release". The documented behaviour for pydantic's case (plugin-dependencies reference, "Tag plugin releases for version resolution"): the three plugins are relative-path sources in their marketplace, and "for a relative-path plugin with no matching tag, Claude Code installs the marketplace's current copy instead and checks the constraint when the plugin loads". So a dependency entry would not fail; it would float with whatever `main` holds and only check `~0.1.0` at load. That is a constraint that checks but does not pin, which defeats spec 4.2 rule 4's purpose (an upstream change cannot land unreviewed). Two further reasons survive: a cross-marketplace dependency needs `allowCrossMarketplaceDependenciesOn: ["pydantic-skills"]` in this plugin's marketplace.json, which it lacks today; and the house override (Task 9) sits beside a vendored tree per spec 4.5. Ruling: vendor by SHA until `pydantic--v*` tags exist, then flip to `{ "name": "pydantic", "version": "~0.1.0", "marketplace": "pydantic-skills" }`.

## Global constraints

- Everything is markdown or YAML, with one exception this plan introduces: `hooks/hooks.json` and the shell scripts it calls under `hooks/scripts/` are plugin hook components (plugins reference, Hooks) and are the only executable content. No Python, no build step. Vendoring is a documented shell recipe, not a script in the repo.
- No em dashes in any authored file. Vendored files are exempt and never edited.
- Every new skill directory name equals its `SKILL.md` frontmatter `name` (Claude Code takes the invocation name from `name`, falling back to the directory; the two must agree so routing rows are unambiguous).
- Routing names in `templates/graph-profile.yaml` are those frontmatter names.
- Precedence on conflict (spec 4.5): house > vault-generated > community. The Pydantic house rule overrides the vendored `pydantic` skill's dataclass advice via a separate skill (Task 9), never by editing the vendored file.
- Written skills cite their vendor doc pages at the top, and the implementer fetches every cited page during the task and records its `<title>` next to the URL. A page that 404s is replaced and the swap named in the commit body. Writing from memory is a review Blocking finding.
- Written skills target the versions forge pins today (Argo CD 3.5.2, Helm 3.21.4, kubectl 1.35.8, sops 3.13.3, age 1.3.2, Envoy Gateway v1.9.1, CNPG 1.29.x, agent-router v1.1.0) and say so in the Sources block. Prefer the versioned doc URL where the site has one; otherwise cite the `stable`/latest page and record the version banner it showed.
- Keep each `SKILL.md` under ~250 lines; split into `rules/` or `references/` (house shape) beyond that.
- Stack map for this repo (no profile exists; this is what `/graph-init` should write):

```yaml
stacks:
  skills:    { paths: ["skills/**"] }
  manifest:  { paths: [".claude-plugin/**"] }
  templates: { paths: ["templates/**"] }
  agents:    { paths: ["agents/**"] }
  commands:  { paths: ["commands/**"] }
  hooks:     { paths: ["hooks/**"] }
  docs:      { paths: ["docs/**", "README.md"] }
routing:
  "skills/**/SKILL.md": { impl: [superpowers:writing-skills, review-testing-rules], review: [review-testing-rules] }
  "**/*.{yaml,yml,json,md}": { impl: [review-testing-rules], review: [review-testing-rules] }
  "hooks/**": { impl: [review-testing-rules, security-review], review: [review-testing-rules, security-review] }
  always: { impl: [prior-art], review: [review-protocol, security-review, privacy-review] }
```

- Every task's REQUIRED list derives from that map: `prior-art` and `review-testing-rules` always; `superpowers:writing-skills` on every task that authors a `SKILL.md`.
- Commit per task, imperative subject, body naming the doc pages fetched (written skills) or the SHA and diff result (vendored trees).

## Vendoring recipe (used verbatim by Tasks 6, 8, 10, 14, 16)

```bash
S=/private/tmp/claude-501/-Users-shonpazarker-projects/882da8d8-5a59-43be-b2ab-b69f22cd4b97/scratchpad
P=/Users/shonpazarker/projects/graph-engineering
# 1. clone at the pinned SHA (sparse for monorepos; drop the sparse lines for a whole-repo vendor)
git clone --filter=blob:none --no-checkout https://github.com/<org>/<repo> $S/vendor-<repo>
cd $S/vendor-<repo>
git sparse-checkout init --cone && git sparse-checkout set <subtree> [<subtree>...]
git checkout <SHA>
# 2. copy the subtree into the skill directory (one rsync per skill); never the clone's .git
rsync -a --delete --exclude .git $S/vendor-<repo>/<subtree>/ $P/skills/<group>/<name>/
#    (alternative with no rsync flags to get wrong: git -C $S/vendor-<repo> archive <SHA> <subtree> | tar -x -C <staging>)
# 3. license, and NOTICE where the upstream root has one, alongside when the subtree has none
cp $S/vendor-<repo>/LICENSE $P/skills/<group>/<name>/LICENSE
test -f $S/vendor-<repo>/NOTICE && cp $S/vendor-<repo>/NOTICE $P/skills/<group>/<name>/NOTICE
# 4. provenance
$EDITOR $P/skills/<group>/<name>/SOURCE.md
# 5. verify: the clone is still at the pin and clean, the copy is byte-identical, and git sees files not a gitlink
git -C $S/vendor-<repo> status --porcelain            # expect empty
git -C $S/vendor-<repo> rev-parse HEAD                 # expect the SOURCE.md SHA
cd $P && git diff --no-index --stat $S/vendor-<repo>/<subtree> skills/<group>/<name>
find skills/<group>/<name> -name .git                  # expect empty
git add skills/<group>/<name> && git ls-files skills/<group>/<name> | wc -l   # expect > 0
git ls-files -s skills/<group>/<name> | grep -c '^160000'                    # expect 0
```

Acceptance for step 5, all six lines pasted in the report: clean status and the pinned SHA; the `--stat` output names only `SOURCE.md`, `LICENSE` and, where the upstream has one, `NOTICE` as new files and zero modified files (`git diff --no-index` exits 1 on those additions, which is expected; any other line fails the task); no `.git` entry under the vendored tree; `git ls-files` counts more than zero files; no `160000` (gitlink) mode. The reviewer reproduced the failure this guards against: a whole-repo rsync without `--exclude .git` commits an embedded-repository pointer and zero files while the old diff acceptance still passed.

`SOURCE.md` shape (every field filled, none left as a placeholder):

```
# SOURCE
- Upstream: https://github.com/<org>/<repo>
- Subtree: <path in upstream>
- Commit: <full SHA> (<tag or "untagged">), committed <ISO date>
- Vendored: <ISO date>, plan 2026-09-10-stack-skills Task <n>
- License: <SPDX id>; LICENSE alongside, copied from <upstream path>; NOTICE alongside where the upstream root has one (Playwright does)
- Refresh: the five recipe commands above with this repo's values filled in
- Local changes: none. House overrides, if any, live in <skill path> (spec 4.5 precedence).
```

## Written skill: required shape (Tasks 1, 2, 3, 4, 5, 7, 9, 11, 12, 13, 15)

```
---
name: <equals directory name>
description: Use when <the moment>. <What it covers in one breath>.
license: MIT
---

# <Title>

Sources (fetched <date>, <tool> <version>):
- <URL> - "<page title as fetched>"
- ...

## When to apply
## Rules            (each rule ends with the doc URL or anchor it comes from)
## Anti-patterns    (each names the failure it causes)
## Verify           (a short recipe using the tool's own CLI, with the expected output)
```

Written skills carry the plugin's MIT license (plugin.json author is the owner); vendored trees carry the upstream license.

## Verification, per task

1. `claude plugin validate /Users/shonpazarker/projects/graph-engineering` exits 0 (validates `plugin.json` and every skill's frontmatter).
2. `python3 -m json.tool .claude-plugin/plugin.json > /dev/null` exits 0.
3. For every new `SKILL.md`: `head -4` shows `name:` equal to the directory basename and a non-empty `description:`.
4. Written skills: every URL in the Sources block was fetched in-task (the implementer's report lists URL and title); `grep -c '^- http' SKILL.md` equals the number of titles recorded.
5. Vendored trees: the recipe's step 5 result, pasted into the report.
6. `grep -rn $'\xe2\x80\x94' <authored files>` returns nothing (no em dashes).
7. Reviewer applies `review-protocol`, `security-review`, `privacy-review` plus `review-testing-rules`; a written skill without a Sources block, or with a rule that cites no page, is Important; a vendored tree with a modified file is Blocking.

## Task table

| # | Task | Group | Size | Lane | Runs in parallel with | After |
|---|---|---|---|---|---|---|
| 0 | Register the seven skill groups in plugin.json | manifest | small | implementer-simple | none | - |
| 1 | Write `argocd` | k8s-gitops | standard | implementer | 2-5, 6-8, 10-17 | 0 |
| 2 | Write `helm` | k8s-gitops | standard | implementer | 1, 3-5, 6-8, 10-17 | 0 |
| 3 | Write `cloudnativepg` | k8s-gitops | standard | implementer | 1-2, 4-5, 6-8, 10-17 | 0 |
| 4 | Write `envoy-gateway` | k8s-gitops | standard | implementer | 1-3, 5, 6-8, 10-17 | 0 |
| 5 | Write `agent-router` | k8s-gitops | standard | implementer | 1-4, 6-8, 10-17 | 0 |
| 6 | Vendor `temporal-developer` v0.6.2 | temporal | small | implementer-simple | 1-5, 7-8, 10-17 | 0 |
| 7 | Write `uv` | python | standard | implementer | 1-6, 8, 10-17 | 0 |
| 8 | Vendor `pydantic`, `building-pydantic-ai-agents`, `pydantic-ai-harness` | python | small | implementer-simple | 1-7, 10-17 | 0 |
| 9 | Write `pydantic-house-rules` (the adaptation) | python | standard | implementer | 10-17 | 8 |
| 10 | Vendor `fastapi` | python | small | implementer-simple | 1-9, 11-17 | 0 |
| 11 | Write `kubectl` and `kustomize` | k8s-gitops | standard | implementer | 1-10, 12-17 | 0 |
| 12 | Write `sops-age` | k8s-gitops | standard | implementer | 1-11, 13-17 | 0 |
| 13 | Write `microsoft-agent-framework` | agents | standard | implementer | 1-12, 14-17 | 0 |
| 14 | Vendor the three Playwright skills | qa | small | implementer-simple | 1-13, 15-17 | 0 |
| 15 | Write `bruno` | qa | standard | implementer | 1-14, 16-17 | 0 |
| 16 | Vendor `promql`, `loki`, `tempo` | observability | small | implementer-simple | 1-15, 17 | 0 |
| 17 | Harvest the four rule packs into `skills/rules` | rules | standard | implementer | 1-16 | 0 |
| 18 | Routing rows, `/graph-init` detection, README, version 0.8.0 | templates, commands, docs, manifest | standard | implementer | 19, 20 | 1-17 |
| 19 | Agent fallback catalogs, all nine agent files | agents | standard | implementer | 18, 20 | 1-17 |
| 20 | Owner step: retire the four global rule packs | docs | small | implementer-simple (owner executes) | 18, 19, 21, 22 | 17 |
| 21 | Spec 4.2 amendment: vendoring bare and untagged upstreams | docs | small | implementer-simple | 1-19, 20, 22 | 0 |
| 22 | `hooks/hooks.json`: lint on edit, test before stop, handoff on start | hooks | standard | implementer | 11-21 | 7, 8, 9, 10 |
| 23 | Dry dispatch against a forge file list | docs | standard | implementer | none | 18, 19, 20, 21, 22 |

Sizes: 8 `small` (0, 6, 8, 10, 14, 16, 20, 21), 15 `standard`, 23 tasks (numbered 0 to 22, plus the dry dispatch as 23 to keep the pre-gate numbering stable; 24 headings, 23 units of work after Task 20 became the owner's manual step). Vendor tasks are `small` although they copy many files, because the work is one scripted copy whose acceptance is a mechanical diff; `implementer-simple` escalates if a tree needs judgment (for example an upstream file that fails `claude plugin validate`). Owner may flip any of them to `standard`.

Ordering honours forge plan 5: Tasks 1 to 5 (Argo CD, Helm, CNPG, Envoy Gateway, agent-router), 6 (Temporal) and 7 to 10 (Python) are dispatched in the first wave; everything else in the same wave if capacity allows, otherwise second. Task 22 (hooks) follows the python group because forge plan 6 is its first consumer; Task 21 (spec amendment) can land any time after Task 0; Task 20 (the owner retires the global packs) sits directly after Task 17 so the name collision is closed before the routing rows that depend on it are reviewed; Task 23 (dry dispatch) is last and is the gate.

---

### Task 0: Register the seven skill groups in plugin.json

**Size:** small. **Stack:** manifest. **REQUIRED:** prior-art, review-testing-rules.
**Files:** `.claude-plugin/plugin.json`; `skills/{python,agents,k8s-gitops,temporal,qa,observability,rules}/.gitkeep`.

- [ ] Append `./skills/python`, `./skills/agents`, `./skills/k8s-gitops`, `./skills/temporal`, `./skills/qa`, `./skills/observability`, `./skills/rules` to the `skills` array, after `./skills/process`. Do not bump `version` here (Task 18 does).
- [ ] Create each directory with a `.gitkeep` so the registered path exists; the first skill task landing in a group deletes that group's `.gitkeep`.
- [ ] Run `claude plugin validate /Users/shonpazarker/projects/graph-engineering`. Expected: exit 0. Contingency, written into the report if it happens: if validate rejects a registered directory that holds no `SKILL.md`, revert the seven entries and instead have each group's first task add its own line (Tasks 1, 6, 7, 13, 14, 16, 17), and say so in the ledger.
- [ ] Commit: `Register the six stack skill groups and the rules group`.

**Acceptance:** verification items 1 and 2; `git status` shows only the manifest and the seven `.gitkeep` files.

### Task 1: Write `argocd`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/k8s-gitops/argocd/SKILL.md`, optionally `skills/k8s-gitops/argocd/rules/*.md`; delete `skills/k8s-gitops/.gitkeep` (this task owns that deletion; Tasks 2 to 5, 11 and 12 do not touch it).

Docs to fetch (all returned 200 on 2026-09-10; titles as fetched):
- https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/ "Cluster Bootstrapping" (app of apps)
- https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/ "Sync Phases and Waves"
- https://argo-cd.readthedocs.io/en/stable/operator-manual/health/ "Resource Health" (custom Lua health checks)
- https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/ "Multiple Sources for an Application"
- https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/ "Introduction" (ApplicationSet)
- https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_diff/ "argocd app diff Command Reference"
- Candidate pages to fetch and cite if live: `user-guide/resource_hooks/` (hooks, PreSync/PostSync), `user-guide/helm/` (the Helm hook to Argo hook mapping forge's HANDOFF cites at release-3.5), `operator-manual/commands/argocd_admin_settings_resource-overrides_health/` (the CLI that runs a health Lua locally).
- Forge runs Argo CD 3.5.2: try each URL under `/en/release-3.5/` first and cite that; fall back to `stable` and record the version banner.

- [ ] `## When to apply`: any `argoproj.io/v1alpha1` Application or ApplicationSet, `argocd-cm` health overrides, sync waves, app-of-apps roots, Argo-rendered Helm (`helm:` block with `valuesObject` or values files).
- [ ] `## Rules` (each with its page): app-of-apps root and child shape; sync waves are integers on the annotation and the next wave waits for health, not for sync alone; child Applications need a custom health Lua because the built-in one is relayed status (cite health page and, as rung-1 evidence, forge ADR 0009: a child with a running PostSync hook must report Progressing); CRD-shipping charts go in an earlier wave than their consumers; `syncPolicy.retry` and `controller.sync.timeout.seconds` bound a held gate; multiple sources for chart plus values; hooks and their deletion policies; `ignoreDifferences` only with a reason comment.
- [ ] `## Anti-patterns`: relaying `status.health.status` verbatim for a child Application; unpinned `targetRevision: main` for third-party charts; hand `kubectl apply` in an Argo-owned namespace; values keys the chart does not render; a health Lua past ~250 lines in one file (forge split theirs into per-domain values files).
- [ ] `## Verify`: `argocd app diff <app> --local <dir>` (expect no diff), `kubectl -n argocd get application <app> -o jsonpath='{.status.sync.status} {.status.health.status} {.status.operationState.phase}'` (expect `Synced Healthy Succeeded`), and the local Lua runner `argocd admin settings resource-overrides health <manifest> --argocd-cm-path <argocd-cm.yaml>` if that page is live.
- [ ] Commit: `Add argocd skill written from the Argo CD 3.5 docs`.

**Acceptance:** verification 1, 3, 4, 6; every rule cites a page; the Verify recipe was run against forge (`~/projects/forge-platform`, `argocd/root.yaml`) or, if no cluster is up, the report says so and shows the command output from `argocd app diff --help` proving the flags exist at 3.5.2.

### Task 2: Write `helm`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/k8s-gitops/helm/SKILL.md`.

Docs to fetch (200 on 2026-09-10; helm.sh pages returned no `<title>`, record the H1 instead):
- https://helm.sh/docs/topics/charts/ (Chart.yaml, `crds/`, dependencies)
- https://helm.sh/docs/chart_best_practices/ (the whole best-practices tree; cite the sub-pages you use)
- https://helm.sh/docs/helm/helm_lint/ and https://helm.sh/docs/helm/helm_template/
- Candidates: `topics/charts_hooks/`, `helm/helm_show_values/`. Forge runs Helm 3.21.4.

- [ ] `## When to apply`: authoring a chart (`Chart.yaml`, `templates/**`, `values.yaml`), consuming a third-party chart (values files, `valuesObject` in an Argo Application), chart hooks, CRDs in `crds/`.
- [ ] `## Rules`: pin `version` and `appVersion`; every values key you set must exist in the chart's rendered `values.yaml` at that version (`helm show values <repo>/<chart> --version <v>`); CRDs live in `crds/` and are not templated (or are, only with an explicit reason: Argo CD renders `templates/crds/` as ordinary resources, which forge relies on); named templates in `_helpers.tpl`; labels per the best-practices page; hooks and weights; `helm lint` clean before commit.
- [ ] `## Anti-patterns`: `latest` or unpinned chart versions; values keys that silently render nothing; secrets in `values.yaml` (route to `sops-age`); templating that hides a `kind` behind a conditional nobody documents.
- [ ] `## Verify`: `helm lint <chart>`; `helm template <release> <chart> -f values.yaml | kubectl apply --dry-run=server -f -`; `helm show values <repo>/<chart> --version <v> | yq '<key>'` for every values key set.
- [ ] Commit: `Add helm skill written from the Helm 3.21 docs`.

**Acceptance:** verification 1, 3, 4, 6; Verify recipe run against one forge Application's chart (for example `argocd/apps/loki.yaml`, chart `loki` 18.12.1) with the output in the report.

### Task 3: Write `cloudnativepg`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/k8s-gitops/cloudnativepg/SKILL.md`.

Docs to fetch. `cloudnative-pg.io/documentation/current/*` is a meta-refresh to `docs/devel`; cite the versioned path. Forge's operator chart 0.29.0 has `appVersion: 1.29.1`, and forge's HANDOFF says "CNPG 1.30". Resolve by `kubectl cnpg version` on the forge cluster or the chart's `appVersion`; cite that version. `https://cloudnative-pg.io/docs/1.30/`, `/docs/1.30/kubectl-plugin`, `/docs/1.30/backup` returned 200 on 2026-09-10; check the `1.29` equivalents in-task.
- `docs/<v>/` (index), `docs/<v>/kubectl-plugin`, `docs/<v>/backup`, `docs/<v>/connection_pooling` (Pooler), `docs/<v>/declarative_database_management` (Database, DatabaseRole).

- [ ] `## When to apply`: any `postgresql.cnpg.io` resource (Cluster, Pooler, Database, DatabaseRole, ScheduledBackup, ObjectStore from the barman-cloud plugin), and Argo health for `Cluster`/`Database`.
- [ ] `## Rules`: Cluster spec essentials (instances, storage, bootstrap, superuser secret handling); backups via the barman-cloud plugin and `ScheduledBackup`; Pooler per consumer; declarative `Database` and `DatabaseRole`, and the ordering fact from forge (rung 1, HANDOFF 2026-09-10): CNPG does not order `Database` after `DatabaseRole`, so `CREATE DATABASE ... OWNER <role>` can run first and consumers crash-loop until both land; Argo health for `Database` gates on `status.applied == true` (forge has this Lua already; do not write a second one); password roles over TLS versus certificate roles and the client-CA namespace limit forge recorded.
- [ ] `## Anti-patterns`: plain-text superuser secrets; one Pooler shared by all consumers; a `Database` with no owning role landed first; assuming the operator's client CA is a ClusterIssuer.
- [ ] `## Verify`: `kubectl cnpg status <cluster> -n <ns>`; `kubectl get cluster <cluster> -n <ns> -o jsonpath='{.status.phase}'` (expect `Cluster in healthy state`); `kubectl get database -n <ns> -o jsonpath='{.items[*].status.applied}'`; `kubectl cnpg report cluster <cluster>` for a diagnostic bundle.
- [ ] Commit: `Add cloudnativepg skill written from the CNPG 1.29 docs`.

**Acceptance:** verification 1, 3, 4, 6; the Sources block names the CNPG version cited and how it was confirmed; Verify run against forge `manifests/forge-pg/cluster.yaml` if a cluster is up, else the report shows `kubectl cnpg --help` output.

### Task 4: Write `envoy-gateway`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/k8s-gitops/envoy-gateway/SKILL.md`, `skills/k8s-gitops/envoy-gateway/rules/*.md` if over ~250 lines.

Docs to fetch (200 on 2026-09-10; forge runs chart `gateway-helm` v1.9.1, so try the `/v1.9/` doc mirror first and cite it if it resolves):
- https://gateway.envoyproxy.io/docs/tasks/security/oidc/ "OIDC Authentication"
- https://gateway.envoyproxy.io/docs/tasks/security/jwt-authentication/ "JWT Authentication"
- https://gateway.envoyproxy.io/docs/tasks/security/jwt-claim-authorization/ "JWT Claim-Based Authorization"
- https://gateway.envoyproxy.io/docs/api/gateway_api/backendtlspolicy/ "BackendTLSPolicy"
- https://gateway.envoyproxy.io/docs/tasks/operations/egctl/ "Use egctl"
- https://gateway.envoyproxy.io/docs/tasks/traffic/http-routing/ "HTTP Routing"
- Candidate: the HTTP timeouts task page (forge spike S1 asks whether `timeouts.request: 0s` disables the timeout at v1.9.1).

- [ ] `## When to apply`: GatewayClass, Gateway, HTTPRoute, SecurityPolicy (OIDC, JWT, claim authz), BackendTLSPolicy, ClientTrafficPolicy, BackendTrafficPolicy, ReferenceGrant, health-check exemption routes.
- [ ] `## Rules`: policy `targetRefs` scope (Gateway versus HTTPRoute) and precedence; OIDC flow fields (provider, clientID, clientSecret ref, redirectURL, cookie settings, `forwardIDToken`); JWT providers and claim-to-header; BackendTLSPolicy needs a CA bundle ConfigMap and hostname; exemption routes for unauthenticated health probes as their own HTTPRoute (forge `manifests/gateway-exemptions/`); one SecurityPolicy per app is the proven shape (forge: six copies).
- [ ] `## Anti-patterns`: attaching an OIDC policy at the Gateway and expecting per-route exemptions; trusting a client-supplied identity header without confirming Envoy overwrites it (forge spike S2 is open; write the rule as "verify, do not assume"); `timeouts.request: 0s` assumed to mean disabled (spike S1 open); HTTP/1.1-only listeners in front of gRPC clients (forge: `argocd` CLI needs `--grpc-web`).
- [ ] `## Verify`: `egctl x translate --from gateway-api --to gateway-api -f <file>` (expect no errors); `kubectl get securitypolicy -n <ns> <name> -o jsonpath='{.status.ancestors[*].conditions[?(@.type=="Accepted")].status}'` (expect `True`); `egctl config envoy-proxy listener -n envoy-gateway-system`; a `curl -sSI https://<host>/` showing the 302 to the IdP for a protected route and 200 for an exemption route.
- [ ] Commit: `Add envoy-gateway skill written from the Envoy Gateway 1.9 docs`.

**Acceptance:** verification 1, 3, 4, 6; Verify run against forge `manifests/gateway-auth/securitypolicy-bugsink.yaml` (translate) with the output in the report.

### Task 5: Write `agent-router` (formerly Envoy AI Gateway)

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/k8s-gitops/agent-router/SKILL.md`.

Verified fact to state in the skill (2026-09-10, GitHub API): `envoyproxy/ai-gateway` now redirects to `theagentrouter/agent-router` (Apache-2.0, "Manages Unified Access to Generative AI Services built on Envoy Gateway"); latest release `v1.1.0` on 2026-08-21. Never cite the old name as current.

Docs to fetch (index https://theagentrouter.ai/docs/ returned 200 on 2026-09-10 and links these; the versioned trees offered are `/docs/1.0/` and `/docs/next/`, so pick the one matching v1.1.0 and say which): `/docs/getting-started/` (install, Envoy Gateway version compatibility), `/docs/compatibility`, `/docs/concepts/architecture/`, `/docs/capabilities/` (routes and backends), `/docs/capabilities/security/upstream-auth` (provider credentials, the Entra/Azure path forge needs), `/docs/api/` (CRD reference), `/docs/cli/`. The index names both `AgentRoute` (7 mentions) and the pre-rename `AIGatewayRoute` under `aigateway.envoyproxy.io` (1 mention): confirm from `/docs/api/` which API group and kinds v1.1.0 serves and whether the old kinds remain as aliases. Fallback if a page moves: `https://github.com/theagentrouter/agent-router` at tag `v1.1.0` (`README.md`, `docs/`, `api/`).

- [ ] `## When to apply`: routing LLM traffic through Envoy Gateway, provider backends (Azure OpenAI / Foundry, OpenAI, Anthropic), backend credentials and Entra-style policies, per-caller cost and token metrics.
- [ ] `## Rules`: install depends on Envoy Gateway (state the compatible EG version from the docs); route by model header; backend security policy per provider with secret refs (never inline keys); token usage metrics and the `gen_ai.*` names forge's `LLMDailySpend` alert waits on; keyless auth path for Azure if the docs support it (forge open item: workload identity from a local k3d cluster).
- [ ] `## Anti-patterns`: API keys in `values.yaml`; one backend policy shared across tenants when per-caller cost labels are required; citing `envoyproxy/ai-gateway` docs after the rename.
- [ ] `## Verify`: `kubectl get <route-kind>,<backend-kind> -A` with the kinds confirmed from `/docs/api/`; a `curl` through the gateway with the model header and the expected upstream response; the metrics endpoint scraped with `curl -s <metrics-url> | grep gen_ai` showing the token counters.
- [ ] Commit: `Add agent-router skill (Envoy AI Gateway successor) from its v1.1.0 docs`.

**Acceptance:** verification 1, 3, 4, 6; the Sources block records the rename fact with the date checked and the tag cited; the report names which doc location was used and whether any CRD kind changed at v1.1.0.

### Task 6: Vendor `temporal-developer` v0.6.2

**Size:** small. **Stack:** skills. **REQUIRED:** prior-art, review-testing-rules.
**Files:** `skills/temporal/temporal-developer/**` (SKILL.md, README.md, LICENSE, references/**), `skills/temporal/temporal-developer/SOURCE.md`; delete `skills/temporal/.gitkeep`.

- [ ] Recipe with `<org>/<repo>` = `temporalio/skill-temporal-developer`, SHA `2d7fda32ffbf71106c65c98478ee1031aca1b65b` (tag `v0.6.2`), whole repo (no sparse checkout), subtree = repo root minus `.git/` and `.github/` (`rsync -a --delete --exclude .git --exclude .github`). This is the whole-repo vendor the reviewer reproduced the gitlink failure on: the `.git` exclusion is not optional. The upstream frontmatter `name` is `temporal-developer` and it carries `version: 0.6.2`; the directory name matches.
- [ ] LICENSE is in-tree (MIT); step 3 not needed. Write `SOURCE.md`; note the `references/python/data-handling.md` page as the Pydantic data-converter reference that Task 9 cites.
- [ ] Step 5: expected additions `SOURCE.md` only; expected deletions `.github/**` only (say so in the report); zero modified files; no `.git` under the tree; `git ls-files` counts the 110 upstream files minus `.github/**` plus `SOURCE.md`; no `160000` mode.
- [ ] Commit: `Vendor temporal-developer skill at v0.6.2`.

**Acceptance:** verification 1, 3, 5; `claude plugin validate` accepts the upstream frontmatter (it has an extra `version` field; if validate rejects it, ESCALATE rather than edit the file).

### Task 7: Write `uv`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/python/uv/SKILL.md`; delete `skills/python/.gitkeep` (this task owns that deletion; Tasks 8, 9 and 10 do not touch it).

Docs (200 on 2026-09-10): https://docs.astral.sh/uv/concepts/projects/ "Projects | uv"; https://docs.astral.sh/uv/concepts/projects/dependencies/ "Managing dependencies | uv"; https://docs.astral.sh/uv/concepts/projects/sync/ "Locking and syncing | uv"; https://docs.astral.sh/uv/reference/cli/ "Commands | uv". Candidate: `concepts/python-versions/`. Record the uv version the docs page banner shows and `uv --version` locally.

- [ ] `## When to apply`: `pyproject.toml`, `uv.lock`, `.python-version`, any Python task in a uv project, CI install steps, Dockerfiles for Python services.
- [ ] `## Rules`: `uv init`/`uv add`/`uv remove` edit `pyproject.toml` and the lock together; dependency groups (`dev`) and `--group`; `uv sync --frozen` in CI and images; `uv run` never a bare `python`; `uv lock --check` as the drift gate; pin the interpreter with `.python-version` and `requires-python`; workspaces for monorepos.
- [ ] `## Anti-patterns`: `pip install` inside a uv project; `uv pip` for project dependencies; committing without the lock; `requirements.txt` as the source of truth.
- [ ] `## Verify`: `uv lock --check` (exit 0), `uv sync --frozen` (exit 0), `uv run python -c 'import sys; print(sys.version)'` matching `.python-version`.
- [ ] Commit: `Add uv skill written from the uv docs`.

**Acceptance:** verification 1, 3, 4, 6; the Verify recipe run in a scratch `uv init` project in the scratchpad, output in the report.

### Task 8: Vendor `pydantic`, `building-pydantic-ai-agents`, `pydantic-ai-harness`

**Size:** small. **Stack:** skills. **REQUIRED:** prior-art, review-testing-rules.
**Files:** `skills/python/pydantic/{SKILL.md,LICENSE,SOURCE.md}`; `skills/python/building-pydantic-ai-agents/{SKILL.md,references/*.md (11 files),LICENSE,SOURCE.md}`; `skills/python/pydantic-ai-harness/{SKILL.md,references/CODE-MODE.md,LICENSE,SOURCE.md}`.

- [ ] Recipe with `pydantic/skills`, SHA `9e9390ee24d44b32cf5379c58acaebd7563f5f86`, sparse set `plugins/pydantic/skills/pydantic plugins/ai/skills/building-pydantic-ai-agents plugins/pydantic-ai-harness/skills/pydantic-ai-harness`. Three rsyncs, one per skill, subtree = the `skills/<name>` directory (not the plugin wrapper; `.claude-plugin/plugin.json` and the plugin README are not vendored).
- [ ] Step 3: copy the repo-root `LICENSE` (MIT) into each of the three directories. Three `SOURCE.md` files; the `pydantic` one names `skills/python/pydantic-house-rules` as the house override location.
- [ ] Step 5 diff per skill: additions `SOURCE.md` and `LICENSE` only.
- [ ] Commit: `Vendor the pydantic, building-pydantic-ai-agents and pydantic-ai-harness skills`.

**Acceptance:** verification 1, 3, 5, for each of the three; frontmatter names are `pydantic`, `building-pydantic-ai-agents`, `pydantic-ai-harness` and match the directories.

### Task 9: Write `pydantic-house-rules` (the named adaptation)

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/python/pydantic-house-rules/SKILL.md`. **After:** Task 8.

The vendored `pydantic` skill (SHA `9e9390ee`, `SKILL.md` lines 8 to 15) says, verbatim:

> "In a nutshell, Pydantic is dataclasses with runtime validation. It leverages type hints to understand how validation (and serialization) should be performed. It is mostly useful when dealing with external untrusted data, for example when defining an HTTP API."

> "It is generally *not* recommended to use Pydantic to define classes that are instantiated within the user code. By doing so, you will lose flexibility (e.g. can't use types not supported by Pydantic, harder to perform post init changes). It is usually better to use vanilla classes (or standard library dataclasses) in this case, as a static type checker will already catch type mismatches."

The house rule (owner, standing: "Pydantic v2 models everywhere, no dataclasses; Temporal via pydantic data converter") overrides the second paragraph. Spec 4.5: house > vault > community.

- [ ] Frontmatter `name: pydantic-house-rules`, description "Use alongside the vendored pydantic skill on any Python model, DTO, config or state class. House precedence: Pydantic v2 models everywhere, no dataclasses."
- [ ] Sources: https://docs.pydantic.dev/latest/concepts/models/ "Models | Pydantic Docs"; https://docs.pydantic.dev/latest/concepts/dataclasses/ "Dataclasses | Pydantic Docs" (cited to state that `pydantic.dataclasses` is also not the house shape); the vendored `skills/temporal/temporal-developer/references/python/data-handling.md` for the data converter.
- [ ] Quote the overridden sentences above under `## What this overrides`, then state the rule: internal classes are `BaseModel` subclasses too; `model_config = ConfigDict(frozen=True)` for value objects; `model_validate` at boundaries and `model_dump` on the way out; Temporal payloads through `pydantic_data_converter`; UUIDv7 ids as `uuid.UUID` fields.
- [ ] `## Rules` also inherit the vendored skill's mechanics by reference (constraints, validators, discriminated unions): do not duplicate them.
- [ ] `## Anti-patterns`: `@dataclass` anywhere in app code; `TypedDict` for domain state; `dict` payloads across a workflow boundary.
- [ ] `## Verify`: `grep -rn '@dataclass\|from dataclasses' <src>` returns nothing; `uv run python -c 'from pydantic import BaseModel; print(BaseModel.model_validate)'` proves v2.
- [ ] In-task, re-grep the pinned vendored file for `dataclass` and `vanilla class` and quote any sentence beyond the two above; the review checks the quotes against `skills/python/pydantic/SKILL.md` byte for byte.
- [ ] Commit: `Add pydantic-house-rules overriding the vendored dataclass advice`.

**Acceptance:** verification 1, 3, 4, 6; the quoted text matches the vendored file exactly (`grep -F` of each quoted sentence against it succeeds); Task 18 routes `pydantic-house-rules` on every row that routes `pydantic`.

### Task 10: Vendor `fastapi`

**Size:** small. **Stack:** skills. **REQUIRED:** prior-art, review-testing-rules.
**Files:** `skills/python/fastapi/{SKILL.md,references/{dependencies,other-tools,path-operations,pydantic,responses,streaming}.md,LICENSE,SOURCE.md}`.

- [ ] Recipe with `fastapi/fastapi`, SHA `50113da16fec53b66b80d75e80a89296de4fa5a5`, sparse set `fastapi/.agents/skills/fastapi` (the skill sits under the `fastapi/` package directory, so the sparse path starts with `fastapi/`; the sourcing report's row 3 path is correct as written). Subtree = that directory (7 files).
- [ ] Step 3: repo-root `LICENSE` (MIT). `SOURCE.md`.
- [ ] Step 5 diff: additions `SOURCE.md` and `LICENSE` only.
- [ ] Commit: `Vendor the FastAPI in-repo skill`.

**Acceptance:** verification 1, 3, 5; frontmatter `name: fastapi`.

### Task 11: Write `kubectl` and `kustomize`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/k8s-gitops/kubectl/SKILL.md`, `skills/k8s-gitops/kustomize/SKILL.md`.

Docs (200 on 2026-09-10): https://kubernetes.io/docs/reference/kubectl/ "Command line tool (kubectl)"; https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/ "kubectl diff"; https://kubernetes.io/docs/concepts/configuration/overview/ "Kubernetes Configuration Good Practices"; https://kustomize.io/ "Kustomize - Kubernetes native configuration management"; https://kubectl.docs.kubernetes.io/references/kustomize/ "Kustomize | SIG CLI"; https://kubectl.docs.kubernetes.io/references/kustomize/cmd/build/ "kustomize build | SIG CLI". Forge pins kubectl 1.35.8; check `Taskfile.yml` for whether it uses `kubectl kustomize` or a standalone `kustomize` and cite that.

- [ ] `kubectl` `## When to apply`: any manifest under `manifests/**` or `k8s/**`, any imperative operation during verification. `## Rules`: read-only first (`get`, `describe`, `logs`, `diff`) and `--dry-run=server` before any write; in a GitOps repo Argo owns the apply, so `kubectl apply` by hand is a drift you must revert; resource requests and limits; labels and selectors; namespaces explicit; `-o jsonpath` for assertions in tests (forge's `tests/*.sh` are the house pattern). `## Anti-patterns`: `kubectl apply` in an Argo-managed namespace; `latest` images; secrets as plain `Secret` manifests (route to `sops-age`); `kubectl delete` without `--dry-run` first. `## Verify`: `kubectl diff -f <file>` (exit 0 means in sync, 1 means drift), `kubectl apply --dry-run=server -f <file>`, `kubectl get <kind> -n <ns> -o jsonpath=...`.
- [ ] `kustomize` `## When to apply`: `kustomization.yaml`, bases and overlays, patches, generators. `## Rules`: `resources` list explicit; strategic-merge versus JSON6902 patches and when each; `namespace` and `commonLabels` at the overlay; generators for ConfigMaps with hash suffixes and the `disableNameSuffixHash` trade-off; Argo CD renders kustomize directories natively. `## Anti-patterns`: editing rendered output; overlays that re-declare whole resources; `commonLabels` that rewrite selectors on existing Deployments. `## Verify`: `kubectl kustomize <dir> | kubectl apply --dry-run=server -f -` (or `kustomize build`), and `kubectl diff -k <dir>`.
- [ ] Commit: `Add kubectl and kustomize skills written from the kubernetes.io and SIG CLI docs`.

**Acceptance:** verification 1, 3, 4, 6 for both files; Verify run against forge `manifests/ntfy/` (kustomization) with output in the report.

### Task 12: Write `sops-age`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/k8s-gitops/sops-age/SKILL.md`.

Docs (200 on 2026-09-10): https://getsops.io/docs/ "SOPS: Secrets OPerationS"; https://github.com/getsops/sops#usage "GitHub - getsops/sops"; https://github.com/FiloSottile/age "GitHub - FiloSottile/age". Forge pins sops 3.13.3 and age 1.3.2; the skill states both.

- [ ] `## When to apply`: `.sops.yaml`, `*.enc.yaml`, any Kubernetes `Secret` committed to git, key rotation, adding a recipient.
- [ ] `## Rules`: `.sops.yaml` `creation_rules` with `path_regex` and `age` recipients; `encrypted_regex: ^(data|stringData)$` so `kind`, `metadata` stay readable and Argo/kustomize can still see the resource; `sops updatekeys` after a recipient change; the age private key lives outside the repo (`SOPS_AGE_KEY_FILE`); a canary secret proves decryption in CI (forge `manifests/forge-secrets/secrets/sops-canary.enc.yaml`); `security-review` is always on for these files.
- [ ] `## Anti-patterns`: a file matching no `creation_rules` path committed in plain text; encrypting `metadata`; the age key in the repo, a Taskfile or a screenshot; `sops -d` output redirected into a tracked file.
- [ ] `## Verify`: `sops -d <file>.enc.yaml | yq '.kind,.metadata.name'` (prints, values still masked); `sops -d --extract '["data"]' <file>.enc.yaml >/dev/null && echo ok`; `git grep -nE 'AGE-SECRET-KEY-1'` returns nothing; `sops updatekeys --yes <file>` after editing recipients.
- [ ] Commit: `Add sops-age skill written from the SOPS and age docs`.

**Acceptance:** verification 1, 3, 4, 6; the Verify recipe run against forge's canary file if the age key is available, else the report shows `sops --version` and `age --version` outputs and says the decrypt step was not run.

### Task 13: Write `microsoft-agent-framework`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/agents/microsoft-agent-framework/SKILL.md`, `skills/agents/microsoft-agent-framework/rules/*.md` if over ~250 lines; delete `skills/agents/.gitkeep`.

Docs (200 on 2026-09-10): https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview "Microsoft Agent Framework Overview"; https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/run-agent "Running Agents"; https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/overview "Workflow capabilities"; https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/chat-client-agent "Custom Agents"; https://github.com/microsoft/agent-framework/blob/main/docs/decisions/0037-agent-skills-design.md. Python is the house default; cite the Python tabs and the PyPI package name the docs give; record the framework version.

- [ ] `## When to apply`: any agent, tool, workflow or checkpoint built on the framework; choosing between a single agent call and a workflow; structured outputs.
- [ ] `## Rules`: agent construction with a chat client; tools as typed functions with Pydantic parameter models (house rule, Task 9); structured output via a Pydantic response model; workflows for multi-step work with checkpoints and resume; state typed and explicit; observability hooks (OpenTelemetry) on every call; token and cost budget per step; the harvested `agent-workflow-rules` pack governs where the docs are silent.
- [ ] `## Anti-patterns`: parsing free text for control flow; one giant prompt instead of a workflow; hidden module-level agent state; secrets in prompt templates; LLM-as-judge deciding pass/fail without deterministic thresholds.
- [ ] `## Verify`: `uv run python -c 'import <package>; print(<package>.__version__)'` with the package name from the docs; a minimal agent run script under the scratchpad that returns a structured Pydantic result, with its output pasted.
- [ ] Commit: `Add microsoft-agent-framework skill written from the Microsoft Learn docs`.

**Acceptance:** verification 1, 3, 4, 6; the report names the framework version the docs described and the Verify output.

### Task 14: Vendor the three Playwright skills

**Size:** small. **Stack:** skills. **REQUIRED:** prior-art, review-testing-rules.
**Files:** `skills/qa/playwright-cli/{SKILL.md,references/*.md (10 files),LICENSE,SOURCE.md}`; `skills/qa/playwright-trace/{SKILL.md,LICENSE,SOURCE.md}`; `skills/qa/playwright-component-testing/{SKILL.md,references/*.md (5),templates/react/*,templates/vue/*,LICENSE,SOURCE.md}`; delete `skills/qa/.gitkeep`.

- [ ] Recipe with `microsoft/playwright`, SHA `af74c938e45f3e759dc2521993f201389eb16cb6`, sparse set `packages/playwright-core/src/tools/skills`. Three rsyncs, one per skill directory.
- [ ] Step 3: repo-root `LICENSE` (Apache-2.0) and repo-root `NOTICE` (present at this SHA: "Playwright / Copyright (c) Microsoft Corporation / This software contains code derived from the Puppeteer project") into each of the three directories; Apache-2.0 section 4(d) requires the NOTICE to travel with redistributions. Three `SOURCE.md`, each naming NOTICE on the License line. Upstream frontmatter includes `allowed-tools`; keep it byte-identical.
- [ ] Step 5 per skill: additions `SOURCE.md`, `LICENSE` and `NOTICE` only. (grafana/skills, pydantic/skills, fastapi and temporal have no root NOTICE, checked 2026-09-10, so their tasks add two files, not three.)
- [ ] Commit: `Vendor the playwright-cli, playwright-trace and playwright-component-testing skills`.

**Acceptance:** verification 1, 3, 5 for each; if `claude plugin validate` rejects `allowed-tools`, ESCALATE (never edit).

### Task 15: Write `bruno`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/qa/bruno/SKILL.md`.

Docs (200 on 2026-09-10): https://docs.usebruno.com/bru-cli/overview "Bruno CLI - Bruno Docs"; https://docs.usebruno.com/bru-cli/runCollection "Command Examples - Bruno Docs". Candidates: the environments and secrets pages under the same docs tree.

- [ ] `## When to apply`: `*.bru` files, `bruno.json`, API contract checks in the qa node, CI collection runs.
- [ ] `## Rules`: collection layout and `bruno.json`; environments per target with secrets injected via `--env-var` or a git-ignored `.env`, never committed; assertions on values, not just status (per `qa-verification`); `bru run --env <env> --reporter-junit <file>` as the evidence artifact; folder-scoped runs for one feature.
- [ ] `## Anti-patterns`: tokens in `.bru` or environment files; screenshots of the GUI runner as evidence; `bru run` with no assertions; skipping the failing request to go green.
- [ ] `## Verify`: `bru run <folder> --env <env> --env-var TOKEN=$TOKEN --reporter-junit results.xml` (exit 0, junit file present); `bru --version`.
- [ ] Commit: `Add bruno skill written from the Bruno CLI docs`.

**Acceptance:** verification 1, 3, 4, 6; Verify run against a two-request scratch collection in the scratchpad against `https://httpbin.org` or a local server, output in the report.

### Task 16: Vendor `promql`, `loki`, `tempo`

**Size:** small. **Stack:** skills. **REQUIRED:** prior-art, review-testing-rules.
**Files:** `skills/observability/promql/{SKILL.md,references/patterns.md,LICENSE,SOURCE.md}`; `skills/observability/loki/{SKILL.md,LICENSE,SOURCE.md}`; `skills/observability/tempo/{SKILL.md,references/{architecture-and-operations,traceql}.md,LICENSE,SOURCE.md}`; delete `skills/observability/.gitkeep`.

- [ ] Recipe with `grafana/skills`, SHA `51d33e71e191b409bbd25fc7be2684c610d18166`, sparse set `skills/grafana-core/promql skills/grafana-lgtm/loki skills/grafana-lgtm/tempo`. Three rsyncs. Upstream frontmatter names are `promql`, `loki`, `tempo` and carry `license: Apache-2.0`.
- [ ] Step 3: repo-root `LICENSE` (Apache-2.0) into each. Three `SOURCE.md`.
- [ ] Step 5 diff per skill: additions `SOURCE.md` and `LICENSE` only.
- [ ] Commit: `Vendor the Grafana promql, loki and tempo skills`.

**Acceptance:** verification 1, 3, 5 for each.

### Task 17: Harvest the four rule packs into `skills/rules`

**Size:** standard. **Stack:** skills. **REQUIRED:** prior-art, superpowers:writing-skills, review-testing-rules.
**Files:** `skills/rules/{backend-rules,architecture-resilience-rules,agent-workflow-rules,review-testing-rules}/SKILL.md`; delete `skills/rules/.gitkeep`.

Sources: `~/.claude/skills/<name>/SKILL.md` (43, 78, 28, 46 lines on 2026-09-10). Spec 4.3 names five packs including `frontend-rules`; that one is out of this ask (see Open questions).

- [ ] Copy each file verbatim, then the scrub pass: grep for `koach`, `@equival`, `packages/`, `he+en`, `openwiki`; none are expected (the packs are generic), record the grep result. Keep `name` and `description` unchanged: spec 4.3 says the packs MOVE into the plugin, and the forge profile's existing rows (`architecture-resilience-rules`, `review-testing-rules`) must resolve without edits.
- [ ] Add one line under the H1 of each: `Harvested from the owner's global rule packs on 2026-09-10 (spec 4.3); the plugin copy is the portable one.`
- [ ] Name collision, resolved by the reviewer's reproduction on 2026-09-10: on this machine a bare `review-testing-rules` resolves to `~/.claude/skills/review-testing-rules` (the global copy) while plugin skills answer to the `graph-engineering:` prefix. Interim consequence: harmless, the two copies are byte-identical apart from the provenance line. Record in the report that dispatches may write `graph-engineering:<name>` to force the plugin copy, and that Task 20 is the owner's step that removes the ambiguity.
- [ ] Commit: `Harvest the backend, architecture-resilience, agent-workflow and review-testing rule packs`.

**Acceptance:** verification 1, 3, 6; `diff <(sed 1,5d ~/.claude/skills/<name>/SKILL.md) <(sed 1,6d skills/rules/<name>/SKILL.md)` is empty for each (only the provenance line differs), pasted in the report.

### Task 20: Owner step: retire the four global rule packs

**Size:** small. **Stack:** docs. **REQUIRED:** prior-art, review-testing-rules. **After:** Task 17. **Owner-executed** (it edits `~/.claude`, which no agent touches); the implementer-simple lane only writes the instructions and records the result.
**Files:** `docs/superpowers/runs/2026-09-10-rule-pack-move.md`.

Spec 4.3 says the global packs move into the plugin, not copy. Until the global copies are gone, a bare `backend-rules` on this machine resolves to `~/.claude/skills/backend-rules` (reviewer reproduction, 2026-09-10) and the plugin copy is reachable only as `graph-engineering:backend-rules`.

- [ ] Write the run doc with the manual step, verbatim for the owner: after Task 17 is merged and `claude plugin update graph-engineering` (or a `--plugin-dir` session) shows the four plugin skills, run `rm -r ~/.claude/skills/{backend-rules,architecture-resilience-rules,agent-workflow-rules,review-testing-rules}` and `~/.claude/CLAUDE.md`'s "On-Demand Rule Packs" list keeps working because the plugin supplies the same names.
- [ ] Record the interim facts: bare names resolve to the global copy (identical content, harmless); dispatches may use the `graph-engineering:` prefix to force the plugin copy; `frontend-rules` stays global until its own harvest.
- [ ] Owner runs the step and confirms in a `--plugin-dir` session that `/review-testing-rules` now answers with the plugin cache path; the confirmation line goes into the run doc.
- [ ] Commit: `Record the rule-pack move and the owner step that retires the global copies`.

**Acceptance:** the run doc exists with the exact `rm` line and the confirmation line; nothing under `~/.claude` is changed by an agent.

### Task 18: Routing rows, `/graph-init` detection, README, version 0.8.0

**Size:** standard. **Stack:** templates, commands, docs, manifest. **REQUIRED:** prior-art, review-testing-rules. **After:** Tasks 1 to 17.
**Files:** `templates/graph-profile.yaml`, `commands/graph-init.md`, `README.md`, `.claude-plugin/plugin.json`.

- [ ] Add a comment above `routing` stating the glob dialect: globstar (`**`) plus brace expansion, minimatch-style, matched against repo-relative paths; a matcher check is `wcmatch.glob.globmatch(path, key, flags=GLOBSTAR | BRACE | DOTGLOB)`. Then add these routing rows, after the `**/{migrations,schemas}/**` row and before `always`, each with a one-line comment (globs match forge's tree today: `argocd/**/*.yaml`, `manifests/**`, `observability/**`, `.sops.yaml`, `**/*.enc.yaml`, `**/kustomization.yaml`; and the plan-5 additions `**/Chart.yaml`, `**/*.py`, `tests/**/*.spec.ts`, `**/*.bru`):

```yaml
  # Python: uv projects, Pydantic v2 (house rule overrides the vendored dataclass advice), FastAPI.
  "**/*.py":
    impl: [uv, pydantic, pydantic-house-rules, fastapi, backend-rules, architecture-resilience-rules]
    review: [pydantic, pydantic-house-rules, fastapi, backend-rules, architecture-resilience-rules]
    qa: []
  "**/{pyproject.toml,uv.lock,.python-version}":
    impl: [uv]
    review: [uv]
  # Agents: Microsoft Agent Framework by house default, Pydantic AI when the repo uses it.
  "**/agents/**/*.py":
    impl: [microsoft-agent-framework, building-pydantic-ai-agents, agent-workflow-rules]
    review: [microsoft-agent-framework, agent-workflow-rules]
  # Temporal: workflows and activities directories.
  "**/{workflows,activities}/**/*.py":
    impl: [temporal-developer, pydantic-house-rules, architecture-resilience-rules]
    review: [temporal-developer, architecture-resilience-rules]
  # GitOps: Argo CD Applications (Argo renders Helm and kustomize, so both ride along).
  "argocd/**/*.{yaml,yml}":
    impl: [argocd, helm, kubectl, architecture-resilience-rules]
    review: [argocd, helm]
    qa: [kubectl]
  "manifests/**":
    impl: [kubectl, kustomize]
    review: [kubectl]
    qa: [kubectl]
  "**/Chart.yaml":
    impl: [helm]
    review: [helm]
  "**/templates/**/*.{yaml,yml,tpl}":
    impl: [helm]
    review: [helm]
  "**/kustomization.{yaml,yml}":
    impl: [kustomize]
    review: [kustomize]
  # CloudNativePG: name the directory that holds your Cluster manifests (forge: manifests/forge-pg*).
  "**/{postgres,cnpg}/**":
    impl: [cloudnativepg]
    review: [cloudnativepg]
  "**/*-pg/**":
    impl: [cloudnativepg]
    review: [cloudnativepg]
  "**/*-pg-*/**":
    impl: [cloudnativepg]
    review: [cloudnativepg]
  # Envoy Gateway: manifests are named by kind; the gateway-* directories hold policies and exemptions.
  "**/{httproute,securitypolicy,backendtlspolicy,backendtrafficpolicy,clienttrafficpolicy,gateway,gatewayclass,referencegrant}*.{yaml,yml}":
    impl: [envoy-gateway]
    review: [envoy-gateway, security-review]
  "**/{gateway,gateway-*}/**":
    impl: [envoy-gateway]
    review: [envoy-gateway, security-review]
  # LLM gateway (agent-router, formerly Envoy AI Gateway).
  "**/{ai-gateway,agent-router,llm-gateway}/**":
    impl: [agent-router, envoy-gateway]
    review: [agent-router, security-review]
  # Secrets: sops + age; security-review is always on and repeated here on purpose.
  "{.sops.yaml,**/*.enc.yaml,**/*.enc.yml}":
    impl: [sops-age]
    review: [sops-age, security-review]
    qa: []
  # QA: Playwright specs (the **/*.{ts,tsx} row above also matches; the union is intended).
  "{tests/**/*.spec.ts,playwright.config.ts}":
    impl: [playwright-cli, playwright-component-testing]
    review: [playwright-cli]
    qa: [playwright-cli, playwright-trace, ux-evidence]
  "{**/*.bru,**/bruno.json}":
    impl: [bruno]
    qa: [bruno]
  # Observability: PromQL, LogQL, TraceQL.
  "{observability/**,**/dashboards/**/*.json,**/*rule*.{yaml,yml}}":
    impl: [promql, loki, tempo]
    review: [promql, loki, tempo]
    qa: [promql, loki, tempo]
```

- [ ] `always.impl` gains `review-testing-rules` (the pack every task in every stack reads; it is now portable).
- [ ] `commands/graph-init.md` step 2: add detection of `argocd/`, `manifests/`, `**/Chart.yaml`, `**/kustomization.yaml`, `.sops.yaml`, `*.enc.yaml`, `observability/`, `playwright.config.ts`, `*.bru`, `**/{workflows,activities}/**/*.py`; step 6 keeps only rows whose files occur.
- [ ] README: a `## Competencies` section listing the groups (`ios`, `android`, `react`, `supabase`, `python`, `agents`, `k8s-gitops`, `temporal`, `qa`, `observability`, `security`, `privacy`, `ux`, `content`, `process`, `rules`), the provenance rule (vendored trees carry `SOURCE.md` and the upstream license, are never edited, and house overrides live in a sibling skill), and the pointer to this plan and the sourcing report.
- [ ] `.claude-plugin/plugin.json` `version` 0.7.0 to 0.8.0 (README: installs pick up by version, not commit).
- [ ] Commit: `Route the python, agents, k8s-gitops, temporal, qa and observability skills; 0.8.0`.

**Acceptance:** verification 1, 2, 6; every skill name in the new rows exists as `skills/*/<name>/SKILL.md` (`for n in $(...); do test -f skills/*/$n/SKILL.md; done` pasted); `yq '.routing | keys' templates/graph-profile.yaml` parses.

### Task 19: Agent fallback catalogs, all nine agent files

**Size:** standard. **Stack:** agents. **REQUIRED:** prior-art, review-testing-rules. **After:** Tasks 1 to 17.
**Files:** all nine agent files, each of which carries a fallback catalog under one of three headings (checked 2026-09-10): `agents/implementer.md`, `agents/implementer-simple.md`, `agents/qa.md` (`## Competency catalog and routing fallback`); `agents/reviewer.md` (`## Lens catalog and routing fallback`); `agents/researcher.md`, `agents/ux-designer.md`, `agents/content-writer.md`, `agents/media-producer.md` (`## Skill routing fallback`). `agents/planner.md` has no catalog; if it has none on the day, leave it.

- [ ] Rows, mirroring Task 18's routing: `*.py` (uv, pydantic, pydantic-house-rules, fastapi, backend-rules); `**/agents/**/*.py` (microsoft-agent-framework, building-pydantic-ai-agents, agent-workflow-rules); `**/{workflows,activities}/**/*.py` (temporal-developer); `argocd/**` (argocd, helm, kubectl); `manifests/**` (kubectl, kustomize, plus cloudnativepg, envoy-gateway, agent-router by directory); `Chart.yaml`, `templates/**` (helm); `kustomization.yaml` (kustomize); `.sops.yaml`, `*.enc.yaml` (sops-age); `tests/**/*.spec.ts` (playwright-cli, playwright-trace, playwright-component-testing); `*.bru` (bruno); `observability/**`, `dashboards/**/*.json` (promql, loki, tempo).
- [ ] `implementer.md`, `implementer-simple.md`, `qa.md`: the `impl`/`qa` half of each row. `reviewer.md`: the `review` half (argocd, helm, kubectl, kustomize, cloudnativepg, envoy-gateway, agent-router, sops-age, pydantic, pydantic-house-rules, fastapi, backend-rules, architecture-resilience-rules, agent-workflow-rules, temporal-developer, playwright-cli, promql, loki, tempo; `security-review` is already preloaded). `researcher.md`, `ux-designer.md`, `content-writer.md`, `media-producer.md`: one row each, "any of the stacks above: the same skills the implementer table names, loaded read-only for context", so a research or design leg on a GitOps repo does not work from priors.
- [ ] Commit: `Teach every agent fallback catalog the new stack rows`.

**Acceptance:** verification 1, 6; `git diff --stat` after the commit lists every agent file named above; `grep -c 'temporal-developer' agents/*.md` is at least 1 for each of the eight catalog-bearing files; the reviewer's table names the review-half skills listed above and no `impl`-only skill.

### Task 21: Spec 4.2 amendment: vendoring bare and untagged upstreams

**Size:** small. **Stack:** docs. **REQUIRED:** prior-art, review-testing-rules. **After:** Task 0.
**Files:** `docs/superpowers/specs/2026-08-31-graph-engineering-plugin-design.md` (append under `## Amendments`).

Spec 4.2 says "Adopted skills are depended on, not vendored". That sentence covers plugin upstreams only; the forge #41 amendment review (2026-09-10) ruled that the rule for everything else is written down in the spec, not left to this plan.

- [ ] Append a block headed `### 2026-09-10 - Vendoring bare and untagged upstreams` after the prior-art amendment, stating: a bare skill tree (no `.claude-plugin/plugin.json`) is vendored under `skills/<group>/<name>/`, pinned by commit SHA, byte-identical, with the upstream license file alongside and a `SOURCE.md` (URL, SHA, date, license, refresh recipe); a plugin upstream with no tagged release is vendored the same way until a `{plugin-name}--v{version}` tag exists, then flips to a `dependencies` entry with a semver constraint and, for another marketplace, an `allowCrossMarketplaceDependenciesOn` entry; house adaptations never edit the vendored tree and live in a sibling skill (spec 4.5). State the reasoning exactly, distinguishing source kinds per the plugin-dependencies reference ("Tag plugin releases for version resolution"): for `github`, `url` and `git-subdir` sources a constraint with no matching tag fails the install; for a relative-path plugin with no matching tag Claude Code installs the marketplace's current copy and checks the constraint at load, so the constraint checks but does not pin, and an untagged upstream floats. Spec 4.2 rule 4 exists so an upstream change cannot land unreviewed; a floating dependency defeats that purpose, therefore vendoring by SHA is the rule until tags exist. Worked example: `pydantic/skills` (three `plugin.json`, a marketplace.json with relative-path sources and `version: 0.1.0`, zero git tags on 2026-09-10) is vendored at `9e9390ee24d44b32cf5379c58acaebd7563f5f86`; the day `pydantic--v0.1.0` exists it becomes `{ "name": "pydantic", "version": "~0.1.0", "marketplace": "pydantic-skills" }` with `pydantic-skills` allow-listed in this plugin's marketplace.json.
- [ ] Cite this plan and `docs/research/2026-09-10-stack-skills-sourcing.md` in the block; one short paragraph on what was rejected (a bare-name dependency, forbidden by 4.2 rule 4; editing vendored files in place, because it breaks the byte-identical refresh).
- [ ] Commit: `Amend spec 4.2: bare and untagged upstreams are vendored by SHA`.

**Acceptance:** verification 6; the block sits under `## Amendments`, dated 2026-09-10, and the worked example's SHA matches Task 8's `SOURCE.md`.

### Task 22: `hooks/hooks.json`: lint on edit, test before stop, handoff on start

**Size:** standard. **Stack:** hooks. **REQUIRED:** prior-art, review-testing-rules, security-review. **After:** Tasks 7 to 10 (forge plan 6 is the first consumer).
**Files:** `hooks/hooks.json`, `hooks/scripts/lint-touched-file.sh`, `hooks/scripts/test-before-stop.sh`, `hooks/scripts/print-handoff.sh`, `README.md` (a `## Hooks` paragraph).

Reuse test passed by the coordinator's ruling: the hooks key on the generic script names `test`, `lint`, `typecheck` across three project conventions and on `docs/HANDOFF.md`; nothing forge-specific, so they belong to the plugin, not the forge repo. Detection order, ruled 2026-09-10: (1) `pyproject.toml` with the script under `[project.scripts]` runs `uv run <script>`; (2) `package.json` `scripts` runs the package manager's `run` (`npm run`, or `pnpm`/`yarn`/`bun` by lockfile); (3) `Taskfile.yml` with a `test` task (present in `task --list-all --silent`) runs `task test`, Stop only, since a single-file lint or typecheck has no Taskfile shape. Exit 0 when none applies. Forge has a Taskfile today, so its Stop hook is live from day one.

Docs to fetch (200 on 2026-09-10): https://code.claude.com/docs/en/hooks (markdown at `hooks.md`) for the event list, matcher syntax, JSON input fields, exit-code semantics and the Stop loop protection; https://code.claude.com/docs/en/plugins-reference "Hooks" for the `hooks/hooks.json` layout and `${CLAUDE_PLUGIN_ROOT}`; https://docs.astral.sh/uv/concepts/projects/run/ "Running commands | uv" for `uv run` and `[project.scripts]`; https://taskfile.dev/reference/cli/ "Command Line Interface Reference | Task" for `--list-all` (`--list-all --silent` prints only task names, one per line, which is the scripting form). Facts already confirmed from those pages: `PostToolUse` matcher `Edit|Write`; `tool_input.file_path` is absolute for `Write`, `Edit`, `Read`; `SessionStart` input `source` is one of `startup`, `resume`, `clear`, `compact`, `fork`; `Stop` input carries `stop_hook_active` and "Claude Code overrides the hook and ends the turn after 8 consecutive blocks" ("Stop input"; "Stop decision control" calls it the 8-consecutive-continuation cap); exit 2 is a blocking error on events that can block; stderr from an exit-0 hook goes to the debug log only, so an informational hook must print to stdout (or use the JSON `additionalContext` form) to be seen.

- [ ] `hooks/hooks.json` with three entries, every command in exec form (`command` plus `args`) pointing at `${CLAUDE_PLUGIN_ROOT}/hooks/scripts/<name>.sh`, executable bit set:
  - `PostToolUse`, matcher `Edit|Write`: `lint-touched-file.sh` reads the JSON input, resolves `tool_input.file_path`, and acts only when that path is under `$CLAUDE_PROJECT_DIR` (compare the canonicalised path prefix; a path outside the project exits 0 silently, so an edit inside a scratchpad clone of a third-party repo never runs that repo's scripts). Within the project it walks upward from the file no further than `$CLAUDE_PROJECT_DIR` to find the nearest project file, in the ruled order: `pyproject.toml` with `lint`/`typecheck` under `[project.scripts]` runs `uv run lint <file>` then `uv run typecheck <file>`; else `package.json` with `scripts.lint`/`scripts.typecheck` (`jq -e`) runs `<pm> run lint -- <file>` then `<pm> run typecheck`. Always exits 0; findings go to stdout as plain text so they inform and never block. No project file or no such script: exit 0 silently.
  - `Stop`: `test-before-stop.sh` looks in `$CLAUDE_PROJECT_DIR` only, in the ruled order: `pyproject.toml` with `test` under `[project.scripts]` runs `uv run test`; else `package.json` with `scripts.test` runs `<pm> run test`; else `Taskfile.yml` whose `task --list-all --silent` output contains a line `test` runs `task test`. Exit 2 with the failing summary on stderr (blocks until green), exit 0 when green or when none applies. It reads `stop_hook_active` from the input and includes it in the stderr line so the loop state is visible. The script header comment and the README paragraph state the documented cap: Claude Code overrides the hook and ends the turn after 8 consecutive blocks (hooks reference, "Stop input").
  - `SessionStart`, no matcher (fires on every `source`, once per session, so no subagent scoping is needed): `print-handoff.sh` prints the first 40 lines of `docs/HANDOFF.md` under `CLAUDE_PROJECT_DIR` to stdout if the file exists, else exits 0 silently.
- [ ] Scripts are POSIX sh or bash with `set -eu`, quote every path, depend only on `jq` (state that dependency in the README paragraph; exit 0 with a one-line stdout notice if `jq` is missing rather than failing the hook), and never run anything from the edited file's contents. `security-review` lens: no `eval`, no unquoted expansion of `file_path`, no network.
- [ ] README `## Hooks`: what each hook does, the three project conventions and the order they are tried, the script names it keys on, the project-directory bound on `PostToolUse`, the `jq` dependency (and `uv`/`task` being invoked only when their project file is present), the 8-consecutive-blocks cap citing "Stop input", and how a repo opts out (Claude Code's per-hook disable, cite the page section).
- [ ] Verify in the scratchpad with four throwaway projects: uv (`uv init`, `[project.scripts] test = ...` failing then passing), npm (`scripts.test` `exit 1` then `exit 0`), Taskfile (`test:` task failing then passing), and one with nothing; run each script by piping a hand-written JSON input (`echo '{"tool_input":{"file_path":"..."}}' | CLAUDE_PROJECT_DIR=<dir> hooks/scripts/lint-touched-file.sh`) and record exit codes: lint 0 in every case including a `file_path` outside `CLAUDE_PROJECT_DIR` (and confirm no script ran for the outside path); test-before-stop 2 then 0 for each of the three conventions, 0 for the empty project; print-handoff prints 40 lines then exits 0 without the file. Then `claude plugin validate /Users/shonpazarker/projects/graph-engineering` exit 0, and one interactive `claude --plugin-dir` session in the Taskfile project (forge's shape) showing the SessionStart text and a blocked Stop.
- [ ] Commit: `Add plugin hooks: lint on edit, test before stop, handoff on session start`.

**Acceptance:** verification 1, 2 (hooks.json is valid JSON), 6; the recorded exit codes for all four projects and the outside-path case; the loop-cap sentence cites "Stop input"; the four doc pages named above are listed with titles in the README paragraph or the script headers; the scripts pass `shellcheck` if installed (say so if not).

### Task 23: Dry dispatch against a forge file list

**Size:** standard. **Stack:** docs. **REQUIRED:** prior-art, review-testing-rules. **After:** Tasks 18, 19, 21, 22.
**Files:** `docs/superpowers/runs/2026-09-10-stack-skills-dry-dispatch.md`.

This is the gate for the whole plan: `/graph-ship` step 4 resolution, done by hand against the new template, must resolve every row to an existing skill.

- [ ] Sample file list (existing forge files first, then the plan-5 shapes): `argocd/root.yaml`, `argocd/apps/loki.yaml`, `argocd/values-health-data.yaml`, `manifests/forge-pg/cluster.yaml`, `manifests/forge-pg-backup/scheduledbackup.yaml`, `manifests/gateway-auth/securitypolicy-bugsink.yaml`, `manifests/gateway-exemptions/httproute-gatus-health.yaml`, `manifests/forge-secrets/secrets/nats-auth.enc.yaml`, `.sops.yaml`, `manifests/ntfy/kustomization.yaml`, `observability/kustomization.yaml`, `observability/dashboards/cnpg-cluster.json`, `tests/81-cnpg.sh`, `docs/HANDOFF.md`; plan-5 shapes: `charts/temporal/Chart.yaml`, `manifests/temporal/httproute.yaml`, `manifests/ai-gateway/backend-foundry.yaml`, `apps/codec-server/pyproject.toml`, `apps/codec-server/src/codec/workflows/encode.py`, `apps/codec-server/src/codec/agents/router.py`, `tests/e2e/login.spec.ts`, `tests/api/health.bru`.
- [ ] Match by machine, not by hand: `uv run --with wcmatch python match.py` in the scratchpad, where `match.py` parses the routing keys out of `templates/graph-profile.yaml` and runs `wcmatch.glob.globmatch(path, key, flags=GLOBSTAR | BRACE | DOTGLOB)` over the sample list; paste its output. The template states this dialect in a comment (globstar plus brace expansion, minimatch-style; git pathspec has no brace expansion, so `git ls-files` is not a valid checker for these rows). The planner ran this matcher on 2026-09-10 against the rows in Task 18: every sample file matched its intended rows; the one miss it found (`apps/codec-server/pyproject.toml` needs the `**/` prefix) is already fixed in Task 18; `tests/81-cnpg.sh` and `docs/HANDOFF.md` match only `always` in the template, which is expected because forge's own profile carries the `**/*.sh` and `docs/**` rows.
- [ ] For each file: the rows it matches, the REQUIRED list per role (impl, review, qa) as the union plus `always`, and for every name the resolved path `skills/<group>/<name>/SKILL.md` with its frontmatter `name`. One table. Any name with no path is a `NEEDS_SETUP` and fails the task.
- [ ] `claude plugin validate /Users/shonpazarker/projects/graph-engineering` exit 0, output pasted (this run also covers `hooks/hooks.json` from Task 22).
- [ ] Start `claude --plugin-dir /Users/shonpazarker/projects/graph-engineering` in a scratch directory (the owner's shell blocks `-p`, so this is an interactive step) and invoke each new skill once by its `/name` shortcut; record the first line each returned. For the four harvested packs, record which copy the bare name resolves to after the owner's Task 20 step, and that the `graph-engineering:<name>` form loads the plugin copy.
- [ ] Record the forge follow-up the owner runs in the forge repo, not here: `/graph-init --force` or a hand edit adding the rows to `~/projects/forge-platform/.claude/graph-profile.yaml`, plus the stack additions (`apps/**` for Python, `charts/**` for Helm) when plan 5 creates them.
- [ ] Commit: `Record the stack-skills dry dispatch: every routing row resolves`.

**Acceptance:** zero unresolved names; the matcher output; the validate output; the per-skill load lines; the harvested-pack resolution answer; the forge follow-up list.

---

---

## Open questions (each ends spiked or as a stated assumption before the gate)

1. **pydantic trio as dependencies?** Assumption A1 above: vendored, because no `{name}--v{version}` tag exists. Owner may reject.
2. **`frontend-rules` harvest.** Spec 4.3 names five packs; this ask names four. Assumption: `frontend-rules` is harvested in a later react-group task, since `react-rules` already covers most of it. Owner may pull it into Task 17.
3. **CNPG doc version.** Chart appVersion says 1.29.1, forge's HANDOFF says 1.30. Task 3 resolves it in-task from the cluster or chart and cites that version; assumption until then: 1.29.
4. **agent-router doc location.** `theagentrouter.ai` served an untitled page; Task 5 may have to cite the GitHub repo's docs at tag `v1.1.0`. Assumption: repo docs at a tag count as vendor docs.
5. **Name collision with the owner's global packs.** Resolved by reproduction (reviewer, 2026-09-10): a bare name resolves to the global copy; the plugin copy answers to `graph-engineering:<name>`. Task 20 is the owner's manual step that deletes the four global copies; until then the collision is harmless because the content is identical.
6. **Vendor tasks marked `small`.** Reasoning in the task table; owner may flip to `standard`.
7. **`**/*.{ts,tsx}` also matches `tests/**/*.spec.ts`,** so react skills load on Playwright specs. Assumption: the union is acceptable in the template and narrowed per repo.
8. **No profile in this repo.** The stack map in Global Constraints stands in; the owner runs `/graph-init` here so future runs do not need a planner-supplied map.
9. **Pydantic `logfire` plugin** (same repo, version 0.1.4, also untagged) for Python observability is not in this ask; note for the next observability pass.
10. **Envoy Gateway open spikes S1 and S2** belong to forge plan 5, not to this plan; Task 4 writes the related rules as "verify, do not assume" rather than asserting an answer.
11. **Hooks and forge.** With the Taskfile branch (ruling I1) forge's Stop hook runs `task test` from day one; its lint-on-edit stays silent until a `pyproject.toml` or `package.json` appears in plan 5/6. Assumption: that is the intended behaviour, not a gap.
