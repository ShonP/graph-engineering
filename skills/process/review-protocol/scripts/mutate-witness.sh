#!/usr/bin/env bash
# Mutation witness: prove that a test notices a change to the guard it is named
# for, without ever touching the tree you work in.
#
#   bash mutate-witness.sh --file <repo-relative path> --lines <a-b> \
#     --find <text> --replace <text> --receipt <absolute path> \
#     [--timeout <seconds>] -- <test argv...>
#
# Run it inside the repo with a clean tree: any uncommitted or untracked change
# is refused with exit 2, because the mutant is built from HEAD. It adds a
# disposable `git worktree add --detach` of HEAD under TMPDIR, then:
#   1. runs the test argv there unmutated. A test already red on HEAD would
#      "kill" every mutant (a missing dependency looks the same), so that is
#      refused with exit 2;
#   2. replaces every occurrence of --find inside lines a-b of --file in the
#      disposable copy only (python, not sed, so GNU and BSD hosts agree). No
#      change is exit 2 `mutation did not change the file`;
#   3. runs the test argv again. killed = it exited nonzero; 124 means it ran
#      past --timeout (default 600 s per run) and its process group was killed.
# The test runs in the subdirectory you invoked from. The copy holds tracked
# files only, so fetch or link dependencies inside the argv, for example
#   -- sh -c 'ln -s /abs/repo/node_modules . && npm test -- src/total.test.ts'
# A trap on EXIT, INT and TERM removes the worktree. The script then asserts
# your tree is unchanged (git diff --quiet, same git status --porcelain) and
# writes the --receipt JSON:
#   {file, lines, find, replace, killed, test_exit, head, observed_at, test}
# Exit: 0 killed, 1 survived (strengthen the test), 2 refused or error.
# Pick a replacement that still builds (flip a comparison, drop a condition):
# a kill that is only a syntax or build error proves nothing.
#
# Heavier optional alternatives when a whole-module mutation score is wanted:
# Stryker (JS/TS/C#, `--mutate <file>:<a-b>`, runs in its own sandbox) and
# mutmut (Python). This script stays one targeted mutant in any language.
set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

die() { echo "mutate-witness: $*" >&2; exit 2; }

file="" lines="" find="" replace="" receipt="" timeout=600 have_replace=0
while [ $# -gt 0 ]; do
  case "$1" in
    --file|--lines|--find|--replace|--receipt|--timeout)
      [ $# -ge 2 ] || die "$1 needs a value"
      case "$1" in
        --file) file="$2" ;;
        --lines) lines="$2" ;;
        --find) find="$2" ;;
        --replace) replace="$2"; have_replace=1 ;;
        --receipt) receipt="$2" ;;
        --timeout) timeout="$2" ;;
      esac
      shift 2 ;;
    --) shift; break ;;
    *) die "unknown argument: $1 (usage is in the header of this script)" ;;
  esac
done

