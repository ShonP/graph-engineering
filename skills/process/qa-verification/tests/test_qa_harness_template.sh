#!/usr/bin/env bash
# Regression cases for templates/qa-harness.sh, driven by a fixture hooks file.
# Needs git and python3; exits 77 (skipped, the automake convention) when either
# is missing. Writes only inside a mktemp dir.
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)/templates/qa-harness.sh"
command -v git >/dev/null && command -v python3 >/dev/null || { echo "SKIP: git or python3 missing"; exit 77; }
# A hook-run caller may export these; the fixture repo must not inherit them.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ge-harness.XXXXXX")" && WORK="$(cd "$WORK" && pwd -P)" || exit 1
trap 'rm -rf "$WORK"' EXIT
REPO="$WORK/repo"
mkdir -p "$REPO/sub"
git -C "$REPO" init -q || exit 1
printf '.graph/\n' >"$REPO/.gitignore"
git -C "$REPO" add .gitignore
git -C "$REPO" -c user.email=fixture@example.invalid -c user.name=fixture commit -qm base || exit 1
HEAD_SHA="$(git -C "$REPO" rev-parse HEAD)"
REPORT="$REPO/.graph/r1/qa/harness-report.json"
fail=0

# Synthetic fixture: FIXTURE_MODE picks the path; teardown appends the runtime
# instance to $MARK so a case can prove it ran.
cat >"$WORK/hooks.sh" <<'EOF'
ge_setup() {
  echo "setup $GRAPH_RUN_ID"
  GE_RUNTIME_INSTANCE="fixture-$GRAPH_RUN_ID"
  [ "$FIXTURE_MODE" != setup-fails ]
}
ge_checks() {
  ge_case AC-1 sh -c 'echo proof >"$GE_EVIDENCE_DIR/body.txt"'
  [ "$FIXTURE_MODE" = pass ] && return 0
  ge_case AC-2 false
  [ "$FIXTURE_MODE" = checks-exit ] && exit 9
  ge_case AC-3 sh -c 'exit 77'
}
ge_teardown() { echo "$GE_RUNTIME_INSTANCE" >>"$MARK"; }
EOF

run() { # run <cwd> <mode> <run id or -> [root]; sets out and code
  rm -f "$WORK/mark"; rm -rf "$REPO/.graph"
  local id=(env GRAPH_RUN_ID="$3")
  [ "$3" = - ] && id=(env -u GRAPH_RUN_ID)
  out="$(cd "$1" && "${id[@]}" MARK="$WORK/mark" FIXTURE_MODE="$2" \
    GE_HARNESS_HOOKS="$WORK/hooks.sh" bash "$HARNESS" "${4-$REPO}" 2>&1)"
  code=$?
}

check() { # check <label> <condition...>
  if "${@:2}"; then echo "ok   $1"; else
    echo "FAIL $1 (exit $code)"; printf '%s\n' "$out" | sed 's/^/     /'; fail=1
  fi
}

report_is() { # report_is <exit_code> <executed> <skipped> <dirty: null|hex> <id:STATUS>...
  python3 - "$REPORT" "$HEAD_SHA" "$REPO" "$@" <<'PY'
import json, os, re, sys
path, head, repo, code, executed, skipped, dirty, *cases = sys.argv[1:]
doc = json.load(open(path, encoding="utf-8"))
assert set(doc) == {"run_id", "candidate", "runtime_instance", "cases",
                    "executed", "skipped", "exit_code"}, sorted(doc)
assert doc["run_id"] == "r1", doc["run_id"]
assert doc["candidate"]["revision"] == head, doc["candidate"]
got = doc["candidate"]["dirty_sha256"]
assert (got is None) if dirty == "null" else bool(re.fullmatch(r"[0-9a-f]{64}", got or "")), got
assert doc["runtime_instance"] == "fixture-r1", doc["runtime_instance"]
assert [f'{c["id"]}:{c["status"]}' for c in doc["cases"]] == cases, doc["cases"]
for c in doc["cases"]:
    assert c["evidence"] == f'.graph/r1/qa/{c["id"]}', c
    assert os.path.isfile(os.path.join(repo, c["evidence"], "output.log")), c
assert [doc["exit_code"], doc["executed"], doc["skipped"]] == [int(code), int(executed), int(skipped)], doc
PY
}

torn_down() { [ "$(cat "$WORK/mark" 2>/dev/null)" = fixture-r1 ]; }
untouched() { [ ! -e "$WORK/mark" ] && [ ! -e "$REPO/.graph" ]; }

# 1. The report is valid JSON with every case, its status and its evidence.
run "$REPO" mixed r1
check "report lists each case with status and evidence" \
  report_is 1 2 1 null AC-1:VERIFIED AC-2:FAILED AC-3:BLOCKED
check "a FAILED case exits 1" test "$code" = 1
check "case evidence is written in its folder" test -s "$REPO/.graph/r1/qa/AC-1/body.txt"
run "$REPO" pass r1
check "all VERIFIED exits 0" report_is 0 1 0 null AC-1:VERIFIED
touch "$REPO/untracked.txt"
run "$REPO" pass r1
check "an untracked file makes the candidate dirty" report_is 0 1 0 hex AC-1:VERIFIED
rm -f "$REPO/untracked.txt"

# 2. Teardown runs on every exit, including failed checks and failed setup.
run "$REPO" mixed r1
check "teardown ran after failing checks" torn_down
run "$REPO" checks-exit r1
check "teardown ran when checks exit early" torn_down
check "an early exit still reports what ran" report_is 1 2 0 null AC-1:VERIFIED AC-2:FAILED
run "$REPO" setup-fails r1
check "teardown ran after a failed setup" torn_down
check "a failed setup reports incomplete (exit 3)" report_is 3 0 0 null

# 3. No GRAPH_RUN_ID (or an unsafe one): refused, nothing started.
run "$REPO" pass -
check "refuses without GRAPH_RUN_ID" test "$code" = 2
check "nothing ran without GRAPH_RUN_ID" untouched
check "the refusal names GRAPH_RUN_ID" grep -q GRAPH_RUN_ID <<<"$out"
run "$REPO" pass ../escape
check "refuses a GRAPH_RUN_ID that is not a plain name" test "$code" = 2
check "nothing ran with an unsafe GRAPH_RUN_ID" untouched

# 4. Outside the candidate worktree root: refused, nothing started.
run "$REPO/sub" pass r1
check "refuses a working directory below the root" test "$code" = 2
check "nothing ran below the root" untouched
run "$REPO/sub" pass r1 "$REPO/sub"
check "refuses a root that is not the worktree top level" test "$code" = 2
run "$WORK" pass r1 "$WORK"
check "refuses a directory that is not a git worktree" test "$code" = 2
check "nothing ran outside a worktree" untouched

exit $fail
