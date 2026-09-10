#!/bin/sh
# Leaves a marker if it is ever executed. Nothing in this project may run: it
# stands in for a clone of somebody else's repo sitting outside the session's
# project directory.
touch "$1"
exit 1
