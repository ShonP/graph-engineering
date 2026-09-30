#!/usr/bin/env bash
#
# PostToolUse hook, matcher Edit|Write, registered async: lint the one file
# Claude just wrote with the argv a repository opted into in
# .claude/graph-checks.json ("lint": {"argv": [..., "{file}"], "extensions":
# [".py"]}). Nothing is autodetected, and without a lint key nothing but bash
# runs. It informs and never blocks: exit 0 on every path.
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
CONFIG="$PROJECT_DIR/.claude/graph-checks.json"
[ -n "$PROJECT_DIR" ] && [ -f "$CONFIG" ] || exit 0
grep -q '"lint"' "$CONFIG" 2>/dev/null || exit 0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
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
