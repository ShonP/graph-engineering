#!/usr/bin/env bash
#
# PreToolUse hook on Bash: turn a small set of destructive commands into a
# permission `ask` that carries the evidence the owner needs, and cost nothing
# on every other command. It never denies, never allows, never writes a file,
# and exits 0 on every path.
#
# Contract, from the docs fetched 2026-09-30:
#   Hooks reference, https://code.claude.com/docs/en/hooks
#     - "PreToolUse decision control": permissionDecision "ask" prompts the user;
#       permissionDecisionReason is shown to the user, not to Claude.
#   Spike e (Claude Code 2.1.285): a handler's `if` rule checks each subcommand
#   of `&&`, `;` and `|`, strips env-var prefixes, and still fires on `$()`,
#   backticks and `$VAR`. So `if` narrows the calls but is not the check: the
#   evidence script re-parses tool_input.command itself.
#
# Fast path: a pure-bash `case` on the raw input. No match means exit 0 with no
# output and no process spawned. The words are matched apart, not as `git push`,
# because git and docker take global options before the subcommand
# (`git -C <worktree> push -f`, `docker -H <host> volume prune`); for the same
# reason the git handler's `if` is `Bash(git *)`. `$(</dev/stdin)` drains stdin
# without exec'ing cat (measured 2026-09-30, bash 3.2: 2.9 ms small, 4.9 ms on a
# 60 KB payload, against 16 ms for `read -d ''`, which reads a pipe a byte at a
# time).
#
# Slow path: destructive_evidence.py, stdlib only, run with the interpreter
# python-runtime.sh selects. No interpreter means fail-open: exit 0, no prompt.

input="$(</dev/stdin)"
case "$input" in
  *git*push* | *git*remote* | *'rm '* | *docker*volume* | *docker*system*) ;;
  *) exit 0 ;;
esac

src="${BASH_SOURCE[0]}"
case "$src" in
  */*) here="${src%/*}" ;;
  *) here=. ;;
esac
here="$(cd "$here" && pwd -P)" || exit 0

# shellcheck source=python-runtime.sh
. "$here/python-runtime.sh" || exit 0
ge_python_runtime 2>/dev/null || exit 0
printf '%s' "$input" | "$GE_PYTHON" "$here/destructive_evidence.py"
exit 0
