#!/usr/bin/env bash
# Capture the text the Stop and PostToolUse hooks show Claude, as evidence.
# Usage: capture.sh <plugin-root> > before.txt   (run once on the base commit,
# once on the change). Synthetic fixture: every file below is invented.
set -uo pipefail
HOOKS="$1/hooks/scripts"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-ux-capture.XXXXXX")" && WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/repo/.claude" "$WORK/repo/src"
cd "$WORK/repo" || exit 1
git init -q .
printf 'import os\n' > src/app.py
printf 'echo "FAILED tests/test_math.py::test_add - assert 3 == 4"\necho "1 failed, 12 passed"\nexit 1\n' > check.sh
# shellcheck disable=SC2016 # $1 belongs to the fixture linter, not this script
printf 'echo "$1:1:8: F401 [*] os imported but unused"\nexit 1\n' > lint.sh
printf '{"name":"fixture","scripts":{"test":"sh check.sh","lint":"sh lint.sh"}}\n' > package.json
config() { printf '%s\n' "$1" > .claude/graph-checks.json; }
show() { # show <title> <script> <json>
  local out err rc
  out="$(printf '%s' "$3" | env CLAUDE_PROJECT_DIR="$WORK/repo" bash "$2" 2>"$WORK/err")"; rc=$?
  err="$(cat "$WORK/err")"
  printf '### %s\nexit: %s\nstderr:\n%s\nstdout:\n%s\n\n' "$1" "$rc" "${err//$WORK/<tmp>}" "${out//$WORK/<tmp>}"
}
stop='{"hook_event_name":"Stop","cwd":"'"$WORK/repo"'","stop_hook_active":false,"background_tasks":[]}'
again='{"hook_event_name":"Stop","cwd":"'"$WORK/repo"'","stop_hook_active":true,"background_tasks":[]}'
edit='{"hook_event_name":"PostToolUse","cwd":"'"$WORK/repo"'","tool_name":"Edit","tool_input":{"file_path":"'"$WORK/repo/src/app.py"'"}}'
config '{"version":1,"test":{"argv":["sh","check.sh"],"timeout_seconds":30}}'
show "Stop, configured test fails, first stop of the prompt" "$HOOKS/test-before-stop.sh" "$stop"
show "Stop, configured test fails, continuation (stop_hook_active=true)" "$HOOKS/test-before-stop.sh" "$again"
config '{"version":1,"test":{"argv":["sleep","5"],"timeout_seconds":1}}'
show "Stop, configured test exceeds its timeout" "$HOOKS/test-before-stop.sh" "$stop"
rm -f .claude/graph-checks.json
show "Stop, no graph-checks.json, package.json test script fails" "$HOOKS/test-before-stop.sh" "$stop"
config '{"version":1,"lint":{"argv":["sh","lint.sh","{file}"],"extensions":[".py"]}}'
show "PostToolUse, lint reports a problem" "$HOOKS/lint-touched-file.sh" "$edit"
config '{"version":1,"lint":{"argv":["graph-absent-linter","{file}"],"extensions":[".py"]}}'
show "PostToolUse, lint runner not installed" "$HOOKS/lint-touched-file.sh" "$edit"
