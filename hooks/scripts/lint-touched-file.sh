#!/usr/bin/env bash
#
# PostToolUse hook, matcher Edit|Write: lint and typecheck the file Claude just
# touched. It informs and never blocks: it exits 0 on every path.
#
# Contract, from the docs fetched 2026-09-10:
#   Hooks reference, "Hooks reference - Claude Code Docs"
#     https://code.claude.com/docs/en/hooks
#     - "PostToolUse input": tool_input.file_path is the absolute path the tool wrote.
#     - "Exit code 2 behavior per event": PostToolUse cannot block; exit 2 only
#       shows stderr to Claude. This hook never does that.
#     - "Exit code 0": stdout and stderr from a hook that exits 0 go to the debug
#       log for PostToolUse, so plain text would never reach Claude. Findings are
#       therefore returned as hookSpecificOutput.additionalContext, the documented
#       way to put a note next to the tool result ("Add context for Claude").
#   uv, "Running commands | uv"
#     https://docs.astral.sh/uv/concepts/projects/run/
#     - `uv run <name>` runs a command the project environment provides.
#   Task, "Command Line Interface Reference | Task"
#     https://taskfile.dev/reference/cli/
#     - Taskfile projects are handled by the Stop hook only; a Taskfile has no
#       single-file lint shape.
#
# Detection order, nearest project file first, walking up from the edited file
# and stopping at $CLAUDE_PROJECT_DIR:
#   1. pyproject.toml with lint / typecheck under [project.scripts]
#        -> `uv run lint <file>` then `uv run typecheck <file>`
#   2. package.json with scripts.lint / scripts.typecheck
#        -> `<pm> run lint <file>` then `<pm> run typecheck`
#      where <pm> is pnpm, yarn, bun or npm, chosen by lockfile. The file is
#      passed without an `npm`-style `--` separator: measured on 2026-09-10,
#      npm 11.12.1 strips a leading `--` and pnpm 10.33.3 forwards it to the
#      script as a literal first argument, so the bare form is the one that
#      behaves the same on both.
# Anything else, including a file outside $CLAUDE_PROJECT_DIR: exit 0 in silence.
#
# Least privilege: the only commands this hook runs are the project's own named
# scripts, from the project directory that declares them, inside the session's
# project directory. Nothing is read from the edited file's contents, there is no
# eval, no shell interpolation of the path, and no network access.

set -eu

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
HOOK_INPUT="$(cat)"

command -v python3 >/dev/null 2>&1 || exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] || exit 0
[ -d "$PROJECT_DIR" ] || exit 0

# Resolve tool_input.file_path, enforce the project-directory bound, and find the
# nearest project file. Prints two lines on success: the directory, then the kind.
RESOLVED=""
if ! RESOLVED="$(HOOK_INPUT="$HOOK_INPUT" CLAUDE_PROJECT_DIR="$PROJECT_DIR" python3 -c '
import json
import os
import sys

try:
    data = json.loads(os.environ["HOOK_INPUT"])
except Exception:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)

tool_input = data.get("tool_input")
if not isinstance(tool_input, dict):
    sys.exit(0)
raw = tool_input.get("file_path")
if not isinstance(raw, str) or not raw or "\n" in raw or "\x00" in raw:
    sys.exit(0)
if not os.path.isabs(raw):
    sys.exit(0)

try:
    project = os.path.realpath(os.environ["CLAUDE_PROJECT_DIR"])
    touched = os.path.realpath(raw)
except OSError:
    sys.exit(0)

# Containment: equal, or under the project directory with a separator between.
# The separator is what keeps a sibling such as /repo-evil out of /repo.
if touched != project and not touched.startswith(project + os.sep):
    sys.exit(0)

directory = os.path.dirname(touched)
while True:
    if os.path.isfile(os.path.join(directory, "pyproject.toml")):
        print(directory)
        print("pyproject")
        break
    if os.path.isfile(os.path.join(directory, "package.json")):
        print(directory)
        print("package")
        break
    parent = os.path.dirname(directory)
    if directory == project or parent == directory:
        break
    directory = parent
