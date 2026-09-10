#!/bin/sh
# Stands in for the console script the real `uv run test` would execute.
# Records its argv so the harness can assert the exact call shape, then passes
# when a PASS file is present and fails when it is not.
printf '%s\n' "$@" > RAN_TEST
[ -f PASS ] && exit 0
echo "fixture: 1 failed, 2 passed" >&2
exit 1
