# shellcheck shell=bash
#
# PostToolUse cases for hooks/scripts/lint-touched-file.sh. Sourced by
# run-tests.sh, which owns every helper and path used here.
#
# The contract under test: exit 0 on every path, findings returned as
# hookSpecificOutput.additionalContext, and no command run for a file outside
# CLAUDE_PROJECT_DIR.

echo
echo "== PostToolUse: lint-touched-file.sh"

reset_markers
set_fail py
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py/src/touched.py")"
check "uv project, failing lint -> exit 0" 0 "$RC"
row "PostToolUse" "uv project, lint+typecheck fail" "$RC"
check_file "uv project ran lint" "$FIX/py/RAN_LINT"
check_file "uv project ran typecheck" "$FIX/py/RAN_TYPECHECK"
check "uv lint got the touched file as its only argument" \
  "$FIX/py/src/touched.py" "$(cat "$FIX/py/RAN_LINT" 2>/dev/null)"
case "$OUT" in
*E501*) check "the failing lint text reaches Claude" yes yes ;;
*) check "the failing lint text reaches Claude" yes "no: $OUT" ;;
esac
python3 -c '
import json
import sys

data = json.load(sys.stdin)
block = data["hookSpecificOutput"]
assert block["hookEventName"] == "PostToolUse", block
assert block["additionalContext"].strip(), block
assert set(data) <= {"hookSpecificOutput", "systemMessage"}, data
' <<<"$OUT" >/dev/null 2>&1
JSON_SHAPE_RC=$?
check "stdout is a PostToolUse additionalContext object" 0 "$JSON_SHAPE_RC"

reset_markers
set_pass py
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py/src/touched.py")"
check "uv project, clean lint -> exit 0" 0 "$RC"
row "PostToolUse" "uv project, lint+typecheck clean" "$RC"
check "a clean run prints nothing" "" "$OUT"

reset_markers
set_fail node
run_hook "$LINT" "$FIX/node" "$(post_json "$FIX/node/src/touched.ts")"
check "pnpm project, failing lint -> exit 0" 0 "$RC"
row "PostToolUse" "pnpm project, lint+typecheck fail" "$RC"
check_file "pnpm project ran lint" "$FIX/node/RAN_LINT"
check "pnpm lint got the touched file only, with no bare --" \
  "$FIX/node/src/touched.ts" "$(cat "$FIX/node/RAN_LINT" 2>/dev/null)"
case "$OUT" in
*no-unused-vars*) check "the failing pnpm lint text reaches Claude" yes yes ;;
*) check "the failing pnpm lint text reaches Claude" yes "no: $OUT" ;;
esac

reset_markers
set_pass node
run_hook "$LINT" "$FIX/node" "$(post_json "$FIX/node/src/touched.ts")"
check "pnpm project, clean lint -> exit 0" 0 "$RC"
row "PostToolUse" "pnpm project, lint+typecheck clean" "$RC"

reset_markers
run_hook "$LINT" "$FIX/taskfile" "$(post_json "$FIX/taskfile/src/touched.sh")"
check "Taskfile project has no lint shape -> exit 0" 0 "$RC"
row "PostToolUse" "Taskfile project (no lint/typecheck shape)" "$RC"
check "Taskfile project prints nothing" "" "$OUT"

reset_markers
run_hook "$LINT" "$FIX/bare" "$(post_json "$FIX/bare/src/touched.py")"
check "project with no scripts -> exit 0" 0 "$RC"
row "PostToolUse" "project with no script of any convention" "$RC"
check "a project with no scripts prints nothing" "" "$OUT"

reset_markers
set_fail py
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/outside/src/touched.ts")"
check "file_path outside CLAUDE_PROJECT_DIR -> exit 0" 0 "$RC"
row "PostToolUse" "file_path outside CLAUDE_PROJECT_DIR" "$RC"
check_no_file "outside path: nothing ran in the foreign project" \
  "$FIX/outside/OUTSIDE_LINT_RAN" "$FIX/outside/OUTSIDE_TYPECHECK_RAN"
check_no_file "outside path: nothing ran in the session project" \
  "$FIX/py/RAN_LINT" "$FIX/py/RAN_TYPECHECK"

reset_markers
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py-evil/src/touched.py")"
check "sibling sharing the project-dir prefix -> exit 0" 0 "$RC"
row "PostToolUse" "sibling path sharing the project-dir prefix" "$RC"
check_no_file "prefix sibling: nothing ran" \
  "$FIX/py-evil/EVIL_LINT_RAN" "$FIX/py-evil/EVIL_TYPECHECK_RAN"

reset_markers
run_hook "$LINT" "$FIX/py" "$(event_json PostToolUse)"
check "input with no file_path -> exit 0" 0 "$RC"
row "PostToolUse" "input with no tool_input.file_path" "$RC"

run_hook "$LINT" "$FIX/py" 'not json at all'
check "malformed JSON on stdin -> exit 0" 0 "$RC"
row "PostToolUse" "malformed JSON on stdin" "$RC"

run_hook "$LINT" "$FIX/py" "$(post_json "relative/path.py")"
check "a relative file_path -> exit 0" 0 "$RC"
row "PostToolUse" "relative tool_input.file_path" "$RC"

run_hook_no_project_dir "$LINT" "$(post_json "$FIX/py/src/touched.py")"
check "CLAUDE_PROJECT_DIR unset -> exit 0" 0 "$RC"
row "PostToolUse" "CLAUDE_PROJECT_DIR unset" "$RC"

reset_markers
set_fail py
set_fail node
