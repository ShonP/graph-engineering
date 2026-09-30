#!/usr/bin/env bash
# Capture the text the SessionStart hook shows Claude, as evidence.
# Usage: capture.sh <plugin-root> > before.txt   (run once on the base commit,
# once on the change). Synthetic fixture: every file below is invented.
set -uo pipefail
HOOK="$1/hooks/scripts/print-handoff.sh"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-ux-capture.XXXXXX")" && WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/long/docs" "$WORK/long/.claude" "$WORK/short/docs" "$WORK/profile-only/.claude"
for n in $(seq 1 200); do printf 'line %s of a long synthetic handoff\n' "$n"; done >"$WORK/long/docs/HANDOFF.md"
for n in $(seq 1 12); do printf 'line %s of a short synthetic handoff\n' "$n"; done >"$WORK/short/docs/HANDOFF.md"
printf 'name: synthetic\n' >"$WORK/long/.claude/graph-profile.yaml"
printf 'name: synthetic\n' >"$WORK/profile-only/.claude/graph-profile.yaml"
show() { # show <title> <project> <json>
  local out rc
  out="$(printf '%s' "$3" | env CLAUDE_PROJECT_DIR="$WORK/$2" bash "$HOOK" 2>&1)"; rc=$?
  printf '### %s\nexit: %s\nstdout:\n%s\n\n' "$1" "$rc" "${out//$WORK/<tmp>}"
}
input() { printf '{"session_id":"s","hook_event_name":"SessionStart","cwd":"/","source":"%s"%s}' "$1" "${2:-}"; }
show "startup, 200-line HANDOFF, profile present" long "$(input startup)"
show "startup, 12-line HANDOFF, no profile" short "$(input startup)"
show "startup, no HANDOFF, profile present" profile-only "$(input startup)"
show "compact, 200-line HANDOFF, profile present" long "$(input compact)"
show "resume (defence in depth beside the matcher)" long "$(input resume)"
show "fork (defence in depth beside the matcher)" long "$(input fork)"
show "startup with agent_type (claude --agent)" long "$(input startup ',"agent_type":"Explore"')"
