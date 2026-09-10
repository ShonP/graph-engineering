#!/bin/sh
# Leaves a marker if it is ever executed. This directory sits next to `py` and
# shares its name prefix, which is what a prefix-only containment check would
# wrongly accept.
touch "$1"
exit 1
