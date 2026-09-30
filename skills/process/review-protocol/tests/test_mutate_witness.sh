#!/usr/bin/env bash
# Regression cases for mutate-witness.sh (AC-W4-MW-01..05). Needs git and
# python3; exits 77 (skipped, the automake convention) when either is missing.
# Writes only inside a mktemp dir: each case builds a throwaway repo there and
# points the script's TMPDIR at an empty directory, so a leaked mutant
# worktree or temp dir fails the case.
set -uo pipefail

MW="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)/scripts/mutate-witness.sh"
{ command -v git && command -v python3; } >/dev/null 2>&1 || { echo "SKIP: git or python3 missing"; exit 77; }
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-mw-test.XXXXXX")" && WORK="$(cd "$WORK" && pwd -P)" || exit 1
trap 'rm -rf "$WORK"' EXIT
REPO="$WORK/repo" SCRATCH="$WORK/tmp" RECEIPT="$WORK/out/deep/receipt.json"
fail=0 errs=""

note() { errs="$errs$1"$'\n'; }
verdict() { # verdict <label>: prints ok/FAIL from the notes gathered since the last verdict
  if [ -z "$errs" ]; then echo "ok   $1"; else echo "FAIL $1"; printf '%s' "$errs" | sed 's/^/     /'; fail=1; fi
  errs=""
}

fresh() { # a committed repo holding a guard and the test that should witness it
  rm -rf "$REPO" "$SCRATCH" "$WORK/out" "$WORK/hang.pid"; mkdir -p "$REPO/sub" "$SCRATCH"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@example.invalid
  git -C "$REPO" config user.name t
  git -C "$REPO" config commit.gpgsign false
  printf '%s\n' '#!/bin/sh' 'qty="$1"' 'if [ "$qty" -le 0 ]; then echo rejected; exit 1; fi' 'echo ok' > "$REPO/guard.sh"
  printf '%s\n' 'sh guard.sh 0 >/dev/null && exit 1' 'sh guard.sh 5 >/dev/null || exit 1' 'exit 0' > "$REPO/test_guard.sh"
  printf 'keep\n' > "$REPO/sub/.keep"
  git -C "$REPO" add -A && git -C "$REPO" commit -qm base
  WT_BEFORE="$(git -C "$REPO" worktree list --porcelain)"
}

mw() { # mw <args...>: run the script from the repo root with the scratch TMPDIR
  out="$(cd "$REPO" && TMPDIR="$SCRATCH" bash "$MW" "$@" 2>&1)"; code=$?
}

field() { python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))[sys.argv[2]]))' "$RECEIPT" "$1"; }

expect_code() { [ "$code" = "$1" ] || note "exit $code, expected $1: $out"; }
expect_out() { grep -qF -- "$1" <<<"$out" || note "output lacks '$1': $out"; }
expect_field() { local got; got="$(field "$1" 2>/dev/null)"; [ "$got" = "$2" ] || note "receipt $1 = $got, expected $2"; }
expect_no_receipt() { [ ! -e "$RECEIPT" ] || note "a receipt was written"; }

unchanged() { # the main tree, its worktree list and the scratch TMPDIR are as before
  git -C "$REPO" diff --quiet || note "git diff is not quiet"
  [ "$(git -C "$REPO" status --porcelain)" = "${1:-}" ] || note "porcelain changed: $(git -C "$REPO" status --porcelain)"
  [ "$(git -C "$REPO" worktree list --porcelain)" = "$WT_BEFORE" ] || note "worktree list changed"
  [ -z "$(ls -A "$SCRATCH")" ] || note "left behind in TMPDIR: $(ls -A "$SCRATCH")"
}

hang_test() { # a test that parks on the HANG mutant and passes otherwise
  printf '%s\n' 'if grep -q HANG guard.sh; then echo $$ > "$1"; exec sleep 60; fi' 'exec sh test_guard.sh' > "$WORK/hang.sh"
}

# AC-W4-MW-01: a killed mutant gives a receipt and leaves the main tree alone.
fresh
mw --file guard.sh --lines 3-3 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh
expect_code 0; expect_out "killed"
expect_field killed true; expect_field test_exit 1; expect_field file '"guard.sh"'; expect_field lines '"3-3"'
expect_field find '"-le 0"'; expect_field replace '"-lt 0"'; expect_field test '["sh", "test_guard.sh"]'
expect_field head "\"$(git -C "$REPO" rev-parse HEAD)\""
field observed_at | grep -Eq '^"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"$' || note "observed_at is not UTC ISO 8601"
grep -qF -- '-le 0' "$REPO/guard.sh" || note "the main tree's guard was mutated"
unchanged; verdict "AC-W4-MW-01 killed mutant: receipt killed=true, main tree unchanged"

# AC-W4-MW-02: a mutant the test does not notice survives.
fresh
mw --file guard.sh --lines 3-3 --find 'echo rejected' --replace 'echo denied' --receipt "$RECEIPT" -- sh test_guard.sh
expect_code 1; expect_out "survived"; expect_field killed false; expect_field test_exit 0
unchanged; verdict "AC-W4-MW-02 surviving mutant: killed=false, exit 1"

# AC-W4-MW-03: uncommitted changes refuse before anything is created.
fresh
printf '# local edit\n' >> "$REPO/guard.sh"
mw --file guard.sh --lines 3-3 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh
expect_code 2; expect_out "uncommitted"; expect_no_receipt
unchanged_porcelain="$(git -C "$REPO" status --porcelain)"
[ "$unchanged_porcelain" = " M guard.sh" ] || note "the local edit was touched: $unchanged_porcelain"
tail -1 "$REPO/guard.sh" | grep -qF '# local edit' || note "the local edit was lost"
[ "$(git -C "$REPO" worktree list --porcelain)" = "$WT_BEFORE" ] || note "worktree list changed"
[ -z "$(ls -A "$SCRATCH")" ] || note "a temp dir was created"
verdict "AC-W4-MW-03 modified file refuses with exit 2, nothing created"

