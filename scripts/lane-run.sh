#!/usr/bin/env bash
# Run a command holding a slot of a host lane:
#   lane-run.sh <lane> [--slots N] [--wait-seconds S] [--max-load5 L] -- <argv...>
# The lock is inherited by the command and released by the kernel when it and
# its children exit. --max-load5 waits for the 5-minute load average to be at
# most L before taking a slot, holding none while it waits, within the same
# --wait-seconds; see scripts/lane_run.py for the contract and exit codes
# (69 here: no Python 3.11+ on the host).
# Rollback: remove the call site; nothing persists but empty lock files.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
# shellcheck source=../hooks/scripts/python-runtime.sh
. "$here/../hooks/scripts/python-runtime.sh"
ge_python_runtime || exit 69
exec "$GE_PYTHON" "$here/lane_run.py" "$@"