' 2>/dev/null)"; then
  exit 0
fi

[ -n "$RESOLVED" ] || exit 0
PROJECT_FILE_DIR="$(printf '%s\n' "$RESOLVED" | sed -n '1p')"
PROJECT_KIND="$(printf '%s\n' "$RESOLVED" | sed -n '2p')"
[ -n "$PROJECT_FILE_DIR" ] || exit 0
[ -d "$PROJECT_FILE_DIR" ] || exit 0

TOUCHED_FILE="$(HOOK_INPUT="$HOOK_INPUT" python3 -c '
import json
import os
print(os.path.realpath(json.loads(os.environ["HOOK_INPUT"])["tool_input"]["file_path"]))
' 2>/dev/null)" || exit 0
[ -n "$TOUCHED_FILE" ] || exit 0

# has_script <kind> <dir> <name> - is that script declared in the project file?
has_script() {
  PROJECT_KIND="$1" PROJECT_FILE_DIR="$2" SCRIPT_NAME="$3" python3 -c '
import json
import os
import sys

kind = os.environ["PROJECT_KIND"]
directory = os.environ["PROJECT_FILE_DIR"]
name = os.environ["SCRIPT_NAME"]

if kind == "pyproject":
    try:
        import tomllib
    except ImportError:
        sys.exit(1)
    try:
        with open(os.path.join(directory, "pyproject.toml"), "rb") as handle:
            data = tomllib.load(handle)
    except Exception:
        sys.exit(1)
    scripts = data.get("project", {}).get("scripts", {})
else:
    try:
        with open(os.path.join(directory, "package.json"), "rb") as handle:
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
  if [ -f "$1/pnpm-lock.yaml" ]; then
    echo pnpm
  elif [ -f "$1/yarn.lock" ]; then
    echo yarn
  elif [ -f "$1/bun.lock" ] || [ -f "$1/bun.lockb" ]; then
    echo bun
  else
    echo npm
  fi
}

FINDINGS=""

# run_check <label> <command...> - append the output of a failing check.
run_check() {
  label="$1"
  shift
  set +e
  output="$("$@" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    FINDINGS="${FINDINGS}${label} failed (exit ${status}):
${output}

"
  fi
}

case "$PROJECT_KIND" in
  pyproject)
    command -v uv >/dev/null 2>&1 || exit 0
    cd "$PROJECT_FILE_DIR" || exit 0
    if has_script pyproject "$PROJECT_FILE_DIR" lint; then
      run_check "uv run lint" uv run lint "$TOUCHED_FILE"
    fi
    if has_script pyproject "$PROJECT_FILE_DIR" typecheck; then
      run_check "uv run typecheck" uv run typecheck "$TOUCHED_FILE"
    fi
    ;;
  package)
    PM="$(package_manager "$PROJECT_FILE_DIR")"
    command -v "$PM" >/dev/null 2>&1 || exit 0
    cd "$PROJECT_FILE_DIR" || exit 0
    if has_script package "$PROJECT_FILE_DIR" lint; then
      run_check "$PM run lint" "$PM" run lint "$TOUCHED_FILE"
    fi
    if has_script package "$PROJECT_FILE_DIR" typecheck; then
      run_check "$PM run typecheck" "$PM" run typecheck
    fi
    ;;
  *)
    exit 0
    ;;
esac

[ -n "$FINDINGS" ] || exit 0

FINDINGS="$FINDINGS" TOUCHED_FILE="$TOUCHED_FILE" python3 -c '
import json
import os

findings = os.environ["FINDINGS"].rstrip()
lines = findings.splitlines()
if len(lines) > 60:
    lines = ["... earlier output trimmed ..."] + lines[-60:]
findings = "\n".join(lines)[:4000]

context = (
    "Project checks on %s reported problems. This is information, not a block.\n\n%s"
    % (os.environ["TOUCHED_FILE"], findings)
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": context,
    }
}))
' || exit 0

exit 0
