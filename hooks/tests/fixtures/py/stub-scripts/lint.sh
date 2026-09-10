#!/bin/sh
# Stands in for the console script the real `uv run lint` would execute.
# Records its argv so the harness can assert the exact call shape, then passes
# when a PASS file is present and fails when it is not.
printf '%s\n' "$@" > RAN_LINT
[ -f PASS ] && exit 0
echo "fixture lint: E501 line too long" >&2
exit 1