[ -n "$file" ] || die "--file is required"
case "$file" in /*) die "--file must be repo-relative: $file" ;; esac
case "/$file/" in */../*) die "--file must stay inside the repo: $file" ;; esac
[[ "$lines" =~ ^([1-9][0-9]*)-([1-9][0-9]*)$ ]] || die "--lines must be <a-b> with 1 <= a <= b"
first="${BASH_REMATCH[1]}" last="${BASH_REMATCH[2]}"
[ "$first" -le "$last" ] || die "--lines must be <a-b> with 1 <= a <= b"
[ -n "$find" ] || die "--find is required and cannot be empty"
[ "$have_replace" = 1 ] || die "--replace is required"
case "$receipt" in /*) ;; *) die "--receipt must be an absolute path" ;; esac
[[ "$timeout" =~ ^[1-9][0-9]*$ ]] || die "--timeout must be a positive number of seconds"
[ $# -gt 0 ] || die "no test command after --"
argv=("$@")
command -v python3 >/dev/null 2>&1 || die "python3 is required"

top="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git work tree"
prefix="$(git rev-parse --show-prefix)" || die "cannot resolve the current directory in the repo"
cd "$top" || die "cannot enter $top"
before="$(git status --porcelain)" || die "git status failed"
[ -z "$before" ] || die "uncommitted changes in $top; commit them first (the mutant is built from HEAD)"
head="$(git rev-parse --verify HEAD 2>/dev/null)" || die "the repo has no HEAD commit"

# The test's own process group, capped at --timeout; killed whole on a signal.
RUNNER='
import os, signal, subprocess, sys
limit, argv = int(sys.argv[1]), sys.argv[2:]
try:
    p = subprocess.Popen(argv, start_new_session=True)
except OSError as e:
    print(f"mutate-witness: cannot run {argv[0]}: {e}", file=sys.stderr)
    sys.exit(127)
def stop():
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass
def on_signal(sig, _frame):
    stop(); p.wait(); sys.exit(128 + sig)
signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)
try:
    rc = p.wait(timeout=limit)
except subprocess.TimeoutExpired:
    stop(); p.wait(); rc = 124
stop()  # nothing the test started outlives it in the disposable tree
sys.exit(rc if rc >= 0 else 128 - rc)
'

# Byte-exact replacement inside lines a-b of a file that must stay in the tree.
MUTATE='
import os, sys
root, rel, first, last, find, repl = sys.argv[1:7]
first, last = int(first), int(last)
def fail(msg):
    print(f"mutate-witness: {msg}", file=sys.stderr); sys.exit(2)
root = os.path.realpath(root)
path = os.path.realpath(os.path.join(root, rel))
if not path.startswith(root + os.sep) or not os.path.isfile(path):
    fail(f"--file is not a regular file inside the repo: {rel}")
with open(path, "rb") as f:
    lines = f.read().splitlines(keepends=True)
if last > len(lines):
    fail(f"--lines {first}-{last} is past the end of {rel} ({len(lines)} lines)")
segment = b"".join(lines[first - 1:last])
mutant = segment.replace(os.fsencode(find), os.fsencode(repl))
if mutant == segment:
    fail("mutation did not change the file")
with open(path, "wb") as f:
    f.write(b"".join(lines[:first - 1]) + mutant + b"".join(lines[last:]))
'

RECEIPT='
import json, os, sys
out, rel, lines, find, repl, killed, rc, head, at = sys.argv[1:10]
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out + ".tmp", "w", encoding="utf-8") as f:
    json.dump({"file": rel, "lines": lines, "find": find, "replace": repl,
               "killed": killed == "1", "test_exit": int(rc), "head": head,
               "observed_at": at, "test": sys.argv[10:]}, f, indent=2)
    f.write("\n")
os.replace(out + ".tmp", out)
'

scratch="$(mktemp -d "${TMPDIR:-/tmp}/ge-mutant.XXXXXX")" && scratch="$(cd "$scratch" && pwd -P)" \
  || die "cannot create a temp dir"
wt="$scratch/${scratch##*/}"
runner=""
cleanup() {
  if [ -n "$runner" ]; then kill -TERM "$runner" 2>/dev/null; wait "$runner" 2>/dev/null; runner=""; fi
  git worktree remove --force "$wt" >/dev/null 2>&1
  rm -rf "$scratch"
  if git worktree list --porcelain | grep -qxF "worktree $wt"; then git worktree prune; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

run_test() { # run_test <log>: sets rc; runs in the background so a signal interrupts wait
  (cd "$wt/$prefix" && exec python3 -c "$RUNNER" "$timeout" "${argv[@]}") >"$1" 2>&1 </dev/null &
  runner=$!
  wait "$runner"; rc=$?
  runner=""
}

git -c core.hooksPath=/dev/null worktree add --detach --quiet "$wt" "$head" >"$scratch/add.log" 2>&1 \
  || die "git worktree add failed: $(cat "$scratch/add.log")"
git -C "$wt" ls-files --error-unmatch -- "$file" >/dev/null 2>&1 || die "--file is not tracked at HEAD: $file"
[ -d "$wt/$prefix" ] || die "the current directory is not in HEAD: $prefix"

run_test "$scratch/baseline.log"
if [ "$rc" -ne 0 ]; then
  tail -n 20 "$scratch/baseline.log" | sed 's/^/  | /' >&2
  die "the test fails on the unmutated HEAD (exit $rc) in the disposable worktree, so a kill would prove nothing"
fi

python3 -c "$MUTATE" "$wt" "$file" "$first" "$last" "$find" "$replace" || exit 2
run_test "$scratch/mutant.log"
test_exit=$rc
observed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
killed=0
if [ "$test_exit" -ne 0 ]; then
  killed=1
  tail -n 15 "$scratch/mutant.log" | sed 's/^/  | /'
fi
cleanup

git diff --quiet && [ "$(git status --porcelain)" = "$before" ] \
  || die "the main tree changed during the run; inspect git status before trusting anything"
python3 -c "$RECEIPT" "$receipt" "$file" "$lines" "$find" "$replace" "$killed" "$test_exit" "$head" \
  "$observed_at" "${argv[@]}" || die "cannot write the receipt: $receipt"

if [ "$killed" = 1 ]; then
  echo "mutate-witness: killed test_exit=$test_exit receipt=$receipt"
  exit 0
fi
echo "mutate-witness: survived test_exit=0 receipt=$receipt (the test does not notice the mutant)"
exit 1
