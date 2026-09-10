#!/bin/sh
# Stands in for the console script the real `uv run typecheck` would execute.
# Records its argv so the harness can assert the exact call shape, then passes
# when a PASS file is present and fails when it is not.
printf '%s\n' "$@" > RAN_TYPECHECK
[ -f PASS ] && exit 0
echo "fixture typecheck: error: incompatible types" >&2
exit 1
