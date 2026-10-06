#!/usr/bin/env bash
# Run commands on an iOS simulator booted headless; close it when done:
#   sim-session.sh [--device <name|udid>] [--keep-gui] [--label L] -- <argv...>   one-shot
#   sim-session.sh acquire [--device <name|udid>] [--label L]   prints SIM_UDID= and SIM_LEASE=
#   sim-session.sh run --lease <id> [--keep-gui] -- <argv...>   one step; renews the lease
#   sim-session.sh release --lease <id>                         at the end, failure included
# SIM_UDID is exported to the command (use `-destination id=$SIM_UDID`). A
# device is shut down only when a wrapper booted it and no live lease holds it;
# Simulator.app is quit only when nothing is booted. See scripts/sim_session.py
# for the contract and exit codes (69 here: no Python 3.11+ on the host).
# Never `open -a Simulator`; close what you open.
# Rollback: remove the call site; state is small JSON under ~/.cache/graph-engineering/sims.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
# shellcheck source=../hooks/scripts/python-runtime.sh
. "$here/../hooks/scripts/python-runtime.sh"
ge_python_runtime || exit 69
exec "$GE_PYTHON" "$here/sim_session.py" "$@"
