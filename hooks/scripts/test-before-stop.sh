#!/usr/bin/env bash
#
# Stop hook: run the project's own test script and block the turn until it is
# green. Exit 2 with a short reason on stderr blocks; exit 0 lets Claude stop.
#
# Contract, from the docs fetched 2026-09-10:
#   Hooks reference, "Hooks reference - Claude Code Docs"
#     https://code.claude.com/docs/en/hooks
#     - "Exit code 2 behavior per event": for Stop, exit 2 "Prevents Claude from
#       stopping, continues the conversation".
#     - "Stop decision control": "A hook that blocks by exiting 2 routes the same
#       way as `reason`: Claude receives the stderr message as the explanation for
#       why it should continue."
#     - "Stop input": stop_hook_active is true while Claude Code is already
#       continuing because of a stop hook, and "Claude Code overrides the hook and
#       ends the turn after 8 consecutive blocks". That cap is enforced by Claude
#       Code, so this script keeps no counter of its own; it reports the flag in
#       the reason so the loop state is visible in the transcript.
#   uv, "Running commands | uv"
#     https://docs.astral.sh/uv/concepts/projects/run/
#     - `uv run <name>` runs a command the project environment provides.
#   Task, "Command Line Interface Reference | Task"
#     https://taskfile.dev/reference/cli/
#     - "Combine --list or --list-all with --silent ... to list only the task
#       names in each line. Useful for scripting with grep or similar."
#
# Detection order, in $CLAUDE_PROJECT_DIR only, no walking:
#   1. pyproject.toml with test under [project.scripts]  -> `uv run test`
#   2. package.json with scripts.test                    -> `<pm> run test`
#      where <pm> is pnpm, yarn, bun or npm, chosen by lockfile.
#   3. Taskfile.yml with a test task in `task --list-all --silent` -> `task test`
# No match, or the tool the project needs is not installed: exit 0 in silence.
#
# Least privilege: the only command this hook runs is the project's own test
# script, from the session's project directory. No eval, no network, nothing read
# from a file's contents.

set -eu

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
HOOK_INPUT="$(cat)"

command -v python3 >/dev/null 2>&1 || exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] || exit 0
[ -d "$PROJECT_DIR" ] || exit 0

STOP_ACTIVE="$(HOOK_INPUT="$HOOK_INPUT" python3 -c '
import json
import os

try:
    data = json.loads(os.environ["HOOK_INPUT"])
    value = data["stop_hook_active"]
except Exception:
    print("unknown")
else:
    print("true" if value else "false")
' 2>/dev/null)" || STOP_ACTIVE="unknown"

cd "$PROJECT_DIR" || exit 0
PROJECT_DIR="$(pwd -P)"

has_script() { # has_script <pyproject|package> <name>
  PROJECT_KIND="$1" SCRIPT_NAME="$2" python3 -c '
import json
import os
import sys

kind = os.environ["PROJECT_KIND"]
name = os.environ["SCRIPT_NAME"]

if kind == "pyproject":
    try:
        import tomllib
    except ImportError:
        sys.exit(1)
    try:
        with open("pyproject.toml", "rb") as handle:
            data = tomllib.load(handle)
    except Exception:
        sys.exit(1)
    scripts = data.get("project", {}).get("scripts", {})
else:
    try:
        with open("package.json", "rb") as handle:
            data = json.load(handle)
    except Exception:
        sys.exit(1)
    scripts = data.get("scripts", {})

if isinstance(scripts, dict) and isinstance(scripts.get(name), str) and scripts[name].strip():
    sys.exit(0)
sys.exit(1)
' 2>/dev/null
}

package_manager() {
  if [ -f pnpm-lock.yaml ]; then
    echo pnpm
  elif [ -f yarn.lock ]; then
    echo yarn
  elif [ -f bun.lock ] || [ -f bun.lockb ]; then
    echo bun
  else
    echo npm
  fi
}

taskfile_has_test() {
  set +e
  listing="$(task --list-all --silent 2>/dev/null)"
  set -e
  printf '%s\n' "$listing" |
    sed 's/^[[:space:]*]*//; s/[[:space:]]*$//' |
    grep -qx 'test'
}

LABEL=""
set --

if [ -f pyproject.toml ] && has_script pyproject test && command -v uv >/dev/null 2>&1; then
  LABEL="uv run test"
  set -- uv run test
elif [ -f package.json ] && has_script package test; then
  PM="$(package_manager)"
  if command -v "$PM" >/dev/null 2>&1; then
    LABEL="$PM run test"
    set -- "$PM" run test
  fi
elif [ -f Taskfile.yml ] && command -v task >/dev/null 2>&1; then
  set +e
  taskfile_has_test
  HAS_TASK_TEST=$?
  set -e
  if [ "$HAS_TASK_TEST" -eq 0 ]; then
    LABEL="task test"
    set -- task test
  fi
fi

[ -n "$LABEL" ] || exit 0

set +e
OUTPUT="$("$@" 2>&1)"
STATUS=$?
set -e

if [ "$STATUS" -eq 0 ]; then
  exit 0
fi

# The backticks below are literal Markdown in the reason text, and the python
# source must reach python3 unexpanded, so single quotes are deliberate here.
# shellcheck disable=SC2016
LABEL="$LABEL" STATUS="$STATUS" OUTPUT="$OUTPUT" \
  PROJECT_DIR="$PROJECT_DIR" STOP_ACTIVE="$STOP_ACTIVE" python3 -c '
import os
import sys

lines = os.environ["OUTPUT"].rstrip().splitlines()
if len(lines) > 20:
    lines = ["... earlier output trimmed ..."] + lines[-20:]
tail = "\n".join(lines)[:2000]

sys.stderr.write(
    "`%s` failed in %s (exit %s). Fix the failing tests, then finish.\n"
    "stop_hook_active=%s; Claude Code ends the turn after 8 consecutive blocks "
    "(hooks reference, \"Stop input\").\n\n%s\n"
    % (
        os.environ["LABEL"],
        os.environ["PROJECT_DIR"],
        os.environ["STATUS"],
        os.environ["STOP_ACTIVE"],
        tail,
    )
)
' || printf '`%s` failed in %s (exit %s). Fix the failing tests, then finish.\n' \
  "$LABEL" "$PROJECT_DIR" "$STATUS" >&2

exit 2
