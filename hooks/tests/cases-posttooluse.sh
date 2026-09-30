# shellcheck shell=bash
#
# PostToolUse cases for hooks/scripts/lint-touched-file.sh. Sourced by
# run-tests.sh, which owns every helper and path used here.
#
# The contract under test: exit 0 on every path; nothing runs, not even python,
# unless graph-checks.json has a lint key; the configured argv gets the touched
# file relative to the root as one element, only for a listed extension and a
# regular file strictly inside the root; findings come back as
# hookSpecificOutput.additionalContext.

echo
echo "== PostToolUse: lint-touched-file.sh"

# AC-W1-LINT-01: projects that declare lint scripts but never opted in.
for project in py node; do
  reset_markers
  set_fail "$project"
  clear_config "$FIX/$project"
  touched="$(find "$FIX/$project/src" -name 'touched.*' | head -1)"
  run_hook_python_trap "$LINT" "$FIX/$project" "$(post_json "$touched")"
  check "$project: lint script, no graph-checks.json -> exit 0" 0 "$RC"
  row "PostToolUse" "$project project, not configured" "$RC"
  check "$project: no config prints nothing" "" "$OUT"
  check_no_file "$project: no config, no python and no lint" \
    "$WORK/RAN_PYTHON" "$FIX/$project/RAN_LINT" "$FIX/$project/RAN_TYPECHECK"
done

reset_markers
write_config "$FIX/py" '{"version":1,"test":{"argv":["sh","stub-scripts/test.sh"]}}'
run_hook_python_trap "$LINT" "$FIX/py" "$(post_json "$FIX/py/src/touched.py")"
check "config with no lint key -> exit 0" 0 "$RC"
row "PostToolUse" "config with a test block only" "$RC"
check_no_file "no lint key: no python and no lint" "$WORK/RAN_PYTHON" "$FIX/py/RAN_LINT"

PY_LINT='{"version":1,"lint":{"argv":["sh","stub-scripts/lint.sh","{file}"],"extensions":[".py"],"timeout_seconds":30}}'
write_config "$FIX/py" "$PY_LINT"

# AC-W1-LINT-03: a failing lint is information, returned as context.
reset_markers
set_fail py
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py/src/touched.py")"
check "configured failing lint -> exit 0" 0 "$RC"
row "PostToolUse" "configured lint reports problems" "$RC"
check "the linter got the path relative to the root" "src/touched.py" "$(cat "$FIX/py/RAN_LINT" 2>/dev/null)"
python3 -c '
import json
import sys

data = json.load(sys.stdin)
block = data["hookSpecificOutput"]
assert set(data) == {"hookSpecificOutput"}, data
assert block["hookEventName"] == "PostToolUse", block
text = block["additionalContext"]
assert text.startswith("Lint on src/touched.py reported problems (exit 1). This is information, not a block."), text
assert "fixture lint: E501 line too long" in text, text
' <<<"$OUT" >/dev/null 2>&1
check "stdout is PostToolUse context beginning 'Lint on'" 0 $?

reset_markers
set_pass py
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py/src/touched.py" tool_name=Write)"
check "configured clean lint (Write) -> exit 0" 0 "$RC"
row "PostToolUse" "configured lint clean" "$RC"
check_file "a Write is linted too" "$FIX/py/RAN_LINT"
check "a clean run prints nothing" "" "$OUT"
set_fail py

# AC-W1-LINT-02: only listed extensions; spaces and non-ASCII stay one element.
reset_markers
printf 'fixture\n' >"$FIX/py/NOTES.md"
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py/NOTES.md")"
check "unlisted extension -> exit 0" 0 "$RC"
row "PostToolUse" "configured for .py, a .md edited" "$RC"
check_no_file "unlisted extension: nothing ran" "$FIX/py/RAN_LINT"
check "unlisted extension prints nothing" "" "$OUT"

