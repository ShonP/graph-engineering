#!/usr/bin/env bash
#
# SessionStart hook, matcher `startup` only: a cached, fail-open health check of
# this repo's graph-engineering setup. Exits 0 on every path.
#
#   - CLAUDE_PROJECT_DIR has no .git: silent.
#   - No .claude/graph-profile.yaml: one /graph-init hint when the project root
#     holds a stack marker (package.json, pyproject.toml, go.mod, ...), else silent.
#   - A profile: `graph-control.py doctor --quick` (it starts no process of its
#     own) and at most 3 lines for its warn and error findings. A clean result is
#     cached in $(git rev-parse --git-common-dir)/graph-engineering/doctor-cache,
#     one line per project dir keyed by the plugin version and the mtimes of the
#     profile and .claude/graph-checks.json, so a hit starts no uv at all.
#
# Stdout is plain text, which SessionStart adds to Claude's context
# (https://code.claude.com/docs/en/hooks.md, "SessionStart decision control").
# Least privilege: reads the profile and plugin manifest, runs the plugin's own
# pinned helper, writes only the cache file inside the repo's git directory.

set -u

# Drain stdin first, on every path, so Claude Code's writer never sees EPIPE.
cat >/dev/null 2>&1

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] && [ -e "$PROJECT_DIR/.git" ] || exit 0

PROFILE="$PROJECT_DIR/.claude/graph-profile.yaml"
if [ ! -f "$PROFILE" ]; then
  for marker in package.json pyproject.toml go.mod Cargo.toml Package.swift build.gradle build.gradle.kts pom.xml Gemfile; do
    if [ -f "$PROJECT_DIR/$marker" ]; then
      printf '%s\n' 'graph-engineering: this repo has no .claude/graph-profile.yaml. The owner can run /graph-init to set it up.'
      break
    fi
  done
  exit 0
fi

PLUGIN_ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)" || exit 0
MANIFEST="$PLUGIN_ROOT/.claude-plugin/plugin.json"
[ -f "$MANIFEST" ] || exit 0
version_re='"version"[[:space:]]*:[[:space:]]*"([^"]+)"'
[[ $(<"$MANIFEST") =~ $version_re ]] || exit 0
VERSION="${BASH_REMATCH[1]}"

mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo unknown; }
CHECKS="$PROJECT_DIR/.claude/graph-checks.json"
checks_mtime=none
[ -f "$CHECKS" ] && checks_mtime="$(mtime "$CHECKS")"
TAB="$(printf '\t')"
KEY="$PROJECT_DIR$TAB$VERSION$TAB$(mtime "$PROFILE")$TAB$checks_mtime"

common="$(git -C "$PROJECT_DIR" rev-parse --git-common-dir 2>/dev/null)" || exit 0
[ -n "$common" ] || exit 0
case "$common" in /*) ;; *) common="$PROJECT_DIR/$common" ;; esac
CACHE="$common/graph-engineering/doctor-cache"
[ -f "$CACHE" ] && grep -Fxq -- "$KEY" "$CACHE" 2>/dev/null && exit 0

command -v uv >/dev/null 2>&1 || exit 0
# shellcheck source=python-runtime.sh
. "$PLUGIN_ROOT/hooks/scripts/python-runtime.sh" 2>/dev/null || exit 0
ge_python_runtime 2>/dev/null || exit 0

REPORT="$(uv run --quiet --script "$PLUGIN_ROOT/scripts/graph-control.py" \
  doctor --root "$PROJECT_DIR" --quick 2>/dev/null)" || exit 0

# Prints the lines to show (none when clean); exits nonzero on any unexpected shape.
FORMAT="$(cat <<'PY'
import json, sys


def one(text):
    return " ".join(str(text).split())[:240]


data = json.load(sys.stdin)
if data.get("status") != "PASS" or not isinstance(data.get("findings"), list):
    sys.exit(1)
rank = {"error": 0, "warn": 1}
shown = sorted((f for f in data["findings"] if f.get("level") in rank), key=lambda f: rank[f["level"]])
lines = ["graph-engineering doctor: %s - fix: %s" % (one(f["message"]), one(f["fix"])) for f in shown]
if len(lines) > 3:
    lines = lines[:2] + ["graph-engineering doctor: %d more findings - fix: run /graph-doctor" % (len(lines) - 2)]
if lines:
    print("\n".join(lines))
PY
)"
LINES="$(printf '%s' "$REPORT" | "$GE_PYTHON" -c "$FORMAT" 2>/dev/null)" || exit 0

if [ -n "$LINES" ]; then
  printf '%s\n' "$LINES"
  exit 0
fi

# Clean: record the key, replacing this project dir's older line, newest 64 kept.
mkdir -p "${CACHE%/*}" 2>/dev/null || exit 0
TMP="$CACHE.$$"
{
  [ -f "$CACHE" ] && DIR="$PROJECT_DIR" awk -F '\t' '$1 != ENVIRON["DIR"]' "$CACHE" | tail -n 63
  printf '%s\n' "$KEY"
} >"$TMP" 2>/dev/null && mv -f "$TMP" "$CACHE" 2>/dev/null
rm -f "$TMP" 2>/dev/null
exit 0
