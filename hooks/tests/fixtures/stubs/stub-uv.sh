#!/bin/sh
# TEST STUB, not uv. run-tests.sh copies this to <sandbox>/bin/uv so the hooks
# find it on PATH. It implements only the one form the hooks use:
#
#   uv run <script> [args...]
#
# It checks that <script> is declared under [project.scripts] in ./pyproject.toml,
# the same condition the hook checks, then runs ./stub-scripts/<script>.sh.
# The real behaviour it stands in for is documented at
# https://docs.astral.sh/uv/concepts/projects/run/ ("Running commands | uv"):
# "Presuming the project provides `example-cli`" ... `uv run example-cli foo`.
set -eu

[ "${1:-}" = "run" ] || { echo "stub uv: only 'uv run' is supported" >&2; exit 2; }
shift
script="${1:-}"
[ -n "$script" ] || { echo "stub uv: no script given" >&2; exit 2; }
shift

SCRIPT_NAME="$script" python3 -c '
import os
import sys
import tomllib

with open("pyproject.toml", "rb") as handle:
    data = tomllib.load(handle)
scripts = data.get("project", {}).get("scripts", {})
sys.exit(0 if os.environ["SCRIPT_NAME"] in scripts else 1)
' || { echo "stub uv: '$script' is not in [project.scripts]" >&2; exit 2; }

exec sh "./stub-scripts/$script.sh" "$@"
