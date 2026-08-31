# Spike: can a plugin agent preload plugin-local skills?

Date: 2026-08-31
Status: **ANSWERED - preloading works, under either name form**

## Question

Does `skills:` frontmatter in a plugin-provided agent resolve a
plugin-provided skill, and under what name (`spike-canary` versus
`spike-plugin:spike-canary`)?

## What was run

1. Grepped every installed plugin agent for `skills:` frontmatter. No plugin
   agent on this machine uses it. Koach's project-local agents
   (`web-implementer`, `ios-implementer`, `android-implementer`) do, which
   proves the field works for project-local agents only.
2. Read the official plugins reference at
   `https://code.claude.com/docs/en/plugins-reference`.

## Answer

The reference states plainly:

> Plugin agents support `name`, `description`, `model`, `effort`, `maxTurns`,
> `tools`, `disallowedTools`, `skills`, `memory`, `background`, and
> `isolation` frontmatter fields.

So `skills:` IS supported on a plugin agent. The reference gives no example of
how a skill is named inside that list, so bare versus plugin-qualified remains
open and needs the canary.

Also noted, because two of these are directly useful to this design:

- **`maxTurns`** - a hard turn cap per agent. This is exactly the "strict
  budget, capped" the spec's spike protocol (section 6.1) describes in prose.
- **`isolation: "worktree"`** - an agent can run in its own git worktree.
  Relevant to the implementer, and possibly cheaper than the spine creating
  worktrees itself.
- `effort`, `disallowedTools`, `background`, `memory`.
- For plugin-shipped agents, `hooks`, `mcpServers` and `permissionMode` are
  NOT supported, for security reasons.

## Canary result

Run 2026-08-31 in a session started with `claude --plugin-dir <scratchpad>/spike-plugin`.

| Agent | `skills:` declared as | Returned |
|---|---|---|
| `spike-bare` | `spike-canary` | `PRELOAD-CONFIRMED-7731` |
| `spike-qualified` | `spike-plugin:spike-canary` | `PRELOAD-CONFIRMED-7731` |

Both resolve. A plugin agent can preload a plugin-local skill, and the bare
name is enough - qualifying it is allowed but buys nothing within the same
plugin.

One qualifier on what this proves: the canary shows the skill's content was in
the agent's context. It does not distinguish preloading from an eager
auto-invocation. Both agents were instructed to use no tools and invoke no
skill, so preload is the reasonable reading, but the distinction was not
measured directly.

## The canary, as run

A throwaway plugin is built at
`<scratchpad>/spike-plugin` with one skill and two agents that differ only in
how they name it:

- `spike-bare` declares `skills: [spike-canary]`
- `spike-qualified` declares `skills: [spike-plugin:spike-canary]`

Each is instructed to reply with the canary phrase if the skill is already in
context, or `NO-CANARY` otherwise, using no tools.

To run, in a session started with:

```bash
claude --plugin-dir <scratchpad>/spike-plugin
```

dispatch each agent with the prompt `Report the canary phrase.`

Reading the result:
- `spike-bare` returns `PRELOAD-CONFIRMED-7731` -> bare names work.
- only `spike-qualified` returns it -> plugin-qualified naming is required.
- neither returns it -> the field is accepted but does not resolve plugin-local
  skills, and spine-named dispatch is the only mechanism.

## Recommendation

Preloading is available, so use it where it is unconditional:

> **Unconditional competencies preload; conditional ones route.**

Spine-named dispatch remains the mechanism for anything that depends on the
task - that is what lets one `implementer` definition serve every stack, and it
is what stops an agent skipping a load and writing from priors. But a
competency an agent loads on every single dispatch gains nothing from the hop.

| Agent | Preload | Spine-routed |
|---|---|---|
| `reviewer` | `review-protocol`, `security-review`, `privacy-review` (the profile's `always` lenses) | stack lenses by file extension |
| `planner` | `product-spec` | - |
| `qa` | `test-strategy` | playwright / api-contract / mobile-ui |
| `implementer` | nothing is unconditional across stacks | everything |
| `content-writer` | `content-strategy`, house voice | platform skill by target |

The reviewer is the hot path: three fewer `Skill` invocations on every review.

Bare names are sufficient within a plugin; use them.
