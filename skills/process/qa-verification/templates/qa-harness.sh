#!/usr/bin/env bash
# Skeleton acceptance harness for a profile's `runtime.command`, implementing
# qa-verification's references/harness-contract.md. Copy it into the repo
# unchanged; everything app-specific (stack, readiness, seeds, login,
# throwaway users, their cleanup) goes in the hooks file, not here.
#
#   GRAPH_RUN_ID=<run id> GE_HARNESS_HOOKS=<hooks file> bash qa-harness.sh "$PWD"
#
# The hooks file is sourced into this shell (under set -uo pipefail) and
# defines three functions:
#   ge_setup     stand the stack up, wait for readiness, seed isolated
#                fixtures; may set GE_RUNTIME_INSTANCE (default ge-<run id>)
#   ge_checks    one `ge_case <case-id> <command...>` per acceptance case
#   ge_teardown  remove everything ge_setup made; runs on every exit
# A case command runs in a subshell at the root with GE_EVIDENCE_DIR set to
# .graph/<run>/qa/<case-id>/ (emptied first); exit 0 = VERIFIED,
# 77 = BLOCKED, anything else = FAILED. The report is
# .graph/<run>/qa/harness-report.json.
# Exit: 0 every case VERIFIED, 1 a case FAILED, 2 refused (nothing started),
# 3 incomplete (a BLOCKED case, failed setup, aborted checks, failed teardown,
# duplicate or invalid case ids, or no cases).
set -uo pipefail

refuse() { echo "qa-harness: refused: $*" >&2; exit 2; }
ID_RE='^[A-Za-z0-9][A-Za-z0-9._-]*$'

[ -n "${GRAPH_RUN_ID:-}" ] || refuse "GRAPH_RUN_ID is required"
[[ $GRAPH_RUN_ID =~ $ID_RE ]] || refuse "GRAPH_RUN_ID must match $ID_RE"
[ $# -eq 1 ] || refuse "usage: qa-harness.sh <candidate worktree root>"
ROOT="$(cd "$1" 2>/dev/null && pwd -P)" || refuse "no such directory: $1"
if ! top="$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null)" || ! top="$(cd "$top" && pwd -P)"; then
  refuse "not a git worktree: $ROOT"
fi
[ "$top" = "$ROOT" ] || refuse "$ROOT is not the worktree root ($top)"
[ "$(pwd -P)" = "$ROOT" ] || refuse "run from the candidate root $ROOT, not $(pwd -P)"
REVISION="$(git rev-parse --verify -q HEAD)" || refuse "no commit at HEAD"
HOOKS="${GE_HARNESS_HOOKS:-}"
[ -n "$HOOKS" ] && [ -f "$HOOKS" ] || refuse "GE_HARNESS_HOOKS must name the hooks file"
# shellcheck source=/dev/null
. "$HOOKS" || refuse "hooks file failed to load: $HOOKS"
for fn in ge_setup ge_checks ge_teardown; do
  declare -F "$fn" >/dev/null || refuse "hooks file does not define $fn"
done

# Candidate identity, taken before setup can write anything: the uncommitted
# diff plus untracked files, minus the run directory. null when clean.
DIRTY="$(python3 - <<'PY'
import hashlib, os, subprocess
spec = ["--", ".", ":(exclude).graph"]
git = lambda *a: subprocess.run(["git", *a], check=True, capture_output=True).stdout
diff = git("diff", "--binary", "HEAD", *spec)
new = sorted(p for p in git("ls-files", "-z", "-o", "--exclude-standard", *spec).split(b"\0") if p)
if not diff and not new:
    print("null")
else:
    h = hashlib.sha256(diff)
    for p in new:
        h.update(b"\0" + p + b"\0")
        h.update(os.readlink(p).encode() if os.path.islink(p) else open(p, "rb").read())
    print(h.hexdigest())
PY
)" || refuse "could not hash the working tree"

QA_DIR="$ROOT/.graph/$GRAPH_RUN_ID/qa"
mkdir -p "$QA_DIR" || refuse "cannot create $QA_DIR"
CASES="$(mktemp "${TMPDIR:-/tmp}/ge-qa-cases.XXXXXX")" || refuse "mktemp failed"
GE_RUNTIME_INSTANCE="ge-$GRAPH_RUN_ID"
invalid=0 stage=setup finished=0

ge_case() { # ge_case <case-id> <command...>
  local id="${1:-}" dir rc status
  shift || true
  if ! [[ $id =~ $ID_RE ]] || [ $# -eq 0 ]; then
    echo "qa-harness: invalid case '$id' (needs an id matching $ID_RE and a command)" >&2
    invalid=1; return 0
  fi
  dir="$QA_DIR/$id"
  if ! { rm -rf -- "$dir" && mkdir -p -- "$dir"; }; then invalid=1; return 0; fi
  (cd "$ROOT" && export GE_EVIDENCE_DIR="$dir" GE_CASE_ID="$id" && "$@") >"$dir/output.log" 2>&1
  rc=$?
  case $rc in 0) status=VERIFIED ;; 77) status=BLOCKED ;; *) status=FAILED ;; esac
  printf '%s\t%s\t%s\n' "$id" "$status" ".graph/$GRAPH_RUN_ID/qa/$id" >>"$CASES"
}

on_exit() {
  local teardown=0 code
  [ "$finished" = 0 ] || return
  finished=1
  trap '' INT TERM # a second Ctrl-C must not skip the cleanup
  ( ge_teardown ) >"$QA_DIR/teardown.log" 2>&1 || teardown=$?
  [ "$teardown" = 0 ] || echo "qa-harness: ge_teardown failed ($teardown), see $QA_DIR/teardown.log" >&2
  code="$(python3 - "$CASES" "$QA_DIR/harness-report.json" "$GRAPH_RUN_ID" "$REVISION" \
    "$DIRTY" "$GE_RUNTIME_INSTANCE" "$stage" "$invalid" "$teardown" <<'PY'
import json, os, sys
cases_path, report, run_id, revision, dirty, instance, stage, invalid, teardown = sys.argv[1:]
cases = []
for line in open(cases_path, encoding="utf-8"):
    cid, status, evidence = line.rstrip("\n").split("\t")
    cases.append({"id": cid, "status": status, "evidence": evidence})
executed = sum(c["status"] != "BLOCKED" for c in cases)
ids = [c["id"] for c in cases]
if any(c["status"] == "FAILED" for c in cases):
    code = 1
elif (executed < len(cases) or not cases or stage != "complete" or invalid != "0"
      or teardown != "0" or len(set(ids)) != len(ids)):
    code = 3
else:
    code = 0
doc = {"run_id": run_id, "candidate": {"revision": revision,
       "dirty_sha256": None if dirty == "null" else dirty},
       "runtime_instance": instance, "cases": cases, "executed": executed,
       "skipped": len(cases) - executed, "exit_code": code}
with open(report + ".tmp", "w", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=2)
    fh.write("\n")
os.replace(report + ".tmp", report)
print(code)
PY
)" || { echo "qa-harness: could not write the report" >&2; code=3; }
  rm -f "$CASES"
  echo "qa-harness: report $QA_DIR/harness-report.json (exit $code)"
  exit "$code"
}

trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if ge_setup >"$QA_DIR/setup.log" 2>&1; then
  stage=checks
  ge_checks && stage=complete
else
  echo "qa-harness: ge_setup failed, see $QA_DIR/setup.log" >&2
fi
exit 0 # on_exit decides the real exit code
