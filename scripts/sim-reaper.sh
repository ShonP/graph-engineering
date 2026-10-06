#!/usr/bin/env bash
# Shut down the simulators the wrappers provably abandoned, then quit an idle Simulator.app:
#   sim-reaper.sh [--dry-run] [--idle-minutes N]
# Only a device sim-session.sh booted (it carries a marker) is ever shut down,
# and only when every lease on it is released or unused for N minutes
# (GRAPH_SIM_IDLE_MIN, default 15) and no running xcodebuild, XCTest or simctl
# names it. A device with no marker (the owner's Xcode, XcodeBuildMCP) is never
# touched. See scripts/sim_reaper.py for the rules. A host without xcrun (not a
# Mac, no Xcode) exits 0 before any interpreter starts.
set -u
command -v xcrun >/dev/null 2>&1 || exit 0
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
# shellcheck source=../hooks/scripts/python-runtime.sh
. "$here/../hooks/scripts/python-runtime.sh"
ge_python_runtime 2>/dev/null || exit 0
exec "$GE_PYTHON" "$here/sim_reaper.py" "$@"
