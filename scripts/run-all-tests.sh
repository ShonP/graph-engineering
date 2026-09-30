#!/usr/bin/env bash
# Run every regression suite and check in this repo, in order, past failures.
#
# Discovery is by convention, so a new suite needs no edit here:
#   - hooks/tests: run-tests.sh, then unittest discovery of test_*.py
#   - each directory under tests/ holding a test_*.py: unittest discovery under
#     `uv run`, with one --with per dependency pinned in the PEP 723 block of
#     scripts/graph-control.py (the same pins the controls ship with), plus
#     --with-requirements <dir>/requirements.txt when the directory has one
#     (pins only its tests need, such as wcmatch for the template's globs)
#   - every tests/**/test_*.sh via bash; exit 77 means skipped (the automake
#     convention the skill tests use), reported, never counted as a pass
#   - the check scripts (skill tests, skill and agent frontmatter, routing)
#
# Prints `<step>: exit=<n>` per step, then
# `run-all-tests: exit=<0|1> complete`, or `partial` when a step was skipped or
# reported skipped tests (unittest `skipped=N`, run-tests.sh `skipped: N`, a
# check script's `SKIP` line): a skipUnless on a missing dependency is coverage
# that did not run.
#   bash scripts/run-all-tests.sh
# Exit 1 when any step failed, 0 otherwise.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT" || exit 1
fail=0
skipped=0

LOG="$(mktemp "${TMPDIR:-/tmp}/ge-run-all.XXXXXX")" || exit 1
trap 'rm -f "$LOG"' EXIT

step() { # step <name> <command...>
  local name="$1" rc note=""
  shift
  echo "--- $name"
  "$@" </dev/null 2>&1 | tee "$LOG"
  rc=${PIPESTATUS[0]}
  if grep -Eq '(^|[(, ])skipped(=|: )[1-9]|^SKIP ' "$LOG"; then
    note=" (tests skipped)"
    skipped=1
  fi
  if [ "$rc" -eq 77 ]; then
    echo "$name: exit=77 (skipped)"
    skipped=1
  else
    echo "$name: exit=$rc$note"
    [ "$rc" -eq 0 ] || fail=1
  fi
}

with_deps=()
while IFS= read -r dep; do
  [ -n "$dep" ] && with_deps+=(--with "$dep")
done < <(python3 - scripts/graph-control.py <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"^# dependencies = \[(.*)\]$", text, re.M)
for dep in (m.group(1).split(",") if m else []):
    dep = dep.strip().strip("'\"")
    if dep:
        print(dep)
PY
)

step hooks/tests/run-tests.sh bash hooks/tests/run-tests.sh
step hooks/tests python3 -m unittest discover -s hooks/tests -p 'test_*.py'

for dir in tests/*/; do
  dir="${dir%/}"
  [ -n "$(find "$dir" -name 'test_*.py' -print -quit)" ] || continue
  dir_deps=()
  [ -f "$dir/requirements.txt" ] && dir_deps=(--with-requirements "$dir/requirements.txt")
  step "$dir" uv run ${with_deps[@]+"${with_deps[@]}"} ${dir_deps[@]+"${dir_deps[@]}"} \
    python -m unittest discover -s "$dir" -p 'test_*.py'
done

while IFS= read -r t; do
  step "$t" bash "$t"
done < <(find tests -name 'test_*.sh' -type f | sort)

step check-skill-scripts bash scripts/check-skill-scripts.sh
step check-skill-frontmatter bash scripts/check-skill-frontmatter.sh "$ROOT"
step check-routing-resolves bash scripts/check-routing-resolves.sh "$ROOT"
step check-agent-frontmatter bash scripts/check-agent-frontmatter.sh "$ROOT"

word=complete
[ "$skipped" -eq 0 ] || word=partial
echo "run-all-tests: exit=$fail $word"
exit "$fail"
