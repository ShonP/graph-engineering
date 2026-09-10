#!/bin/sh
# TEST STUB, not task. run-tests.sh copies this to <sandbox>/bin/task.
# It implements only the two forms the Stop hook uses, per
# https://taskfile.dev/reference/cli/ ("Command Line Interface Reference | Task"):
#
#   task --list-all --silent   one task name per line, names read from Taskfile.yml
#   task <name>                runs ./stub-scripts/task-<name>.sh
set -eu

case "$*" in
"--list-all --silent" | "--list-all -s" | "-a -s" | "-as")
  exec python3 -c '
import re

with open("Taskfile.yml", encoding="utf-8") as handle:
    lines = handle.read().splitlines()

in_tasks = False
for line in lines:
    if re.match(r"^tasks:\s*$", line):
        in_tasks = True
        continue
    if in_tasks:
        if line and not line[0].isspace():
            break
        found = re.match(r"^  ([A-Za-z0-9_.:-]+):\s*$", line)
        if found:
            print(found.group(1))
'
  ;;
esac

[ "$#" -eq 1 ] || { echo "stub task: unsupported arguments: $*" >&2; exit 64; }
[ -f "./stub-scripts/task-$1.sh" ] || { echo "stub task: no task $1" >&2; exit 64; }
exec sh "./stub-scripts/task-$1.sh"