fresh
printf 'x\n' > "$REPO/untracked.txt"
mw --file guard.sh --lines 3-3 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh
expect_code 2; expect_out "uncommitted"; expect_no_receipt; unchanged "?? untracked.txt"
verdict "AC-W4-MW-03 untracked file refuses with exit 2, nothing created"

# AC-W4-MW-04: a replacement that changes nothing is refused.
fresh
mw --file guard.sh --lines 3-3 --find '-le 0' --replace '-le 0' --receipt "$RECEIPT" -- sh test_guard.sh
expect_code 2; expect_out "mutation did not change the file"; expect_no_receipt; unchanged
verdict "AC-W4-MW-04 identical replacement: exit 2, mutation did not change the file"

fresh
mw --file guard.sh --lines 1-2 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh
expect_code 2; expect_out "mutation did not change the file"; expect_no_receipt; unchanged
verdict "AC-W4-MW-04 find text outside the line range: exit 2, nothing changed"

# AC-W4-MW-05: SIGTERM while the test runs leaves no worktree, no temp dir, no test process.
fresh; hang_test
(cd "$REPO" && TMPDIR="$SCRATCH" exec bash "$MW" --file guard.sh --lines 4-4 --find 'echo ok' --replace 'echo HANG' \
  --receipt "$RECEIPT" -- sh "$WORK/hang.sh" "$WORK/hang.pid") >/dev/null 2>&1 &
pid=$!
i=0; while [ ! -s "$WORK/hang.pid" ] && [ $i -lt 150 ]; do sleep 0.2; i=$((i + 1)); done
if [ -s "$WORK/hang.pid" ]; then
  kill -TERM "$pid"; wait "$pid"; code=$?
  [ "$code" = 143 ] || note "exit $code after SIGTERM, expected 143"
  ! kill -0 "$(cat "$WORK/hang.pid")" 2>/dev/null || note "the test process outlived the script"
else
  kill -KILL "$pid" 2>/dev/null; note "the mutant test never started"
fi
expect_no_receipt; unchanged; verdict "AC-W4-MW-05 SIGTERM mid-test: no worktree, main tree unchanged"

# A test that is already red on HEAD cannot witness anything.
fresh
mw --file guard.sh --lines 3-3 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh -c 'exit 3'
expect_code 2; expect_out "fails on the unmutated HEAD"; expect_no_receipt; unchanged
verdict "baseline: a test red before mutation is refused, never a kill"

# A hang past --timeout is a kill (exit 124), and the hung process is gone.
fresh; hang_test
mw --file guard.sh --lines 4-4 --find 'echo ok' --replace 'echo HANG' --timeout 2 --receipt "$RECEIPT" -- sh "$WORK/hang.sh" "$WORK/hang.pid"
expect_code 0; expect_field killed true; expect_field test_exit 124
[ -s "$WORK/hang.pid" ] && ! kill -0 "$(cat "$WORK/hang.pid")" 2>/dev/null || note "the timed-out test process is still alive"
unchanged; verdict "timeout: a hung mutant is killed with test_exit 124"

# The test runs in the same subdirectory of the disposable worktree it was invoked from.
fresh
out="$(cd "$REPO/sub" && TMPDIR="$SCRATCH" bash "$MW" --file guard.sh --lines 3-3 --find '-le 0' --replace '-lt 0' \
  --receipt "$RECEIPT" -- sh -c '[ "${PWD##*/}" = sub ] && cd .. && sh test_guard.sh' 2>&1)"; code=$?
expect_code 0; expect_field killed true; unchanged; verdict "cwd: the test runs in the invoking subdirectory"

# An inherited GIT_DIR (a git hook's environment) must not redirect the script.
fresh
git init -q "$WORK/other" && other_before="$(git -C "$WORK/other" worktree list --porcelain)"
out="$(cd "$REPO" && GIT_DIR="$WORK/other/.git" TMPDIR="$SCRATCH" bash "$MW" --file guard.sh --lines 3-3 \
  --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh 2>&1)"; code=$?
expect_code 0; expect_field killed true; unchanged
[ "$(git -C "$WORK/other" worktree list --porcelain)" = "$other_before" ] || note "the GIT_DIR repo was touched"
rm -rf "$WORK/other"; verdict "env: an inherited GIT_DIR is ignored"

# Bad input is refused before a worktree exists.
bad_input() { # bad_input <label> <args...>
  local label="$1"; shift; fresh; mw "$@"
  expect_code 2; expect_no_receipt; unchanged; verdict "input: $label"
}
bad_input "a path outside the repo" --file ../x.sh --lines 1-1 --find a --replace b --receipt "$RECEIPT" -- true
bad_input "an absolute file path" --file "$REPO/guard.sh" --lines 1-1 --find a --replace b --receipt "$RECEIPT" -- true
bad_input "lines past the end" --file guard.sh --lines 3-9 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh
bad_input "a reversed range" --file guard.sh --lines 3-2 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh
bad_input "a relative receipt" --file guard.sh --lines 3-3 --find '-le 0' --replace '-lt 0' --receipt out.json -- sh test_guard.sh
bad_input "no test argv" --file guard.sh --lines 3-3 --find '-le 0' --replace '-lt 0' --receipt "$RECEIPT" --
bad_input "a missing --find" --file guard.sh --lines 3-3 --replace '-lt 0' --receipt "$RECEIPT" -- sh test_guard.sh

exit $fail
