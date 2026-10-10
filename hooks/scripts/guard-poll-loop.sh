#!/usr/bin/env bash
#
# PreToolUse(Bash) hook: deny a shell loop that sleeps (until, while or for with
# a sleep in its condition or body) when the call comes from a roster
# subagent. Waiting belongs to hooks/scripts/wait-run.sh. poll_loop.py owns the
# decision; the payload fields it reads (agent_id, agent_type) and the output
# shape (hookSpecificOutput.permissionDecision) are from
# https://code.claude.com/docs/en/hooks. The main thread is never blocked.
#
# Kill switch, no deploy needed: GRAPH_POLL_GUARD=off in the hook's environment
# (the owner sets it under `env` in Claude Code settings) disables the hook.
# Unset or `on` means active.
#
# Runs on every Bash call, so the common path stays in bash: input without the
# word sleep exits before any interpreter starts. Always exits 0 and fails
# open: no supported python, bad input or a crash means no decision.

set -u

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
IFS= read -r -d '' HOOK_INPUT || true

[ "${GRAPH_POLL_GUARD:-on}" = "off" ] && exit 0
case "$HOOK_INPUT" in
  *sleep*) ;;
  *) exit 0 ;;
esac

case "$0" in
  */*) SCRIPT_DIR="${0%/*}" ;;
  *) SCRIPT_DIR=. ;;
esac
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd -P)" || exit 0
# shellcheck source=python-runtime.sh
. "$SCRIPT_DIR/python-runtime.sh"
ge_python_runtime 2>/dev/null || exit 0
printf '%s' "$HOOK_INPUT" | "$GE_PYTHON" "$SCRIPT_DIR/poll_loop.py" 2>/dev/null
exit 0
