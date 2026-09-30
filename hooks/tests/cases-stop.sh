# shellcheck shell=bash
#
# Stop cases for hooks/scripts/test-before-stop.sh. Sourced by run-tests.sh,
# which owns every helper and path used here.
#
# The contract under test: nothing runs unless .claude/graph-checks.json has a
# test block; a configured failure exits 2 once per prompt (stop_hook_active
# true exits 0 before any python runs); a running background task defers the
# check. Precheck, timeout and worktree binding live in test_configured_checks.py.

echo
echo "== Stop: test-before-stop.sh"

# AC-W1-STOP-01: projects that declare a test script but never opted in. The
# stubs for uv, pnpm and task are on PATH, so autodetection would run them.
for project in py node taskfile; do
  reset_markers
  set_fail "$project"
  clear_config "$FIX/$project"
  run_hook "$STOP" "$FIX/$project" "$(stop_json false)"
  check "$project: failing test script, no graph-checks.json -> exit 0" 0 "$RC"
  row "Stop" "$project project, not configured" "$RC"
  check_no_file "$project: no config, nothing ran" \
    "$FIX/$project/RAN_TEST" "$FIX/$project/RAN_TASK_TEST"
  check "$project: no config prints nothing" "" "$OUT$ERR"
done

# AC-W1-STOP-01 on a host without Python 3.11+ (stock macOS ships 3.9): a repo
# that never opted in stays silent and spawns no interpreter. The trap python3
# is first on PATH, so it stands in for the old system one and marks any call.
reset_markers
saved_path="$HOOK_PATH"
HOOK_PATH="$PY_TRAP:/usr/bin:/bin"
run_hook_python_trap "$STOP" "$FIX/bare" "$(stop_json false)"
HOOK_PATH="$saved_path"
check "no config, no Python 3.11+ on PATH -> exit 0" 0 "$RC"
row "Stop" "no config, no supported python" "$RC"
check "no config, no runtime prints nothing" "" "$OUT$ERR"
check_no_file "no config: decided in bash, no python spawned" "$WORK/RAN_PYTHON"

CONFIGURED_TEST='{"version":1,"test":{"argv":["sh","stub-scripts/test.sh"],"timeout_seconds":30}}'
TESTS_FAILED="Tests failed: sh stub-scripts/test.sh in $FIX/py (exit 1). Fix them, then finish. This check runs once per prompt."

# AC-W1-STOP-02: the first Stop of a prompt blocks on a configured failure.
reset_markers
set_fail py
write_config "$FIX/py" "$CONFIGURED_TEST"
run_hook "$STOP" "$FIX/py" "$(stop_json false)"
check "configured failing test, first stop -> exit 2" 2 "$RC"
row "Stop" "configured failing test, stop_hook_active=false" "$RC"
check_file "configured test ran" "$FIX/py/RAN_TEST"
check "the reason names argv, root and exit" "$TESTS_FAILED" "$(printf '%s\n' "$ERR" | head -1)"
case "$ERR" in
*"fixture: 1 failed, 2 passed"*) check "the reason carries the output tail" yes yes ;;
*) check "the reason carries the output tail" yes "no: $ERR" ;;
esac
check "a blocking run prints nothing on stdout" "" "$OUT"

# AC-W1-STOP-02: every continuation of the same prompt exits 0 in bash.
reset_markers
run_hook_python_trap "$STOP" "$FIX/py" "$(stop_json true)"
check "configured failing test, stop_hook_active=true -> exit 0" 0 "$RC"
row "Stop" "configured failing test, stop_hook_active=true" "$RC"
check_no_file "continuation: the test did not run again" "$FIX/py/RAN_TEST"
check_no_file "continuation: no python spawned" "$WORK/RAN_PYTHON"

reset_markers
run_hook_python_trap "$STOP" "$FIX/py" '{"hook_event_name":"Stop","stop_hook_active" :  true}'
check "stop_hook_active true with spacing -> exit 0" 0 "$RC"
check_no_file "spaced flag: nothing ran" "$FIX/py/RAN_TEST" "$WORK/RAN_PYTHON"

# AC-W1-STOP-03: a running background task defers the check; a finished one does not.
reset_markers
run_hook "$STOP" "$FIX/py" "$(stop_json false background=running)"
check "background task running -> exit 0" 0 "$RC"
row "Stop" "configured failing test, background task running" "$RC"
check_no_file "background running: the test did not run" "$FIX/py/RAN_TEST"

reset_markers
run_hook "$STOP" "$FIX/py" "$(stop_json false background=completed prompt_id=p-1)"
check "background task completed -> exit 2" 2 "$RC"
row "Stop" "configured failing test, background task completed" "$RC"
check_file "background completed: the test ran" "$FIX/py/RAN_TEST"

reset_markers
set_pass py
run_hook "$STOP" "$FIX/py" "$(stop_json false)"
check "configured passing test -> exit 0" 0 "$RC"
row "Stop" "configured passing test" "$RC"
check_file "configured passing test ran" "$FIX/py/RAN_TEST"
check "a passing run prints nothing" "" "$OUT$ERR"

reset_markers
set_fail py
write_config "$FIX/py" '{"version":1,"lint":{"argv":["sh","stub-scripts/lint.sh","{file}"],"extensions":[".py"]}}'
run_hook "$STOP" "$FIX/py" "$(stop_json false)"
check "config with no test block -> exit 0" 0 "$RC"
row "Stop" "config with a lint block only" "$RC"
check_no_file "no test block: nothing ran" "$FIX/py/RAN_TEST"
check "no test block prints nothing" "" "$OUT$ERR"

reset_markers
write_config "$FIX/py" '{"version":1,"test":{"argv":["sh","stub-scripts/test.sh"],"shell":true}}'
run_hook "$STOP" "$FIX/py" "$(stop_json false)"
check "invalid config -> exit 2, a broken opt-in is visible" 2 "$RC"
row "Stop" "invalid graph-checks.json" "$RC"
check_no_file "invalid config: nothing ran" "$FIX/py/RAN_TEST"
case "$ERR" in
*"graph-checks.json"*"shell"*) check "the reason names the file and the bad key" yes yes ;;
*) check "the reason names the file and the bad key" yes "no: $ERR" ;;
esac
clear_config "$FIX/py"

run_hook "$STOP" "$FIX/bare" 'not json at all'
check "malformed JSON on stdin -> exit 0" 0 "$RC"
row "Stop" "malformed JSON on stdin, not configured" "$RC"

run_hook_no_project_dir "$STOP" "$(stop_json false)"
check "CLAUDE_PROJECT_DIR unset -> exit 0" 0 "$RC"
row "Stop" "CLAUDE_PROJECT_DIR unset" "$RC"

reset_markers
set_fail py
set_fail node
set_fail taskfile
