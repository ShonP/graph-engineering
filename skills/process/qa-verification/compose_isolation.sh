#!/usr/bin/env bash
#
# Compose isolation check: does a qa stack share anything with the developer's?
#
#   compose_isolation.sh <project> [compose args from runtime.up, e.g. -f a.yaml -f b.yaml]
#
# Run it from the run's worktree (the directory `up` runs in). It renders the
# config with every profile enabled and prints one line per leak:
#   - a volume, network or container name without the <project> prefix
#     (`-p` renames only project-scoped resources)
#   - anything `external: true`
#   - a volume backed by a host path (`driver_opts.device`)
#   - `network_mode: host` or `container:...`, and `volumes_from: container:...`
#   - a bind mount whose source is outside the worktree (`./data` is inside it,
#     so it is the run's own copy; `/var/run/docker.sock` or `$HOME/...` is not)
#
# Exit 0: nothing printed, safe to `up`. Exit 1: leaks printed. Exit 2: the
# config could not be rendered or checked - BLOCKED, never "no leaks".
set -uo pipefail

[ $# -ge 1 ] && [ -n "$1" ] || { echo "usage: $0 <project> [compose args]" >&2; exit 2; }
project="$1"; shift
root="$(pwd -P)"

json="$(docker compose -p "$project" --profile '*' "$@" config --format json)" || {
  echo "compose config failed (see stderr above)" >&2; exit 2; }
[ -n "$json" ] || { echo "compose config printed nothing" >&2; exit 2; }

leaks="$(printf '%s' "$json" | jq -r --arg p "$project" --arg root "$root" '
  def outside: (. == $root or startswith($root + "/")) | not;
  [ (.volumes  // {} | .[] | select(.external == true) | "external volume: \(.name)"),
    (.networks // {} | .[] | select(.external == true) | "external network: \(.name)"),
    (.volumes  // {} | .[] | select(.external != true) | .name | select(startswith($p) | not) | "shared volume name: \(.)"),
    (.networks // {} | .[] | select(.external != true) | .name | select(startswith($p) | not) | "shared network name: \(.)"),
    (.volumes  // {} | to_entries[] | select(.value.driver_opts.device != null) | "host-backed volume: \(.key) -> \(.value.driver_opts.device)"),
    (.services // {} | to_entries[] | .key as $s | .value |
      ( (.container_name // empty | select(startswith($p) | not) | "\($s): container_name \(.)"),
        (.network_mode // empty | select(. == "host" or startswith("container:")) | "\($s): network_mode \(.)"),
        (.volumes_from // [] | .[] | select(startswith("container:")) | "\($s): volumes_from \(.)"),
        (.volumes // [] | .[] | select(.type == "bind") | .source | select(outside) | "\($s): bind mount outside the worktree \(.)") ))
  ] | .[]')" || { echo "jq failed on the compose config" >&2; exit 2; }

[ -z "$leaks" ] && exit 0
printf '%s\n' "$leaks"
exit 1
