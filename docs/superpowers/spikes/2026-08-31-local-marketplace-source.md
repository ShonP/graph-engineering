# Spike: does a local-directory marketplace source work?

Date: 2026-08-31
Status: **ANSWERED - no, and the real answer is better**

## Question

Can `/plugin marketplace add <local path>` register a local directory, so the
dev loop does not need a commit and push per test?

## What was run

1. Read the registry baseline:

```bash
python3 -c "import json;print(list(json.load(open('~/.claude/plugins/known_marketplaces.json')).keys()))"
```

All five installed marketplaces are GitHub-sourced.

2. Read the official plugins reference and cross-checked against community
write-ups of local plugin development.

## Answer

A local filesystem path is **not** a supported marketplace source type. Local
directories are supported through a different mechanism, which is better suited
to development anyway:

```bash
claude --plugin-dir ~/projects/graph-engineering
```

Properties confirmed by both the official reference and independent write-ups:

- Loads the plugin for the duration of that session, with no install step.
- **Additive**: the loaded plugin joins the normally installed and enabled
  plugins rather than replacing them.
- Multiple flags are allowed: `--plugin-dir a --plugin-dir b`.
- A `.zip` of the plugin directory is also accepted.
- **When a `--plugin-dir` plugin shares a name with an installed marketplace
  plugin, the local copy wins for that session.** This is the property that
  matters: an installed `graph-engineering` can be shadowed by the working copy
  without uninstalling anything.
- A directory qualifies as a plugin by containing `.claude-plugin/plugin.json`.

Separately, any folder under a skills directory (`~/.claude/skills/`,
`.claude/skills/`) containing `.claude-plugin/plugin.json` loads automatically
as `<name>@skills-dir` on the next session - discovered in place, never
installed. Not the dev loop of choice here, but worth knowing before something
loads unexpectedly.

## Recommendation

Dev loop: `claude --plugin-dir ~/projects/graph-engineering`, one session per
test cycle, no commit required and no risk to the installed copy. Ship via the
GitHub marketplace only when a change is ready.

## Spec impact

Section 11's question 2 is closed. Section 10 gains the `--plugin-dir` dev loop.
Plan Task 12's "install by whichever method the Task 2 spike established"
resolves to `--plugin-dir`, so the first koach run needs no install at all.
