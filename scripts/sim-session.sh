#!/usr/bin/env bash
# Run a command with an iOS simulator booted headless; close it afterwards:
#   sim-session.sh [--device <name|udid>] [--keep-gui] [--label L] -- <argv...>
# SIM_UDID is exported to the command (use `-destination id=$SIM_UDID`). The
# device is shut down on exit only when a wrapper booted it and no other live
# wrapper holds it; Simulator.app is quit only when nothing is booted. See
# scripts/sim_session.py for the contract and exit codes (69 here: no Python
# 3.11+ on the host). Never `open -a Simulator`; close what you open.
# Rollback: remove the call site; state is small JSON under ~/.cache/graph-engineering/sims.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
# shellcheck source=../hooks/scripts/python-runtime.sh
. "$here/../hooks/scripts/python-runtime.sh"
ge_python_runtime || exit 69
exec "$GE_PYTHON" "$here/sim_session.py" "$@"
