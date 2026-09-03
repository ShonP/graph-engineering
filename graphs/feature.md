# feature - reduced walking skeleton

The full feature graph in the spec adds a UX design branch, a qa leg beside
review, and a launch tail. This reduced form is deliberately the smallest graph
that still proves the engine works: a gate that actually stops, a parallel MAP
(the three research nodes share `next: plan`), a dispatch that carries
spine-named skills, a review that ranks, and a fix loop. The research MAP is
here because `prior-art` is a house rule: no run plans from priors.

Later phases add the missing nodes. Nothing here changes when they do, because
the engine reads whatever playbook it is given.

## node: goal
agent: planner
in: the owner's stated goal
out: .graph/<run>/goal.md (with the research questions for the three nodes below)
gate: no
next: research-ux, research-tech, research-competitor

## node: research-ux
agent: researcher
mode: ux
in: .graph/<run>/goal.md
out: .graph/<run>/research/ux.md
gate: no
next: plan

## node: research-tech
agent: researcher
mode: tech
in: .graph/<run>/goal.md
out: .graph/<run>/research/tech.md (reuse candidates first - existing skills, plugins, libraries)
gate: no
next: plan

## node: research-competitor
agent: researcher
mode: competitor
in: .graph/<run>/goal.md
out: .graph/<run>/research/competitor.md
gate: no
next: plan

## node: plan
agent: planner
in: .graph/<run>/goal.md, .graph/<run>/research/*.md
out: .graph/<run>/plan.md, .graph/<run>/research/prior-art.md
gate: yes
next: implement

## node: implement
agent: implementer
in: .graph/<run>/tasks/<n>.md
out: worktree commits
gate: no
next: review

## node: review
agent: reviewer
in: the worktree diff
out: .graph/<run>/findings.json
gate: no
next: fix

## node: fix
agent: implementer
in: .graph/<run>/findings.json
out: worktree commits
gate: no
next: merge

## node: merge
agent: planner
in: the reviewed diff and the gate verdict
out: .graph/<run>/ledger.md
gate: yes
next: END
