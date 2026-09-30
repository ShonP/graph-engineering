#!/usr/bin/env bash
#
# PostToolUse hook, matcher Edit|Write, registered async: lint the one file
# Claude just wrote with the argv a repository opted into in
# .claude/graph-checks.json ("lint": {"argv": [..., "{file}"], "extensions":
# [".py"]}). Nothing is autodetected. The config is looked up where it can
# apply: the edited file's directory and its ancestors (opt-in.sh), so a nested
# repo in a multi-repo workspace and a linked worktree use their own file. With
# no lint key on that path nothing but bash runs. It informs and never blocks:
# exit 0 on every path.
#
# Contract (Claude Code 2.1.285, spiked 2026-09-30; hooks reference
# https://code.claude.com/docs/en/hooks): an async hook's exit code is ignored;
# stdout JSON hookSpecificOutput.additionalContext reaches Claude on the next
# turn. configured_check.py enforces the bound (a regular file strictly inside
# the root, a listed extension), passes the path relative to the root as one
# argv element with no shell, and owns every message.

set -u

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
HOOK_INPUT="$(cat)"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] || exit 0

case "$0" in
  */*) SCRIPT_DIR="${0%/*}" ;;
  *) SCRIPT_DIR=. ;;
esac
# shellcheck source=opt-in.sh
. "$SCRIPT_DIR/opt-in.sh" || exit 0
ge_input_path "$HOOK_INPUT" file_path
case $? in
  0) ge_opted_in lint "${GE_INPUT_PATH%/*}" || exit 0 ;;
  2) ;; # an escaped path: Python decodes it and decides
  *) exit 0 ;;
esac

SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd -P)" || exit 0
# shellcheck source=python-runtime.sh
. "$SCRIPT_DIR/python-runtime.sh"
ge_python_runtime 2>/dev/null || exit 0

ROOT="$(HOOK_INPUT="$HOOK_INPUT" CLAUDE_PROJECT_DIR="$PROJECT_DIR" \
  "$GE_PYTHON" "$SCRIPT_DIR/project_root.py" --touched 2>/dev/null)" || exit 0
FILE="$(HOOK_INPUT="$HOOK_INPUT" "$GE_PYTHON" -c '
import json, os
try:
    path = json.loads(os.environ["HOOK_INPUT"])["tool_input"]["file_path"]
except Exception:
    path = None
print(path if isinstance(path, str) else "")
' 2>/dev/null)" || exit 0
[ -n "$FILE" ] || exit 0

"$GE_PYTHON" "$SCRIPT_DIR/configured_check.py" lint "$ROOT" "$FILE" 2>/dev/null
exit 0
