#!/bin/sh
# Stands in for the commands the real `task test` would run.
touch RAN_TASK_TEST
[ -f PASS ] && exit 0
echo "task: [test] 1 failed" >&2
exit 1
