# shellcheck shell=bash
#
# Stop cases for hooks/scripts/test-before-stop.sh. Sourced by run-tests.sh,
# which owns every helper and path used here.
#
# The contract under test: exit 2 with the reason on stderr while the tests are
# red, exit 0 once they are green or when no test script applies, and no counter
# of its own for the documented 8-consecutive-blocks cap.

echo
echo "== Stop: test-before-stop.sh"

reset_markers
set_fail py
run_hook "$STOP" "$FIX/py" "$(stop_json false)"
check "uv project, failing test -> exit 2" 2 "$RC"
row "Stop" "uv project, failing test" "$RC"
check_file "uv project ran test" "$FIX/py/RAN_TEST"
case "$ERR" in
*"uv run test"*) check "the reason names the command" yes yes ;;
*) check "the reason names the command" yes "no: $ERR" ;;
esac
case "$ERR" in
*"stop_hook_active=false"*) check "the reason reports stop_hook_active" yes yes ;;
*) check "the reason reports stop_hook_active" yes "no: $ERR" ;;
esac
case "$ERR" in
*"8 consecutive blocks"*) check "the reason states the documented cap" yes yes ;;
*) check "the reason states the documented cap" yes "no: $ERR" ;;
esac
check "a blocking run prints nothing on stdout" "" "$OUT"

reset_markers
set_pass py
run_hook "$STOP" "$FIX/py" "$(stop_json false)"
check "uv project, passing test -> exit 0" 0 "$RC"
row "Stop" "uv project, passing test" "$RC"

reset_markers
set_fail node
run_hook "$STOP" "$FIX/node" "$(stop_json false)"
check "pnpm project, failing test -> exit 2" 2 "$RC"
row "Stop" "pnpm project, failing test" "$RC"
case "$ERR" in
*"pnpm run test"*) check "the reason names the pnpm command" yes yes ;;
*) check "the reason names the pnpm command" yes "no: $ERR" ;;
esac

reset_markers
set_pass node
run_hook "$STOP" "$FIX/node" "$(stop_json false)"
check "pnpm project, passing test -> exit 0" 0 "$RC"
row "Stop" "pnpm project, passing test" "$RC"

reset_markers
set_fail taskfile
run_hook "$STOP" "$FIX/taskfile" "$(stop_json false)"
check "Taskfile project, failing test -> exit 2" 2 "$RC"
row "Stop" "Taskfile project, failing test task" "$RC"
check_file "Taskfile project ran task test" "$FIX/taskfile/RAN_TASK_TEST"
case "$ERR" in
*"task test"*) check "the reason names the task command" yes yes ;;
*) check "the reason names the task command" yes "no: $ERR" ;;
esac

reset_markers
set_pass taskfile
run_hook "$STOP" "$FIX/taskfile" "$(stop_json false)"
check "Taskfile project, passing test -> exit 0" 0 "$RC"
row "Stop" "Taskfile project, passing test task" "$RC"

reset_markers
run_hook "$STOP" "$FIX/bare" "$(stop_json false)"
check "project with no test script -> exit 0" 0 "$RC"
row "Stop" "project with no test script of any convention" "$RC"
check "a project with no test script prints nothing" "" "$OUT$ERR"

reset_markers
set_fail taskfile
if PATH="$SYSTEM_PATH" command -v task >/dev/null 2>&1; then
  skip "Taskfile project with task not on PATH" "a real task is installed here"
else
  SAVED_HOOK_PATH="$HOOK_PATH"
  HOOK_PATH="$SYSTEM_PATH"
  run_hook "$STOP" "$FIX/taskfile" "$(stop_json false)"
  HOOK_PATH="$SAVED_HOOK_PATH"
  check "Taskfile project, task not installed -> exit 0" 0 "$RC"
  row "Stop" "Taskfile project, task binary not installed" "$RC"
  check_no_file "task not installed: nothing ran" "$FIX/taskfile/RAN_TASK_TEST"
fi

reset_markers
set_fail py
run_hook "$STOP" "$FIX/py" "$(stop_json true)"
check "failing test with stop_hook_active true -> exit 2" 2 "$RC"
row "Stop" "uv project, failing test, stop_hook_active=true" "$RC"
case "$ERR" in
*"stop_hook_active=true"*) check "the reason echoes stop_hook_active=true" yes yes ;;
*) check "the reason echoes stop_hook_active=true" yes "no: $ERR" ;;
esac

run_hook "$STOP" "$FIX/bare" 'not json at all'
check "malformed JSON on stdin -> exit 0" 0 "$RC"
row "Stop" "malformed JSON on stdin, project with no test" "$RC"

run_hook_no_project_dir "$STOP" "$(stop_json false)"
check "CLAUDE_PROJECT_DIR unset -> exit 0" 0 "$RC"
row "Stop" "CLAUDE_PROJECT_DIR unset" "$RC"

reset_markers
set_fail py
set_fail node
set_fail taskfile
