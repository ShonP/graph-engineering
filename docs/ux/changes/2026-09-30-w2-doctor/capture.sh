#!/usr/bin/env bash
# Capture what the SessionStart hooks print into a fresh session, as evidence.
# Usage: capture.sh <plugin-root> > before.txt   (run once on the base commit,
# once on the change). Runs every handler hooks.json registers for the
# `startup` source, the way Claude Code does. Synthetic fixtures: every file
# below is invented. CLAUDE_CONFIG_DIR points at an empty directory so the
# owner's installed-plugin record never shapes the output.
set -uo pipefail
PLUGIN="$(cd "$1" && pwd -P)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-ux-capture.XXXXXX")" && WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/config"
handlers="$(python3 - "$PLUGIN" <<'PY'
import json, sys
root = sys.argv[1]
hooks = json.load(open(f"{root}/hooks/hooks.json"))["hooks"].get("SessionStart", [])
for group in hooks:
    if "startup" in group.get("matcher", "").split("|"):
        for h in group["hooks"]:
            print(h["command"].replace("${CLAUDE_PLUGIN_ROOT}", root))
PY
)"
show() { # show <title> <project-dir>
  local script out rc
  printf '### %s\n' "$1"
  while IFS= read -r script; do
    [ -n "$script" ] || continue
    out="$(printf '{"hook_event_name":"SessionStart","source":"startup","cwd":"%s"}' "$2" |
      env CLAUDE_PROJECT_DIR="$2" CLAUDE_CONFIG_DIR="$WORK/config" bash "$script" 2>/dev/null)"; rc=$?
    printf '%s: exit %s\n%s\n' "${script#"$PLUGIN"/}" "$rc" "${out:-(no output)}"
  done <<<"$handlers"
  printf '\n'
}
repo() { mkdir -p "$WORK/$1" && git -C "$WORK/$1" init -q && printf '%s' "$WORK/$1"; }

web="$(repo web-app)"
printf '{"name":"fixture"}\n' >"$web/package.json"
show "git repo with package.json, no .claude/graph-profile.yaml" "$web"

notes="$(repo notes)"
printf '# notes\n' >"$notes/README.md"
show "git repo with no stack marker and no profile" "$notes"

mkdir -p "$WORK/scratch" && printf '{"name":"fixture"}\n' >"$WORK/scratch/package.json"
show "directory that is not a git repo" "$WORK/scratch"

svc="$(repo api-service)"
mkdir -p "$svc/.claude"
printf '[project]\nname = "fixture"\n' >"$svc/pyproject.toml"
printf 'content:\n  voice: formal\nrouting: {}\n' >"$svc/.claude/graph-profile.yaml"
show "profile without schema_version, with stale content key, no graph-checks.json" "$svc"

printf 'schema_version: 2\nruntime:\n  none: CLI verified through public commands\n' >"$svc/.claude/graph-profile.yaml"
printf '{"version": 1}\n' >"$svc/.claude/graph-checks.json"
show "same repo after the fix, first startup" "$svc"
show "same repo, second startup, nothing changed (cache hit)" "$svc"
