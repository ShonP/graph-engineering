#!/usr/bin/env bash
# Regression cases for check-no-literal-colours.sh. Needs node; exits 77
# (skipped, the automake convention) when it is missing. Writes only inside a
# mktemp dir. The bad fixture's expected.txt is compared exactly, so a missed
# colour and a false positive both fail.
set -uo pipefail

TESTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CHECK="$TESTS/../scripts/check-no-literal-colours.sh"
FIX="$TESTS/fixtures"
command -v node >/dev/null 2>&1 || { echo "SKIP: node missing"; exit 77; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-colours.XXXXXX")" || exit 1
trap 'rm -rf "$WORK"' EXIT
fail=0

expect() { # expect <label> <expected exit> <actual exit> <output> [expected output]
  if [ "$3" = "$2" ] && { [ $# -lt 5 ] || [ "$4" = "$5" ]; }; then
    echo "ok   $1"
  else
    echo "FAIL $1 (exit $3, expected $2)"; printf '%s\n' "$4" | sed 's/^/     got: /'
    [ $# -lt 5 ] || diff <(printf '%s\n' "$5") <(printf '%s\n' "$4") | sed 's/^/     /'
    fail=1
  fi
}

out="$(cd "$FIX" && bash "$CHECK" good/preset.css good 2>&1)"; code=$?
expect "good tree is clean (preset exempt, no false positives)" 0 "$code" "$out" ""

out="$(cd "$FIX" && bash "$CHECK" good/preset.css bad 2>&1 | sort)"; code=${PIPESTATUS[0]}
expect "bad tree reports every violation and nothing else" 1 "$code" "$out" "$(sort "$FIX/bad/expected.txt")"

out="$(cd "$FIX" && bash "$CHECK" good/preset.css bad/Palette.tsx 2>&1 | head -1)"; code=${PIPESTATUS[0]}
expect "a single file argument is scanned" 1 "$code" "$out" "bad/Palette.tsx:2: text-white"

out="$(cd "$FIX" && bash "$CHECK" good/preset.css "good bad" 2>&1)"; code=$?
expect "an unsplit path list is an error, not a vacuous pass" 2 "$code" "$out"

if command -v zsh >/dev/null 2>&1; then
  out="$(cd "$FIX" && zsh -c 'SRC="good bad"; bash "$1" good/preset.css $SRC' _ "$CHECK" 2>&1)"; code=$?
  expect "zsh unsplit \$SRC fails loudly" 2 "$code" "$out"
fi

printf '@theme { --text-body: 1rem; }\n' > "$WORK/empty.css"
out="$(cd "$FIX" && bash "$CHECK" "$WORK/empty.css" good 2>&1)"; code=$?
expect "a preset with no --color-* tokens is an error" 2 "$code" "$out"

mkdir -p "$WORK/none" && printf 'x\n' > "$WORK/none/README.md"
out="$(bash "$CHECK" "$FIX/good/preset.css" "$WORK/none" 2>&1)"; code=$?
expect "a path with nothing to scan is an error" 2 "$code" "$out"

out="$(bash "$CHECK" "$FIX/good/preset.css" 2>&1)"; code=$?
expect "no path argument is an error" 2 "$code" "$out"

mkdir -p "$WORK/tree/node_modules/x" "$WORK/tree/dist" "$WORK/tree/src"
printf 'export const a = "bg-red-500";\n' > "$WORK/tree/node_modules/x/index.tsx"
printf 'export const a = "#fff";\n' > "$WORK/tree/dist/index.js"
printf 'export const a = "bg-fg";\n' > "$WORK/tree/src/a.tsx"
out="$(bash "$CHECK" "$FIX/good/preset.css" "$WORK/tree" 2>&1)"; code=$?
expect "node_modules and dist are skipped" 0 "$code" "$out" ""

exit $fail
