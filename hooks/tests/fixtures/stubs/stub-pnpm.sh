#!/bin/sh
# TEST STUB, not pnpm. run-tests.sh copies this to <sandbox>/bin/pnpm.
# It implements only:
#
#   pnpm run <script> [args...]
#
# reading the command string from ./package.json and appending the arguments to
# it before handing the whole thing to sh, which is what npm and pnpm both do.
# That append is exactly the behaviour the `--` question turned on: measured on
# 2026-09-10, npm 11.12.1 strips a leading `--` and pnpm 10.33.3 passes it
# through as a literal argument, so the hooks pass the file with no separator.
set -eu

[ "${1:-}" = "run" ] || { echo "stub pnpm: only 'pnpm run' is supported" >&2; exit 2; }
shift
script="${1:-}"
[ -n "$script" ] || { echo "stub pnpm: no script given" >&2; exit 2; }
shift

body="$(SCRIPT_NAME="$script" python3 -c '
import json
import os
import sys

with open("package.json", "rb") as handle:
    scripts = json.load(handle).get("scripts", {})
name = os.environ["SCRIPT_NAME"]
if name not in scripts:
    sys.exit(1)
print(scripts[name])
')" || { echo "stub pnpm: missing script: $script" >&2; exit 1; }

for arg in "$@"; do
  quoted="$(printf '%s' "$arg" | sed "s/'/'\\\\''/g")"
  body="$body '$quoted'"
done

sh -c "$body"
