#!/usr/bin/env bash
# Capture what print-handoff.sh prints into a fresh session when a run has a
# success measure due, as evidence. Usage: capture.sh <plugin-root> > before.txt
# (run once on the base commit, once on the change). Synthetic fixtures: every
# repo, run id, goal and command below is invented. Merge commits are dated
# 2020-01-01 so "window elapsed" does not depend on the day this runs.
set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
PLUGIN="$(cd "$1" && pwd -P)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-ux-capture.XXXXXX")" && WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT

show() { # show <title> <project-dir>
  local out rc
  printf '### %s\n' "$1"
  out="$(printf '{"hook_event_name":"SessionStart","source":"startup","cwd":"%s"}' "$2" |
    env CLAUDE_PROJECT_DIR="$2" bash "$PLUGIN/hooks/scripts/print-handoff.sh" 2>&1)"; rc=$?
  out="${out//"$PLUGIN"/<plugin>}" # the checkout path is machine-specific
  printf 'hooks/scripts/print-handoff.sh: exit %s\n%s\n\n' "$rc" "${out:-(no output)}"
}

# repo <name> - a git repo with one commit dated 2020-01-01; prints its path.
repo() {
  local dir="$WORK/$1"
  mkdir -p "$dir" && git -C "$dir" init -q && printf 'x\n' >"$dir/README.md"
  git -C "$dir" add README.md
  GIT_AUTHOR_DATE=2020-01-01T00:00:00Z GIT_COMMITTER_DATE=2020-01-01T00:00:00Z \
    git -C "$dir" -c user.name=fixture -c user.email=fixture@example.invalid \
    -c commit.gpgsign=false commit -q -m init
  printf '%s' "$dir"
}

# run <repo> <run-id> <window_days> - a merged run with one success signal.
run() {
  local dir="$1/.graph/$2" sha
  mkdir -p "$dir"
  sha="$(git -C "$1" rev-parse HEAD)"
  printf '{"schema_version": 2, "cases": [], "tasks": [], "external_contracts": [],
 "success_signals": [{"goal": "checkout error ratio stays low", "source": "command",
 "command": ["./scripts/error-ratio.sh"], "success_condition": "value <= 0.01",
 "window_days": %s}]}\n' "$3" >"$dir/plan.json"
  printf 'playbook: feature - lane full, risk: none - fixture\n- merge: merged: %s\n' "$sha" >"$dir/ledger.md"
}

plain="$(repo no-runs)"
show "repo with no .graph/*/plan.json" "$plain"

due="$(repo api-service)"
run "$due" 01a0d000-0000-7000-8000-000000000001 7
show "one merged run, 7-day window elapsed, no measure.md" "$due"

pending="$(repo go-cli)"
run "$pending" 01a0d000-0000-7000-8000-000000000002 36500
show "one merged run, window not elapsed" "$pending"

run "$due" 01a0d000-0000-7000-8000-000000000003 14
printf '# Success measures\n\n| goal | status | value | observed_at |\n| --- | --- | --- | --- |\n| checkout error ratio stays low | met | 0.004 | 2020-01-20T00:00:00Z |\n' \
  >"$due/.graph/01a0d000-0000-7000-8000-000000000001/measure.md"
show "two merged runs, one already measured" "$due"
