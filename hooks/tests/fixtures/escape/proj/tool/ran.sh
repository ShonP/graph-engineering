#!/bin/sh
# Leaves a marker naming its argv. This project is legitimately inside the
# session project, so a real file under it SHOULD be linted.
printf '%s\n' "$@" > "$1"
exit 1