reset_markers
mkdir -p "$FIX/py/src/a b"
printf 'x = 1\n' >"$FIX/py/src/a b/ü.py"
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py/src/a b/ü.py")"
check "path with a space and non-ASCII -> exit 0" 0 "$RC"
row "PostToolUse" "path with a space and non-ASCII" "$RC"
check "the path reached the linter as one argv element" "src/a b/ü.py" "$(cat "$FIX/py/RAN_LINT" 2>/dev/null)"

reset_markers
write_config "$FIX/py" '{"version":1,"lint":{"argv":["graph-absent-linter","{file}"],"extensions":[".py"]}}'
run_hook "$LINT" "$FIX/py" "$(post_json "$FIX/py/src/touched.py")"
check "configured lint runner missing -> exit 0" 0 "$RC"
row "PostToolUse" "configured lint runner not installed" "$RC"
case "$OUT" in
*'"additionalContext": "lint skipped: graph-absent-linter not found in '*) check "a missing runner says lint skipped" yes yes ;;
*) check "a missing runner says lint skipped" yes "no: $OUT" ;;
esac
# AC-W1-LINT-04: the bound. .ts is listed so the extension filter is not what
# stops the outside file, and foreign projects carry their own opt-in bait.
write_config "$FIX/py" '{"version":1,"lint":{"argv":["sh","stub-scripts/lint.sh","{file}"],"extensions":[".py",".ts"]}}'
write_config "$FIX/outside" '{"version":1,"lint":{"argv":["sh","ran.sh","OUTSIDE_LINT_RAN","{file}"],"extensions":[".ts"]}}'
write_config "$FIX/py-evil" '{"version":1,"lint":{"argv":["sh","ran.sh","EVIL_LINT_RAN","{file}"],"extensions":[".py"]}}'
for bound_case in \
  "file outside CLAUDE_PROJECT_DIR|$FIX/outside/src/touched.ts" \
  "sibling sharing the project-dir prefix|$FIX/py-evil/src/touched.py" \
  "file_path equal to CLAUDE_PROJECT_DIR|$FIX/py" \
  "file_path that is a directory|$FIX/py/src" \
  "directory named like a listed file|$FIX/py/src/dir.py" \
  "file_path that does not exist|$FIX/py/src/ghost.py" \
  "symlink inside the root to a file outside|$FIX/py/src/link.py" \
  "relative file_path|src/touched.py"; do
  label="${bound_case%%|*}"
  mkdir -p "$FIX/py/src/dir.py"
  ln -sf "$FIX/py-evil/src/touched.py" "$FIX/py/src/link.py"
  reset_markers
  run_hook "$LINT" "$FIX/py" "$(post_json "${bound_case#*|}")"
  check "$label -> exit 0" 0 "$RC"
  row "PostToolUse" "$label" "$RC"
  check_no_file "$label: nothing ran" "$FIX/py/RAN_LINT" \
    "$FIX/outside/OUTSIDE_LINT_RAN" "$FIX/py-evil/EVIL_LINT_RAN"
  check "$label: prints nothing" "" "$OUT"
done
clear_config "$FIX/outside"
clear_config "$FIX/py-evil"

reset_markers
run_hook "$LINT" "$FIX/py" "$(event_json PostToolUse)"
check "input with no file_path -> exit 0" 0 "$RC"
row "PostToolUse" "input with no tool_input.file_path" "$RC"
check_no_file "no file_path: nothing ran" "$FIX/py/RAN_LINT"

run_hook "$LINT" "$FIX/py" 'not json at all'
check "malformed JSON on stdin -> exit 0" 0 "$RC"
row "PostToolUse" "malformed JSON on stdin" "$RC"

run_hook_no_project_dir "$LINT" "$(post_json "$FIX/py/src/touched.py")"
check "CLAUDE_PROJECT_DIR unset -> exit 0" 0 "$RC"
row "PostToolUse" "CLAUDE_PROJECT_DIR unset" "$RC"

reset_markers
clear_config "$FIX/py"
rm -rf "$FIX/py/src/a b" "$FIX/py/src/dir.py" "$FIX/py/src/link.py" "$FIX/py/NOTES.md"
set_fail py
set_fail node
