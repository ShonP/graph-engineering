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
      OUTSIDE="$FIX/escape" python3 -c '
import os
import sys

sys.path.insert(0, os.environ["SCRIPTS_DIR"])
import resolve_touched_project as bound

PROJECT = os.environ["PROJECT"]
OUTSIDE = os.environ["OUTSIDE"]
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
