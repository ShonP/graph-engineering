#!/usr/bin/env bash
#
# PreToolUse(Agent|Task) hook: enforce the repo profile's `policy:` block
# (blocked subagent types, never-models, role tiers) through
# `graph-control.py guard-agent`. Contract: docs/graph-controls.md, "guard-agent".
#
# Cheap no-op unless $CLAUDE_PROJECT_DIR/.claude/graph-profile.yaml has a
# top-level `policy:` line, so repos without a policy never pay for a uv start.
# Always exits 0 and fails open: no uv, a guard error or a nonzero exit means
# no decision, never a blocked dispatch. Hook output shape, from
# https://code.claude.com/docs/en/hooks ("PreToolUse decision control"):
# hookSpecificOutput.permissionDecision plus an optional updatedInput, which
# replaces the whole tool input.
#
# Least privilege: reads the profile, runs the plugin's own pinned helper; the
# helper appends one line to .graph/ledger.md on a policy-override and nothing else.

set -u

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
HOOK_INPUT="$(cat)"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] || exit 0
PROFILE="$PROJECT_DIR/.claude/graph-profile.yaml"
[ -f "$PROFILE" ] || exit 0
grep -q '^policy:' "$PROFILE" 2>/dev/null || exit 0
command -v uv >/dev/null 2>&1 || exit 0

PLUGIN_ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)" || exit 0
DECISION="$(printf '%s' "$HOOK_INPUT" | uv run --quiet --script "$PLUGIN_ROOT/scripts/graph-control.py" \
  guard-agent --profile "$PROFILE" --root "$PROJECT_DIR")" || exit 0
[ -z "$DECISION" ] || printf '%s\n' "$DECISION"
exit 0
