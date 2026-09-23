# shellcheck shell=bash
#
# Unit cases for hooks/scripts/resolve_touched_project.py, the PostToolUse
# security bound. Sourced by run-tests.sh.
#
# The end-to-end cases in cases-posttooluse.sh can only reach one of the three
# guards, because the isfile guard rejects everything the other two would catch.
# These call the functions directly, so each guard is individually load-bearing:
# remove any one of them and a case here fails.

echo
echo "== bound: resolve_touched_project.py"

# resolver_says <expected> <python expression> - runs it with the module imported
# and the sandbox paths available as PROJECT and OUTSIDE.
resolver_says() {
  local label="$1" expected="$2" expression="$3"
  local actual
  actual="$(
    RESOLVER_EXPR="$expression" PROJECT="$FIX/escape/proj" \
      OUTSIDE="$FIX/escape" WS="$FIX/workspace" PY="$FIX/py" python3 -c '
import os
import sys

sys.path.insert(0, os.environ["SCRIPTS_DIR"])
import resolve_touched_project as bound

PROJECT = os.environ["PROJECT"]
OUTSIDE = os.environ["OUTSIDE"]
WS = os.environ["WS"]
PY = os.environ["PY"]
print(eval(os.environ["RESOLVER_EXPR"]))
' 2>&1
  )"
  check "$label" "$expected" "$actual"
}

SCRIPTS_DIR="$HOOKS_DIR/scripts"
export SCRIPTS_DIR

# Guard 1: strict containment. Equality must be rejected, because the project
# root itself would start the walk one level above the root.
resolver_says "is_inside rejects the project root itself" False \
  'bound.is_inside(PROJECT, PROJECT)'
resolver_says "is_inside accepts a path under the project" True \
  'bound.is_inside(PROJECT + "/src/touched.py", PROJECT)'
resolver_says "is_inside rejects a prefix sibling" False \
  'bound.is_inside(PROJECT + "-evil/x.py", PROJECT)'
resolver_says "is_inside rejects an ancestor" False \
  'bound.is_inside(OUTSIDE, PROJECT)'

# Guard 3: the walk never inspects a directory outside the project, whatever
# start point it is handed. OUTSIDE holds a package.json, so a walk that does
# not stop returns it.
resolver_says "the walk refuses a start point above the project" None \
  'bound.find_project_file(OUTSIDE, PROJECT)'
resolver_says "the walk refuses a start point beside the project" None \
  'bound.find_project_file(PROJECT + "-evil", PROJECT)'
resolver_says "the walk stops at the project root" None \
  'bound.find_project_file(PROJECT + "/src", PROJECT)'
resolver_says "the walk still finds a project file inside the bound" \
  "('$FIX/escape/proj/tool', 'package')" \
  'bound.find_project_file(PROJECT + "/tool/nested", PROJECT)'

# Guard 2: the touched path must be a real file. Checked end to end as well.
resolver_says "resolve rejects a directory" None \
  'bound.resolve({"tool_input": {"file_path": PROJECT + "/tool/nested"}}, PROJECT)'
resolver_says "resolve rejects a path that does not exist" None \
  'bound.resolve({"tool_input": {"file_path": PROJECT + "/tool/ghost.ts"}}, PROJECT)'
resolver_says "resolve rejects the project root" None \
  'bound.resolve({"tool_input": {"file_path": PROJECT}}, PROJECT)'
resolver_says "resolve accepts a real file in a nested project" \
  "('$FIX/escape/proj/tool', 'package')" \
  'bound.resolve({"tool_input": {"file_path": PROJECT + "/tool/real.ts"}}, PROJECT)'

# A project file that declares neither `lint` nor `typecheck` is not the project
# that owns the file (ADR 0014 D2). The uv workspace shape puts the three script
# names on the ROOT and ships the member with no entry point at all, so stopping
# at the nearest pyproject.toml means every edit under packages/*/src/ silently
# stops being linted. The walk keeps going until a project file declares one of
# the two, or the project directory is reached.
resolver_says "a project file declaring lint or typecheck is the owner" True \
  'bound.declares_scripts(WS, "pyproject")'
resolver_says "a project file declaring neither is not" False \
  'bound.declares_scripts(WS + "/packages/x", "pyproject")'
resolver_says "the walk passes a scriptless workspace member and lands on the root" \
  "('$FIX/workspace', 'pyproject')" \
  'bound.find_project_file(WS + "/packages/x/src", WS)'
resolver_says "a member's file resolves to the workspace root" \
  "('$FIX/workspace', 'pyproject')" \
  'bound.resolve({"tool_input": {"file_path": WS + "/packages/x/src/touched.py"}}, WS)'
# The other half: walking past the scriptless member must not reach past the
# project bound either. With the member itself as the project, there is no
# scripted ancestor inside the bound, so the answer is nothing at all - NOT the
# workspace root above it.
resolver_says "the walk stops at the bound rather than finding a scripted ancestor" None \
  'bound.find_project_file(WS + "/packages/x/src", WS + "/packages/x")'
# And a project that DOES declare the scripts still resolves to itself: the
# patch must not turn every repo into a walk to its outermost project file.
resolver_says "a project that declares the scripts still resolves to itself" \
  "('$FIX/py', 'pyproject')" \
  'bound.resolve({"tool_input": {"file_path": PY + "/src/touched.py"}}, PY)'
