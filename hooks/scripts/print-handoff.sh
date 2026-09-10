#!/usr/bin/env bash
#
# SessionStart hook: put the top of the project's handoff note in front of Claude
# at the start of every session. Exits 0 always.
#
# Contract, from the doc fetched 2026-09-10:
#   Hooks reference, "Hooks reference - Claude Code Docs"
#     https://code.claude.com/docs/en/hooks
#     - "SessionStart decision control": "Claude Code adds stdout it treats as
#       plain text to Claude's context", and "a hook that only loads context can
#       print to stdout directly without building JSON". The header line below
#       also keeps the output from starting with `{`, which is what would make
#       Claude Code parse it as JSON instead ("Exit code 0").
#     - "Exit code 2 behavior per event": SessionStart cannot block.
#     - The hook is registered with no matcher, so it fires for every documented
#       source: startup, resume, clear, compact and fork ("SessionStart input").
#
# No file: exit 0 in silence. No commands are run and nothing is written.

set -eu

# Drain stdin, on every path, so Claude Code's writer never sees EPIPE. This hook
# needs no field from the input: it fires for every source.
cat >/dev/null

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] || exit 0
[ -d "$PROJECT_DIR" ] || exit 0

HANDOFF="$PROJECT_DIR/docs/HANDOFF.md"
[ -f "$HANDOFF" ] || exit 0

printf 'docs/HANDOFF.md, first 40 lines (graph-engineering SessionStart hook):\n\n'
head -n 40 -- "$HANDOFF" || exit 0

exit 0
