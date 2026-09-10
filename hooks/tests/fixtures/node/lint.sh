#!/bin/sh
# Records its argv so the harness can assert that the touched file arrives as
# the only argument, with no bare `--` in front of it.
printf '%s\n' "$@" > RAN_LINT
[ -f PASS ] && exit 0
echo "fixture lint: no-unused-vars" >&2
exit 1
