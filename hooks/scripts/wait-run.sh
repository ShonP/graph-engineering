#!/usr/bin/env bash
#
# Bounded blocking wait for a command longer than one tool call. Not a hook:
# agents call it by path. A bare `sleep N` is blocked by the harness, and a
# foreground subagent's background jobs die when it ends its turn, so this
# starts the command detached and blocks for at most S seconds per call.
#
#   wait-run.sh --log <absolute path> [--max-block S] [--full [--reason TEXT]] [-- <argv...>]
#
# --full marks a full-suite start: each GRAPH_RUN_ID gets two free full runs,
# and a later one without --reason is refused with exit 2 before it starts.
#
# With argv: start it (refused with exit 2 while a job for the log still runs),
# then wait. Without argv: attach to the job and wait. S defaults to 270, so a
# return lands inside the 5-minute worker cache, and is clamped to 590. One line
# out: `wait-run: exit=<n>|running state=complete|partial elapsed=<s>s
# max_block=<S>s log=<path>`, plus the log's last 20 lines on a nonzero exit.
# Exit: the job's code when complete, 75 when still running, 2 on an error.
# Make the Bash call's own timeout longer than S. wait_run.py owns the logic.

set -u

case "$0" in
  */*) SCRIPT_DIR="${0%/*}" ;;
  *) SCRIPT_DIR=. ;;
esac
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd -P)" || exit 2
# shellcheck source=python-runtime.sh
. "$SCRIPT_DIR/python-runtime.sh"
ge_python_runtime || exit 2
exec "$GE_PYTHON" "$SCRIPT_DIR/wait_run.py" "$@"
