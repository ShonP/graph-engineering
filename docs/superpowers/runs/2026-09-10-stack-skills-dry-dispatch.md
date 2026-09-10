# Stack skills dry dispatch, 2026-09-10

The closing gate for `docs/superpowers/plans/2026-09-10-stack-skills.md`. It
runs `/graph-ship` step 4 (skill resolution) by hand against the new
`templates/graph-profile.yaml`, over a file list shaped like the forge-platform
repo today plus the shapes forge plan 5 will add, and asks one question: does
every routing row resolve to a skill that exists?

Answer: yes. 22 sample files, 28 routing rows, 35 names routed by the sample,
54 names used anywhere in the template, **0 unresolved**.

Tree under test: worktree `stack-skills/task23` off `1a68c24` (plugin 0.8.0,
every wave merged). Claude Code 2.1.265.

## Prior art

- Reuse candidates checked first. `hooks/scripts/resolve_touched_project.py`
  (Task 22) resolves a touched file to a project root, not a routing row, so it
  is the wrong tool here; rejected. `scripts/check-skill-frontmatter.sh` already
  owns the name-equals-directory check, so this run calls it rather than
  re-implementing it, and the matcher reuses its tolerant line-based
  frontmatter reader for the one file strict YAML rejects (below). `wcmatch`
  is adopted as the matcher because the template's own comment names its
  dialect and its `globmatch` flags.
- Rejected: `git ls-files <pattern>` as the checker. Git pathspec globs have no
  brace expansion, so 14 of the 28 rows would silently match nothing. The
  template says this in a comment; this run did not re-test it.
- Spiked in-task, rung 1: what `claude plugin validate` actually reads. See the
  validate section. Verdict `PARTIAL` for the plan's assumption, and the
  correction is written down there.
- Not re-derived: the sourcing research behind each skill
  (`docs/research/2026-09-10-stack-skills-sourcing.md`).

## The matcher

```
uv run --with wcmatch --with pyyaml python match.py
```

`match.py` is a scratch script. Reproducing it needs only the rule it
implements:

1. `yaml.safe_load(templates/graph-profile.yaml)`, take `routing`, hold `always`
   aside. The template, not `plugin.json`, is the routing truth; `plugin.json`
   only lists the skill directories.
2. For each sample path and each remaining key,
   `wcmatch.glob.globmatch(path, key, flags=GLOBSTAR | BRACE | DOTGLOB)`.
3. Per role, the union of the matched rows' lists plus `always[role]`, in
   first-seen order.
4. Resolve each name to the single `skills/*/<name>/SKILL.md` whose directory
   basename is the name, and read its frontmatter.

The per-file table, the resolved paths and the verbatim matcher output are in
[`2026-09-10-stack-skills-dry-dispatch-table.md`](2026-09-10-stack-skills-dry-dispatch-table.md),
split out to keep both files under the 250-line house limit.

`scripts/check-routing-resolves.sh` makes this repeatable: it fails on any routing- or agent-referenced name that does not resolve to one `skills/*/<name>/SKILL.md`.

Two results worth pulling forward:

- `tests/81-cnpg.sh` and `docs/HANDOFF.md` match no row and get `always` only.
  Expected: forge's own profile carries `**/*.sh` and `docs/**`.
- `argocd/values-health-data.yaml` does **not** trip `**/{Health,Workout}*`.
  That row is prefix-anchored and case-sensitive, so a lowercase `health` in the
  middle of a filename is not a false positive on the iOS row.

One surprise, recorded rather than papered over: `yaml.safe_load` rejects
`skills/python/pydantic-house-rules/SKILL.md`'s frontmatter, whose unquoted
`description` contains `House precedence:` and so reads as a nested mapping. The loader does not care (probe 1 lists
`graph-engineering:pydantic-house-rules` as a live skill) and neither does
`scripts/check-skill-frontmatter.sh`, which parses top-level keys line by line.
The matcher falls back to that same reader and reports when it does. Nothing to
fix today; quoting that description would remove the trap for the next tool
that reaches for a real YAML parser.

## Gate: `scripts/check-skill-frontmatter.sh`

