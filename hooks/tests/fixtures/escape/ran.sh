#!/bin/sh
# Leaves a marker if it is ever executed. This project is the ANCESTOR of the
# session's project directory: reaching it means the upward walk left the bound.
touch "$1"
exit 1
