#!/bin/sh
# Records its argv so the harness can assert that the touched file arrives as
# the only argument, with no bare `--` in front of it.
printf '%s\n' "$@" > RAN_TYPECHECK
[ -f PASS ] && exit 0
echo "fixture tsc: TS2322" >&2
exit 1
