#!/usr/bin/env bash
#
# Regression test for the three plugin hooks. Runs from any working directory
# and needs nothing but bash, python3 and the fixtures beside this file: uv,
# the package managers and task are all stubbed under fixtures/stubs.
#
# Every case invokes a hook script the way Claude Code does: the event's
# documented JSON input on stdin, CLAUDE_PROJECT_DIR in the environment, from a
# working directory unrelated to the project.
#
#   bash hooks/tests/run-tests.sh
#
# Exits non-zero when any case fails. Writes only inside a mktemp directory,
# which it removes on the way out.
#
# No `set -e` here: a failing case must be recorded and the run must continue.
# shellcheck source-path=SCRIPTDIR
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
HOOKS_DIR="$(cd "$TESTS_DIR/.." && pwd -P)"
LINT="$HOOKS_DIR/scripts/lint-touched-file.sh"
STOP="$HOOKS_DIR/scripts/test-before-stop.sh"
HANDOFF="$HOOKS_DIR/scripts/print-handoff.sh"

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required to run these tests" >&2
  exit 1
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-hook-tests.XXXXXX")" || exit 1
# Canonicalise: on macOS $TMPDIR is a symlink, and the hooks canonicalise the
# paths they are handed, so the fixture paths have to match what they resolve to.
WORK="$(cd "$WORK" && pwd -P)" || exit 1
trap 'rm -rf "$WORK"' EXIT INT TERM
cp -R "$TESTS_DIR/fixtures/." "$WORK/" || exit 1

# The stubs are committed under names that say what they are, and are installed
# into the sandbox under the names the hooks look for on PATH.
FIX="$WORK"
STUB_BIN="$WORK/bin"
mkdir -p "$STUB_BIN"
for tool in uv pnpm task; do
  cp "$WORK/stubs/stub-$tool.sh" "$STUB_BIN/$tool" || exit 1
  chmod +x "$STUB_BIN/$tool"
done
rm -rf "$WORK/stubs"

SYSTEM_PATH="$PATH"
HOOK_PATH="$STUB_BIN:$PATH"

pass=0
fail=0
skipped=0
ROWS=()

check() { # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then
    printf 'ok   %-58s %s\n' "$1" "$3"
    pass=$((pass + 1))
  else
    printf 'FAIL %-58s expected [%s] got [%s]\n' "$1" "$2" "$3"
    fail=$((fail + 1))
  fi
}

check_file() { # check_file <label> <path> - the marker must be there
  if [ -f "$2" ]; then
    check "$1" ran ran
  else
    check "$1" ran "did not run"
  fi
}

check_no_file() { # check_no_file <label> <path>... - no marker may be there
  local label="$1"
  local found=""
  shift
  for candidate in "$@"; do
    if [ -e "$candidate" ]; then
      found="$found $(basename "$candidate")"
    fi
  done
  if [ -n "$found" ]; then
    check "$label" "nothing ran" "ran:$found"
  else
    check "$label" "nothing ran" "nothing ran"
  fi
}

skip() { # skip <label> <reason>
  printf 'skip %-58s %s\n' "$1" "$2"
  skipped=$((skipped + 1))
}

row() { ROWS+=("$1|$2|$3"); }

reset_markers() {
  find "$WORK" \( -name 'RAN_*' -o -name 'OUTSIDE_*' -o -name 'EVIL_*' \
    -o -name 'ESCAPED_*' -o -name 'INNER_*' \) |
    while read -r marker; do rm -f "$marker"; done
}

set_pass() { touch "$FIX/$1/PASS"; }
set_fail() { rm -f "$FIX/$1/PASS"; }

# run_hook <script> <project_dir> <json> - sets RC, OUT and ERR.
run_hook() {
  local script="$1" proj="$2" json="$3"
  local outf errf
  outf="$WORK/.stdout"
  errf="$WORK/.stderr"
  (
    cd / || exit 99
    printf '%s' "$json" |
      env PATH="$HOOK_PATH" CLAUDE_PROJECT_DIR="$proj" "$script"
  ) >"$outf" 2>"$errf"
  RC=$?
  OUT="$(cat "$outf")"
  ERR="$(cat "$errf")"
  rm -f "$outf" "$errf"
}

# run_hook_no_project_dir <script> <json> - sets RC only.
run_hook_no_project_dir() {
  (
    cd / || exit 99
    printf '%s' "$2" | env -u CLAUDE_PROJECT_DIR PATH="$HOOK_PATH" "$1"
  ) >/dev/null 2>&1
  RC=$?
}

event_json() { # event_json <event> [key=value ...]
  python3 "$TESTS_DIR/make-input.py" "$@"
}

post_json() { event_json PostToolUse "file_path=$1"; }
stop_json() { event_json Stop "stop_hook_active=$1"; }
session_json() { event_json SessionStart "source=$1"; }

echo "== hooks under test: $HOOKS_DIR"
echo "== sandbox: $WORK"
for script in "$LINT" "$STOP" "$HANDOFF"; do
  if [ -x "$script" ]; then
    check "executable: $(basename "$script")" 0 0
  else
    check "executable: $(basename "$script")" 0 1
  fi
done
python3 -m json.tool "$HOOKS_DIR/hooks.json" >/dev/null 2>&1
check "hooks.json parses as JSON" 0 $?
for script in "$LINT" "$STOP" "$HANDOFF"; do
  bash -n "$script" 2>/dev/null
  check "parses as bash: $(basename "$script")" 0 $?
done
python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' \
  "$HOOKS_DIR/scripts/resolve_touched_project.py" 2>/dev/null
check "resolve_touched_project.py parses" 0 $?

# shellcheck source=cases-resolver.sh
. "$TESTS_DIR/cases-resolver.sh"
# shellcheck source=cases-posttooluse.sh
. "$TESTS_DIR/cases-posttooluse.sh"
# shellcheck source=cases-stop.sh
. "$TESTS_DIR/cases-stop.sh"
# shellcheck source=cases-sessionstart.sh
. "$TESTS_DIR/cases-sessionstart.sh"

echo
echo "== exit codes"
printf '| %-12s | %-48s | %s |\n' "Hook" "Case" "Exit"
printf '| %-12s | %-48s | %s |\n' "------------" \
  "------------------------------------------------" "----"
for entry in "${ROWS[@]}"; do
  IFS='|' read -r hook case_name code <<<"$entry"
  printf '| %-12s | %-48s | %-4s |\n' "$hook" "$case_name" "$code"
done

echo
echo "passed: $pass  failed: $fail  skipped: $skipped"
[ "$fail" -eq 0 ]
