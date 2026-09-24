#!/usr/bin/env bash
# No literal colour outside the Tailwind token preset.
#
#   bash check-no-literal-colours.sh <preset.css> <path>...
#
# <preset.css> is the one file allowed to hold colour values: its `--color-*`
# declarations are the token list, and it is skipped when a <path> contains it.
# Each <path> is a file or a directory (walked; node_modules, dist, build,
# .next, .turbo, coverage and .git skipped). Scans *.{ts,tsx,js,jsx,mts,cts,
# mjs,cjs,css}.
#
# Prints one `file:line: match` per violation. Exit 0 clean, 1 on any
# violation, 2 on a usage error - a missing path, a preset with no colour
# token, or nothing to scan - so a mis-split path list can never pass.
#
# Paths are arguments, never a word-split variable: zsh does not split
# `$SRC`, and a check fed one path named "apps packages" must fail, not pass.
# The rules live in check-no-literal-colours.mjs beside this file. Needs
# Node >= 20 (Tailwind 4's floor) - node is a given in any repo that runs
# Tailwind.
set -euo pipefail
command -v node >/dev/null 2>&1 || { echo "check-no-literal-colours: node is required" >&2; exit 2; }
exec node "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/check-no-literal-colours.mjs" "$@"
