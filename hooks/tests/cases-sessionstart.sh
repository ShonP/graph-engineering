# shellcheck shell=bash
#
# SessionStart cases for hooks/scripts/print-handoff.sh. Sourced by
# run-tests.sh, which owns every helper and path used here.
#
# The contract under test: the first 40 lines of docs/HANDOFF.md on stdout,
# which is the one place Claude Code reads a hook's plain text as context; a
# size warning when that index grows past 150 lines; the three-line reply
# contract when the repo has a graph-engineering profile; nothing at all on
# resume, fork or an --agent session; and exit 0 on every path.

echo
echo "== SessionStart: print-handoff.sh"

CONTRACT_1="graph-engineering reply contract: status and decision replies in at most 5 lines, plain words, echoing the owner's choices."
CONTRACT_2="Give one recommended action, say what you did and what you need, and no internal codes or SHAs unless asked."
CONTRACT_3="Deliverables go to a durable repo path, never only to chat or a scratchpad."
SIZE_WARNING="docs/HANDOFF.md is 200 lines; keep this index under 150 lines and move detail into linked files."

# count_line <exact line> - how many times OUT holds that exact line.
count_line() { printf '%s\n' "$OUT" | grep -cxF -- "$1"; }

# check_contract <label> <expected count per line>
check_contract() {
  check "$1" "$2 $2 $2" \
    "$(count_line "$CONTRACT_1") $(count_line "$CONTRACT_2") $(count_line "$CONTRACT_3")"
}

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
check_contract "startup, no profile -> no contract lines" 0
case "$OUT" in
*"keep this index under 150 lines"*) check "60-line HANDOFF -> no size warning" none shown ;;
*) check "60-line HANDOFF -> no size warning" none none ;;
esac

run_hook "$HANDOFF" "$FIX/bare" "$(session_json startup)"
check "HANDOFF absent -> exit 0" 0 "$RC"
row "SessionStart" "docs/HANDOFF.md absent" "$RC"
check "HANDOFF absent prints nothing" "" "$OUT"

run_hook "$HANDOFF" "$FIX/handoff-long" "$(session_json startup)"
check "200-line HANDOFF and a profile -> exit 0" 0 "$RC"
row "SessionStart" "200-line HANDOFF, profile present" "$RC"
case "$OUT" in
"{"*) check "long: stdout does not open with a brace" yes "no: $OUT" ;;
*) check "long: stdout does not open with a brace" yes yes ;;
esac
check "long: prints the 40th line, not the 41st" "1 0" \
  "$(count_line "line 38 of the long handoff") $(count_line "line 39 of the long handoff")"
check "200-line HANDOFF -> size warning, once" 1 "$(count_line "$SIZE_WARNING")"
check_contract "startup with a profile -> each contract line once" 1

for source_value in clear compact; do
  run_hook "$HANDOFF" "$FIX/handoff-long" "$(session_json "$source_value")"
  check "source=$source_value -> exit 0" 0 "$RC"
  row "SessionStart" "HANDOFF and profile, source=$source_value" "$RC"
  check_contract "source=$source_value -> each contract line once" 1
done

for source_value in resume fork; do
  run_hook "$HANDOFF" "$FIX/handoff-long" "$(session_json "$source_value")"
  check "source=$source_value -> exit 0" 0 "$RC"
  row "SessionStart" "HANDOFF and profile, source=$source_value" "$RC"
  check "source=$source_value prints nothing (bytes)" 0 "${#OUT}"
done

AGENT_JSON="$(session_json startup)"
AGENT_JSON="${AGENT_JSON%\}}, \"agent_type\": \"Explore\"}"
run_hook "$HANDOFF" "$FIX/handoff-long" "$AGENT_JSON"
check "agent_type present -> exit 0" 0 "$RC"
row "SessionStart" "HANDOFF and profile, agent_type present" "$RC"
check "agent_type present prints nothing (bytes)" 0 "${#OUT}"

# Built in the sandbox, not committed: a profile with no HANDOFF, and an empty
# HANDOFF, the two edges of the line count and the contract block.
mkdir -p "$WORK/profile-only/.claude" "$WORK/empty-handoff/docs"
cp "$FIX/handoff-long/.claude/graph-profile.yaml" "$WORK/profile-only/.claude/"
: >"$WORK/empty-handoff/docs/HANDOFF.md"

run_hook "$HANDOFF" "$WORK/profile-only" "$(session_json startup)"
check "profile, no HANDOFF -> exit 0" 0 "$RC"
row "SessionStart" "profile present, HANDOFF absent" "$RC"
check_contract "profile, no HANDOFF -> each contract line once" 1

run_hook "$HANDOFF" "$WORK/empty-handoff" "$(session_json startup)"
check "empty HANDOFF -> exit 0" 0 "$RC"
row "SessionStart" "docs/HANDOFF.md empty" "$RC"
check "empty HANDOFF -> nothing on stderr" "" "$ERR"

run_hook_no_project_dir "$HANDOFF" "$(session_json startup)"
check "CLAUDE_PROJECT_DIR unset -> exit 0" 0 "$RC"
row "SessionStart" "CLAUDE_PROJECT_DIR unset" "$RC"
