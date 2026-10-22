# Onboarding

Matrix: `docs/ops/access.yaml`. Check it with `<doctor command>` (add `--live` to probe each access).

## Day 0

1. <Get added to the repo and to the access group: who adds you, how to ask.>
2. <Install the toolchain: one line per tool.>
3. Run `<doctor command> --live`. Every row you are meant to hold shows ok; a failing row names how to request it.

## What you can do

<One line per capability row you hold, from the matrix.>

## What goes through pipelines

<One line per pipeline: workflow name, what it does, how to dispatch it. No schedule triggers.>

## Owner-only

<The rows marked `owner_only` and why. Ask the owner; do not work around them.>

## Offboarding

1. Remove the person from <access group>.
2. Revoke <anything granted outside the group>.
3. Rotate <any vault secret they could read>.