```
$ scripts/check-skill-frontmatter.sh
check-skill-frontmatter: 60 SKILL.md checked, 0 failure(s)
$ echo $?
0
```

Green, which means the two pre-existing `skills/react/tanstack-*` name
mismatches from the plan's verification item 1 are closed. Every frontmatter
`name` equals its directory basename, so the invocation-name question below has
no bite on this tree.

## Gate: `claude plugin validate`

```
$ claude plugin validate /Users/shonpazarker/projects/graph-engineering
Validating marketplace manifest: /Users/shonpazarker/projects/graph-engineering/.claude-plugin/marketplace.json

⚠ Found 1 warning:

  ❯ description: No marketplace description provided. Adding a description helps users understand what this marketplace offers

✔ Validation passed with warnings
$ echo $?
0
```

Same output and exit 0 for the worktree path. `hooks/hooks.json` is inside that
tree, so this run covers Task 22 in the sense the plan meant.

It covers less than the plan assumed, and this is the one correction this run
makes. `--json` shows the target and the empty content list:

```
"target": ".../.claude-plugin/marketplace.json", "type": "marketplace",
"errors": [], "contents": []
```

Because this repo is also a marketplace, `validate <repo>` validates
`marketplace.json` and stops; it never reaches `plugin.json`. Pointing it at
`.claude-plugin/plugin.json` validates the manifest (`type: plugin`, no errors)
and still reports `contents: []`. Pointing it at `skills/` starts component
mode and passes, also with `contents: []`. Two scratch probes explain that:

- `skills/<name>/SKILL.md` with frontmatter `foo: bar` only: component mode
  opens it, warns "No description in frontmatter", says nothing about the
  missing `name`, and exits **0**.
- `skills/<group>/<name>/SKILL.md`, this plugin's layout: component mode finds
  nothing at all and exits 0. It does not recurse into the group directory.

So for this tree `claude plugin validate` is a manifest check and nothing more,
and `scripts/check-skill-frontmatter.sh` is the only thing checking any
SKILL.md, exactly as the script's own header claims.

## Gate: hooks (Task 22)

`claude plugin validate` never opens `hooks/hooks.json`, so the hook checks run
separately:

```
$ python3 -m json.tool hooks/hooks.json > /dev/null ; echo $?
0
$ bash hooks/tests/run-tests.sh | tail -1
passed: 93  failed: 0  skipped: 0
$ echo $?
0
```

## Loader answers

Run by the controller on 2026-09-10 with
`claude --plugin-dir <plugin tree> -p ... --output-format text`, quoted from
`.graph/<run>/task-23-loader-probes.md`. The implementer's own shell cannot run
`claude -p`, so these are the rung-1 observations this section rests on.

- **Listing.** 61 entries prefixed `graph-engineering:` (60 `SKILL.md` files
  plus the `graph-ship` command). The model receives names only, no
  descriptions.
- **Invocation name.** Every skill answers to `graph-engineering:<directory
  name>`. Names seen include `graph-engineering:temporal-developer`,
  `graph-engineering:tanstack-query-rules`,
  `graph-engineering:pydantic-house-rules`, `graph-engineering:backend-rules`.
  The 0.7.0 observation stands: when frontmatter `name` and directory disagree,
  the **directory** wins, which is the opposite of the plan's prior-art note.
  Moot on this tree, because the frontmatter script now forces them to agree,
  and that is precisely why the check is a gate.
- **Extra frontmatter key.** `temporal-developer` carries `version: 0.6.2`. It
  loaded, first heading `# Skill: temporal-developer`. The loader accepts the
  extra key silently.
- **`allowed-tools`.** Accepted, but invoking such a skill is itself a
  permission decision on the tools it grants.
  `graph-engineering:playwright-component-testing` (no `allowed-tools`) loaded,
  `# Component Testing with Playwright`. `playwright-trace` and
  `playwright-cli` both returned `<error>Execute skill: <name></error>` with no
  body under default non-interactive permissions, and `playwright-trace` loaded
  as `# Playwright Trace CLI` under `--allowedTools "Skill" "Bash(npx:*)"` and
  under `--dangerously-skip-permissions`, and failed again under
  `--permission-mode acceptEdits`.
