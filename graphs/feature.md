# feature - reduced walking skeleton

The full feature graph in the spec adds a UX design branch. This reduced form
is deliberately the smallest graph that still proves the engine works: a gate
that actually stops, two parallel MAPs (the three research nodes share
`next: plan`; review and qa share `next: fix`), a dispatch that carries
spine-named skills, a review that ranks, a qa leg that runs the change, and a
fix loop fed by both. The research MAP is here because `prior-art` is a house
rule: no run plans from priors. The qa leg is here because review reads code
and qa runs it; a change nobody ran is not verified.

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
next: review, qa

## node: review
agent: reviewer
in: the worktree diff
out: .graph/<run>/findings.json
gate: no
next: fix

## node: qa
agent: qa
in: the worktree, the plan's acceptance criteria, the profile's `runtime` block
out: .graph/<run>/qa.md (criterion table), .graph/<run>/qa-findings.json (Important findings qa found beside the criteria, e.g. Schemathesis spec drift), .graph/<run>/qa/ (evidence: bru and schemathesis reports, screenshots, query results)
gate: no
next: fix

## node: fix
agent: implementer
in: .graph/<run>/findings.json, .graph/<run>/qa-findings.json, the FAILED rows of .graph/<run>/qa.md
out: worktree commits
gate: no
next: merge

## node: merge
agent: planner
in: the reviewed diff and the gate verdict
out: .graph/<run>/ledger.md
gate: yes
next: END
