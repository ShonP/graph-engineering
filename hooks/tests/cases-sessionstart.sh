# shellcheck shell=bash
#
# SessionStart cases for hooks/scripts/print-handoff.sh. Sourced by
# run-tests.sh, which owns every helper and path used here.
#
# The contract under test: the first 40 lines of docs/HANDOFF.md on stdout,
# which is the one place Claude Code reads a hook's plain text as context, and a
# silent exit 0 when the file is absent.

echo
echo "== SessionStart: print-handoff.sh"

run_hook "$HANDOFF" "$FIX/py" "$(session_json startup)"
check "HANDOFF present -> exit 0" 0 "$RC"
row "SessionStart" "docs/HANDOFF.md present" "$RC"
case "$OUT" in
"{"*) check "stdout does not open with a brace" yes "no: $OUT" ;;
*) check "stdout does not open with a brace" yes yes ;;
esac
HANDOFF_LINES="$(printf '%s\n' "$OUT" | grep -c 'of the handoff')"
check "prints no more than 40 lines of the file" ok \
  "$([ "$HANDOFF_LINES" -le 40 ] && [ "$HANDOFF_LINES" -ge 30 ] &&
    echo ok || echo "count=$HANDOFF_LINES")"
case "$OUT" in
*"line 38 of the handoff"*) check "includes the 40th line of the file" yes yes ;;
*) check "includes the 40th line of the file" yes no ;;
esac
case "$OUT" in
*"line 39 of the handoff"*) check "stops before the 41st line of the file" yes no ;;
*) check "stops before the 41st line of the file" yes yes ;;
esac

run_hook "$HANDOFF" "$FIX/bare" "$(session_json startup)"
check "HANDOFF absent -> exit 0" 0 "$RC"
row "SessionStart" "docs/HANDOFF.md absent" "$RC"
check "HANDOFF absent prints nothing" "" "$OUT"

for source_value in resume clear compact fork; do
  run_hook "$HANDOFF" "$FIX/py" "$(session_json "$source_value")"
  check "source=$source_value -> exit 0" 0 "$RC"
  row "SessionStart" "docs/HANDOFF.md present, source=$source_value" "$RC"
done

run_hook_no_project_dir "$HANDOFF" "$(session_json startup)"
check "CLAUDE_PROJECT_DIR unset -> exit 0" 0 "$RC"
row "SessionStart" "CLAUDE_PROJECT_DIR unset" "$RC"