- **Other loads.** `graph-engineering:argocd` loaded, `# Argo CD`.
  `graph-engineering:playwright-e2e-testing` returned `Unknown skill`; the qa
  group holds `playwright-cli`, `playwright-component-testing` and
  `playwright-trace`, and no routing row names the missing one.
- **Coverage, stated plainly.** All 61 names were seen in the listing. Five
  were invoked by name, chosen as the ones carrying an open question, and four
  of those five returned a body; `playwright-cli` aborted under every
  permission variant tried. The rest were resolved on disk by the matcher, not
  loaded one at a time.

Consumer consequence, now written into `README.md` beside the `ask` snippet: an
`ask` or `deny` rule aborts the invocation regardless of `allowed-tools`, so the
two Playwright skills prompt on first use in an interactive session and abort
in `claude -p` or CI unless `Bash(npx:*)` and `Bash(npm:*)` are pre-allowed
there. The README stated the mechanism already but not the consequence; two
sentences were added.

## The five harvested rule packs

`backend-rules`, `architecture-resilience-rules`, `agent-workflow-rules`,
`review-testing-rules`, `frontend-rules`, all under `skills/rules/`. Five, not
the four the plan's Task 20 wording implies.

Each plugin copy differs from the owner's `~/.claude/skills/<name>/SKILL.md` by
exactly one added provenance line and nothing else.

Bare-name resolution today: **the global copy**. The listing shows both a bare
`backend-rules` and a `graph-engineering:backend-rules`, so the two live side by
side and a dispatch that writes the bare name gets the machine-local file. Task
20 (owner-only, not yet run) deletes the global copies; after it, the bare name
is gone and `graph-engineering:<name>` is the only form. Until then, dispatches
should name the prefixed form when they mean the portable copy.

## Forge follow-up, run in the forge repo by the owner

`~/projects/forge-platform/.claude/graph-profile.yaml` predates this plan: it
carries four routing rows of its own (`**/*.{yaml,yml}`, `**/*.sh`, `tests/**`,
`docs/**`) and an `always.impl` of `[prior-art]`. Recommended path is a hand
edit, not `/graph-init --force`, because `--force` regenerates the file and
would drop forge's `docs` stack, its four local rows and its board name.

**Nine rows to add now.** Each has real hits in forge's 279 tracked files today
(hit counts from the same matcher run against `git ls-files`):

| Row | forge files hit |
| --- | --- |
| `argocd/**/*.{yaml,yml}` | 43 |
| `manifests/**` | 103 |
| `**/kustomization.{yaml,yml}` | 11 |
| `**/*-pg/**` | 9 |
| `**/*-pg-*/**` | 1 |
| `**/{httproute,securitypolicy,...,referencegrant}*.{yaml,yml}` | 22 |
| `**/{gateway,gateway-*}/**` | 17 |
| `{.sops.yaml,**/*.enc.yaml,**/*.enc.yml}` | 26 |
| `{observability/**,**/dashboards/**/*.json,**/*rule*.{yaml,yml}}` | 17 |

**Ten more rows when plan 5 lands** (zero hits today, so adding them early is
harmless but pointless): `**/*.py`,
`**/{pyproject.toml,uv.lock,.python-version}`, `**/agents/**/*.py`,
`**/{workflows,activities}/**/*.py`, `**/Chart.yaml`,
`**/{chart,charts}/**/templates/**/*.{yaml,yml,tpl}`,
`**/{ai-gateway,agent-router,llm-gateway}/**`, `**/*.{ts,tsx}`,
`{tests/**/*.spec.ts,playwright.config.ts}`, `{**/*.bru,**/bruno.json}`.

**Three more edits**, not rows:

- `stacks`: add `apps/**` for the Python services and `charts/**` for Helm.
- `always.impl`: add `review-testing-rules` beside `prior-art`, matching the
  template.
- After Task 20, rewrite forge's bare `architecture-resilience-rules` and
  `review-testing-rules` to the `graph-engineering:` form, or the rows point at
  files that no longer exist.

Nineteen rows, three edits.
