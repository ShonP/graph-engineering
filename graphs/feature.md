# feature - reduced walking skeleton

The full feature graph in the spec adds parallel research, a UX design branch, a
qa leg beside review, and a launch tail. This reduced form is deliberately the
smallest graph that still proves the engine works: a gate that actually stops, a
dispatch that carries spine-named skills, a review that ranks, and a fix loop.

Later phases add the missing nodes. Nothing here changes when they do, because
the engine reads whatever playbook it is given.

## node: goal
agent: pm-planner
in: the owner's stated goal
out: .graph/<run>/goal.md
gate: no
next: plan

## node: plan
agent: pm-planner
in: .graph/<run>/goal.md
out: .graph/<run>/plan.md
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
agent: pm-planner
in: the reviewed diff and the gate verdict
out: .graph/<run>/ledger.md
gate: yes
next: END
