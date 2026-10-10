---
description: Check this repo's graph-engineering setup and report what is broken with its fix - profile schema and removed keys, runtime, graph-checks.json, policy tiers, gate risk ids, routing skills, .graph ignore, the UX evidence store (commands resolve, media ignored), and whether this session runs the installed plugin version. Read-only.
---

# /graph-doctor - is this repo's setup healthy

Read-only. It runs one helper that reads files and changes nothing, so anyone
may run it at any time. The SessionStart hook runs the same helper with
`--quick` and caches a clean result.

## Steps

1. Run the helper against the repo root (a linked worktree's own root; outside
   git, the current directory):

   ```bash
   uv run <plugin-root>/scripts/graph-control.py doctor --root "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   ```

   It prints `{"status": "PASS", "findings": [...]}`. Each finding has `level`
   (`error`, `warn` or `info`), `id`, `message` and `fix`, errors first.
   `"status": "BLOCKED"` means the helper itself failed: show its `reason` in
   one line and stop.

2. Report in at most 10 lines: one line per `error`, then per `warn`, as
   `<level>: <message> - fix: <fix>`. With more than 9, show the first 9 and end
   with `and <n> more`. Leave `info` findings out unless nothing else was found.
   No `error` or `warn` findings: say in one line that the setup is healthy.

3. Apply no fix. Profile rewrites (`/graph-init`, `/graph-init --upgrade`) are
   the owner's to run; a restart is the owner's to do.
