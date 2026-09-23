#!/usr/bin/env bash
# Runs the regression tests that ship beside skill scripts:
# skills/**/tests/test_*.py (stdlib unittest) and skills/**/tests/test_*.sh.
# Exit 77 from a test means its prerequisites are missing: reported as SKIP,
# never as ok, so a green run cannot hide a test that did not run.
#   bash scripts/check-skill-scripts.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail=0; n=0
while IFS= read -r t; do
  n=$((n + 1))
  case "$t" in
    *.py) python3 "$t" >/dev/null 2>"${TMPDIR:-/tmp}/ge-skill-test.log" ;;
    *.sh) bash "$t" >"${TMPDIR:-/tmp}/ge-skill-test.log" 2>&1 ;;
  esac
  rc=$?
  if [ $rc -eq 0 ]; then echo "ok   ${t#"$ROOT"/}"; elif [ $rc -eq 77 ]; then echo "SKIP ${t#"$ROOT"/} ($(head -1 "${TMPDIR:-/tmp}/ge-skill-test.log"))"; else echo "FAIL ${t#"$ROOT"/}"; sed 's/^/     /' "${TMPDIR:-/tmp}/ge-skill-test.log"; fail=1; fi
done < <(find "$ROOT/skills" -path '*/tests/test_*' \( -name '*.py' -o -name '*.sh' \) | sort)
rm -f "${TMPDIR:-/tmp}/ge-skill-test.log"
[ "$n" -gt 0 ] || { echo "no skill tests found" >&2; exit 1; }
exit $fail
