#!/usr/bin/env bash
# Regression cases for compose_isolation.sh. Needs docker compose v2 and jq;
# exits 77 (skipped, the automake convention) when either is missing. Writes only inside a mktemp dir.
set -uo pipefail

CHECK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)/compose_isolation.sh"
docker compose version >/dev/null 2>&1 && command -v jq >/dev/null || { echo "SKIP: docker compose or jq missing"; exit 77; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-iso.XXXXXX")" && WORK="$(cd "$WORK" && pwd -P)" || exit 1
trap 'rm -rf "$WORK"' EXIT
fail=0

case_() { # case_ <label> <expected exit> <expected line or ""> <compose yaml>
  rm -f "$WORK/compose.yaml"; printf '%s\n' "$4" > "$WORK/compose.yaml"
  out="$(cd "$WORK" && bash "$CHECK" ge-t 2>&1)"; code=$?
  if [ "$code" = "$2" ] && { [ -z "$3" ] || grep -qF -- "$3" <<<"$out"; }; then
    echo "ok   $1"
  else
    echo "FAIL $1 (exit $code)"; printf '%s\n' "$out" | sed 's/^/     /'; fail=1
  fi
}

case_ "plain file is clean"           0 ""                              $'services:\n  app:\n    image: alpine\n    volumes: [./data:/data, pg:/pg]\nvolumes:\n  pg: {}'
case_ "named volume"                  1 "shared volume name: pgdata"    $'services:\n  app:\n    image: alpine\n    volumes: [pg:/pg]\nvolumes:\n  pg:\n    name: pgdata'
case_ "external network"              1 "external network: corp"        $'services:\n  app:\n    image: alpine\n    networks: [corp]\nnetworks:\n  corp:\n    name: corp\n    external: true'
case_ "container_name"                1 "app: container_name dev-app"   $'services:\n  app:\n    image: alpine\n    container_name: dev-app'
case_ "container_name in a profile"   1 "dbg: container_name shared"    $'services:\n  dbg:\n    image: alpine\n    profiles: [debug]\n    container_name: shared'
case_ "network_mode host"             1 "app: network_mode host"        $'services:\n  app:\n    image: alpine\n    network_mode: host'
case_ "network_mode container"        1 "network_mode container:dev"    $'services:\n  app:\n    image: alpine\n    network_mode: "container:dev"'
case_ "volumes_from container"        1 "volumes_from container:db"     $'services:\n  app:\n    image: alpine\n    volumes_from: ["container:db"]'
case_ "bind outside worktree"         1 "outside the worktree /var/run" $'services:\n  app:\n    image: alpine\n    volumes: [/var/run/docker.sock:/s]'
case_ "host-backed volume"            1 "host-backed volume: pg"        $'services:\n  app:\n    image: alpine\n    volumes: [pg:/pg]\nvolumes:\n  pg:\n    driver_opts: {type: none, o: bind, device: /srv/pg}'
case_ "unparseable config is BLOCKED" 2 ""                              $'services: [oops'

exit $fail
