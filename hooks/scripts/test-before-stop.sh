#!/usr/bin/env bash
#
# Stop hook: run the tests a repository opted into in .claude/graph-checks.json,
# at most once per user prompt. No config, or a config with no test block:
# exit 0 in silence. Nothing is autodetected.
#
# Contract (Claude Code 2.1.285, spiked 2026-09-30; hooks reference
# https://code.claude.com/docs/en/hooks). Registered with asyncRewake: exit 2
# wakes Claude with stderr, exit 0 and 1 are silent.
#   - stop_hook_active is false only on the first Stop of a prompt and true on
#     every continuation, including the re-fire after a wake. Exiting 0 on true,
#     in bash before any python, is what bounds the loop to one run per prompt.
#   - background_tasks entries with status "running" mean work is still in
#     flight; the tree is not final, so the check waits for a later Stop.
#   - The input cwd is the tree being worked on; project_root.py binds a linked
#     worktree of $CLAUDE_PROJECT_DIR to itself.
# configured_check.py owns the run, the timeout ("not verified", exit 0) and
# every message.

set -eu

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
HOOK_INPUT="$(cat)"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] && [ -d "$PROJECT_DIR" ] || exit 0

ACTIVE='"stop_hook_active"[[:space:]]*:[[:space:]]*true'
[[ $HOOK_INPUT =~ $ACTIVE ]] && exit 0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck source=python-runtime.sh
. "$SCRIPT_DIR/python-runtime.sh"
ge_python_runtime || exit 2

HOOK_INPUT="$HOOK_INPUT" "$GE_PYTHON" -c '
import json, os, sys
try:
    tasks = json.loads(os.environ["HOOK_INPUT"]).get("background_tasks")
except Exception:
    sys.exit(1)
live = isinstance(tasks, list) and any(isinstance(t, dict) and t.get("status") == "running" for t in tasks)
sys.exit(0 if live else 1)
' 2>/dev/null && exit 0

root() { HOOK_INPUT="$HOOK_INPUT" CLAUDE_PROJECT_DIR="$PROJECT_DIR" "$GE_PYTHON" "$SCRIPT_DIR/project_root.py"; }
# A cwd in an unrelated repository is an error only for a project that opted in.
if [ -f "$PROJECT_DIR/.claude/graph-checks.json" ]; then
  ROOT="$(root)" || exit 2
else
  ROOT="$(root 2>/dev/null)" || exit 0
fi

STATUS=0
"$GE_PYTHON" "$SCRIPT_DIR/configured_check.py" test "$ROOT" || STATUS=$?
[ "$STATUS" -eq 77 ] && exit 0
exit "$STATUS"
