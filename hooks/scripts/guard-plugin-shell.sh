#!/usr/bin/env bash
#
# PreToolUse(Bash) hook: deny a Bash call that runs one of the plugin's own
# scripts (wait-run, mutate-witness, lane-run, worktree-gc) in a shape Claude
# Code cannot check: a command word that starts with a shell variable, or a
# shell started with a -c script in the plugin script's argv. Claude Code stops
# such a call on a safety prompt even in bypass mode, so the deny reason teaches
# the literal absolute path and a script file passed through bash instead.
# plugin_shell.py owns the decision; the payload fields and the output shape
# (hookSpecificOutput.permissionDecision) are from
# https://code.claude.com/docs/en/hooks. Every caller is gated, main thread
# included, because the prompt stops every caller.
#
# Kill switch, no deploy needed: GRAPH_SHELL_GUARD=off in the hook's
# environment (the owner sets it under `env` in Claude Code settings) disables
# the hook. Unset or `on` means active.
#
# Runs on every Bash call, so the common path stays in bash. Python starts only
# when the raw payload names one of the four scripts and also holds a dollar
# sign or a shell word followed by an option. Always exits 0 and fails open: no
# supported python, bad input or a crash means no decision.

set -u

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
IFS= read -r -d '' HOOK_INPUT || true

[ "${GRAPH_SHELL_GUARD:-on}" = "off" ] && exit 0
case "$HOOK_INPUT" in
  *wait-run.sh*|*mutate-witness.sh*|*lane-run.sh*|*worktree-gc.sh*) ;;
  *) exit 0 ;;
esac
# A shell word (bash, sh, zsh, dash, ksh; never the .sh suffix) followed by
# separators, quotes or JSON escapes and then an option sign.
SHELL_OPTION='(^|[^.])sh([^[:alnum:]]|\\[nrt])*[-+]'
case "$HOOK_INPUT" in
  *'$'*) ;;
  *) [[ "$HOOK_INPUT" =~ $SHELL_OPTION ]] || exit 0 ;;
esac

case "$0" in
  */*) SCRIPT_DIR="${0%/*}" ;;
  *) SCRIPT_DIR=. ;;
esac
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd -P)" || exit 0
# shellcheck source=python-runtime.sh
. "$SCRIPT_DIR/python-runtime.sh"
ge_python_runtime 2>/dev/null || exit 0
printf '%s' "$HOOK_INPUT" | "$GE_PYTHON" "$SCRIPT_DIR/plugin_shell.py" 2>/dev/null
exit 0
