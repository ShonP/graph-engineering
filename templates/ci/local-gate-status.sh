#!/usr/bin/env bash
set -euo pipefail

GATE_SCRIPT="${GATE_SCRIPT:-scripts/ci/gate.sh}"
LOCKFILES=(uv.lock pnpm-lock.yaml package-lock.json yarn.lock bun.lock Cargo.lock go.sum pubspec.lock
  Package.resolved Gemfile.lock poetry.lock)

digest() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256; else sha256sum; fi
}

key() {
  [ -f "$GATE_SCRIPT" ] || return 1
  local files=("$GATE_SCRIPT") lock hash
  for lock in "${LOCKFILES[@]}"; do
    [ -f "$lock" ] && files+=("$lock")
  done
  read -r hash _ < <(cat "${files[@]}" | digest)
  printf '%s\n' "$hash"
}

refuse() {
  echo "local-gate: not published: $1"
  exit 0
}

publish() {
  [ -z "$(git status --porcelain)" ] || refuse "dirty tree"
  command -v gh >/dev/null 2>&1 || refuse "gh not found"
  gh auth status >/dev/null 2>&1 || refuse "gh auth status failed"
  local sha value
  sha="$(git rev-parse HEAD)"
  value="$(key)" || refuse "no gate script at $GATE_SCRIPT"
  gh api -X POST "repos/{owner}/{repo}/statuses/$sha" -f state=success -f context=local-gate \
    -f "description=key=$value" >/dev/null || refuse "gh api failed"
  echo "local-gate: published key=$value on $sha"
}

verified() {
  command -v gh >/dev/null 2>&1 || return 1
  [ -n "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ] || return 1
  local value latest
  value="$(key)" || return 1
  latest="$(gh api "repos/{owner}/{repo}/commits/$1/statuses?per_page=100" \
    --jq '[.[] | select(.context == "local-gate")][0] | select(. != null) | "\(.state) \(.description)"')" || return 1
  [ "$latest" = "success key=$value" ]
}

check() {
  local sha="${1:-${GITHUB_SHA:-}}" result=false
  [ -n "$sha" ] || sha="$(git rev-parse HEAD)"
  verified "$sha" && result=true
  echo "verified=$result"
  [ -z "${GITHUB_OUTPUT:-}" ] || echo "verified=$result" >>"$GITHUB_OUTPUT"
  [ "$result" = true ]
}

case "${1:-}" in
  key) key ;;
  publish) publish ;;
  check) check "${2:-}" ;;
  *) echo "usage: local-gate-status.sh key | publish | check [<sha>]" >&2; exit 2 ;;
esac
