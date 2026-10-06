#!/usr/bin/env bash
# Shut down simulators no live process owns, then quit an idle Simulator.app:
#   sim-reaper.sh [--dry-run] [--grace-minutes N]
# Never touches a device a live sim-session.sh holds or a running xcodebuild,
# XCTest or simctl names. See scripts/sim_reaper.py for the rules. A host
# without xcrun (not a Mac, no Xcode) exits 0 before any interpreter starts.
set -u
command -v xcrun >/dev/null 2>&1 || exit 0
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
# shellcheck source=../hooks/scripts/python-runtime.sh
. "$here/../hooks/scripts/python-runtime.sh"
ge_python_runtime 2>/dev/null || exit 0
exec "$GE_PYTHON" "$here/sim_reaper.py" "$@"
