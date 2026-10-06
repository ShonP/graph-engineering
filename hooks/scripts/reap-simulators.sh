#!/usr/bin/env bash
#
# Stop and SubagentStop hook: start scripts/sim-reaper.sh detached and return.
# Registered `async`, and the reaper is double-backgrounded with every
# descriptor redirected, so the hook costs a fork and never holds a turn open.
#
#   - GRAPH_SIM_REAPER=off: nothing starts (owner kill switch, no deploy).
#   - No xcrun on PATH (not a Mac, no Xcode): nothing starts.
#   - Otherwise the reaper shuts down only simulators a wrapper booted and no
#     live lease or running build holds, then quits an idle Simulator.app
#     (rules in scripts/sim_reaper.py), appending what it
#     did to <sim dir>/reaper.log; the log rolls to reaper.log.1 past 1 MB.
#
# Prints nothing and exits 0 on every path.

set -u
cat >/dev/null 2>&1
[ "${GRAPH_SIM_REAPER:-on}" = off ] && exit 0
command -v xcrun >/dev/null 2>&1 || exit 0

PLUGIN_ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)" || exit 0
DIR="${GRAPH_SIM_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/graph-engineering/sims}"
mkdir -p "$DIR" 2>/dev/null || exit 0
LOG="$DIR/reaper.log"
if [ -f "$LOG" ] && [ "$(wc -c <"$LOG" 2>/dev/null || echo 0)" -gt 1048576 ]; then
  mv -f "$LOG" "$LOG.1" 2>/dev/null
fi

( nohup bash "$PLUGIN_ROOT/scripts/sim-reaper.sh" </dev/null >>"$LOG" 2>&1 & ) >/dev/null 2>&1
exit 0
