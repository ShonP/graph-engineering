#!/usr/bin/env bash
#
# Regression test for the three plugin hooks. Runs from any working directory
# and needs nothing but bash, python3 and the fixtures beside this file. Every
# check a hook runs is opted into per case by writing .claude/graph-checks.json
# into the sandbox. uv, pnpm and task are stubbed under fixtures/stubs and put
# on PATH as bait: a project that declares test or lint scripts but has no
# graph-checks.json must run none of them.
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

# Unit cases use the same supported runtime as production hooks.
. "$HOOKS_DIR/scripts/python-runtime.sh"
ge_python_runtime || exit 1

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-hook-tests.XXXXXX")" || exit 1
# Canonicalise: on macOS $TMPDIR is a symlink, and the hooks canonicalise the
# paths they are handed, so the fixture paths have to match what they resolve to.
WORK="$(cd "$WORK" && pwd -P)" || exit 1
trap 'rm -rf "$WORK"' EXIT INT TERM
cp -R "$TESTS_DIR/fixtures/." "$WORK/" || exit 1

# The stubs are committed under names that say what they are, and are installed
# into the sandbox under the names the old autodetection looked for on PATH.
FIX="$WORK"
STUB_BIN="$WORK/bin"
mkdir -p "$STUB_BIN"
for tool in uv pnpm task; do
  cp "$WORK/stubs/stub-$tool.sh" "$STUB_BIN/$tool" || exit 1
  chmod +x "$STUB_BIN/$tool"
done
rm -rf "$WORK/stubs"

# A python3 that only leaves a marker: first on PATH with GE_PYTHON unset, it
# proves a hook decided in bash alone, before spawning any interpreter.
PY_TRAP="$WORK/python-trap"
mkdir -p "$PY_TRAP"
printf '#!/bin/sh\ntouch "%s/RAN_PYTHON"\nexit 1\n' "$WORK" >"$PY_TRAP/python3"
chmod +x "$PY_TRAP/python3"

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
  find "$WORK" \( -name 'RAN_*' -o -name 'OUTSIDE_*' -o -name 'EVIL_*' \) |
    while read -r marker; do rm -f "$marker"; done
}

set_pass() { touch "$FIX/$1/PASS"; }
set_fail() { rm -f "$FIX/$1/PASS"; }

# write_config <dir> <json> - opt <dir> into checks for one case.
write_config() { mkdir -p "$1/.claude" && printf '%s\n' "$2" >"$1/.claude/graph-checks.json"; }
clear_config() { rm -f "$1/.claude/graph-checks.json"; }

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

# run_hook_python_trap <script> <project_dir> <json> - run_hook with GE_PYTHON
# unset and the python3 trap first on PATH; RAN_PYTHON appears if python ran.
run_hook_python_trap() {
  local saved_path="$HOOK_PATH" saved_python="$GE_PYTHON"
  HOOK_PATH="$PY_TRAP:$HOOK_PATH"
  unset GE_PYTHON
  run_hook "$@"
  GE_PYTHON="$saved_python"
  export GE_PYTHON
  HOOK_PATH="$saved_path"
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
  "$GE_PYTHON" "$TESTS_DIR/make-input.py" "$@"
}

post_json() { local f="$1"; shift; event_json PostToolUse "file_path=$f" "$@"; }
stop_json() { local a="$1"; shift; event_json Stop "stop_hook_active=$a" "$@"; }
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
"$GE_PYTHON" -m json.tool "$HOOKS_DIR/hooks.json" >/dev/null 2>&1
check "hooks.json parses as JSON" 0 $?
for script in "$LINT" "$STOP" "$HANDOFF"; do
  bash -n "$script" 2>/dev/null
  check "parses as bash: $(basename "$script")" 0 $?
done
for module in configured_check.py checks_config.py; do
  "$GE_PYTHON" -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' \
    "$HOOKS_DIR/scripts/$module" 2>/dev/null
  check "$module parses" 0 $?
done
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
