# infra - render, validate, diff, prove it on a throwaway cluster

For changes whose target is deployment configuration - Helm charts and values,
kustomize overlays, Argo CD applications, plain manifests, gateway and policy
resources, secrets wiring. Application code changes go through `feature` or
`bug`; a change that does both is a `feature` run whose tasks include infra
rows (the impact map and `definition-of-done` classify them).

The research MAP is two nodes, not four: tech (what already exists - a chart
value, an operator feature, an upstream default) and impact (what else renders
from these files, what depends on these resources). The verify leg is qa with
`infra-verification`: render, schema-validate CRDs included, policy, the
rendered diff against base, then apply to a cluster the run creates and
deletes. It never touches a cluster the run did not create.

## node: goal
agent: planner
in: the owner's stated goal
out: .graph/<run>/goal.md (with the research questions for the two nodes below)
gate: no
next: research-tech, research-impact

## node: research-tech
agent: researcher
mode: tech
in: .graph/<run>/goal.md
out: .graph/<run>/research/tech.md (reuse first - an existing chart value, operator feature or upstream default)
gate: no
next: plan

## node: research-impact
agent: researcher
mode: impact
in: .graph/<run>/goal.md, the repo
out: .graph/<run>/research/impact.md (every Application, overlay and chart that renders the touched files; resources that depend on the changed ones; triaged adjacent issues)
gate: no
next: plan

## node: plan
agent: planner
in: .graph/<run>/goal.md, .graph/<run>/research/*.md
out: .graph/<run>/plan.md (tasks with the Infra `definition-of-done` row stamped: rendered diff, validation, rollout order, rollback), .graph/<run>/followups.md, .graph/<run>/research/prior-art.md
gate: yes
next: implement

## node: implement
agent: implementer
in: .graph/<run>/tasks/<n>.md
out: worktree commits, the rendered diff against base in .graph/<run>/qa/infra/rendered.diff, appended rows in .graph/<run>/followups.md
gate: no
next: review, verify

## node: review
agent: reviewer
in: the worktree diff, .graph/<run>/qa/infra/rendered.diff
out: .graph/<run>/findings.json
gate: no
next: fix

## node: verify
agent: qa
skills: [infra-verification]
in: the worktree, the plan's acceptance criteria, the profile's `infra` and `runtime` blocks
out: .graph/<run>/qa.md (one row per recipe step and criterion), .graph/<run>/qa-findings.json, .graph/<run>/qa/infra/
gate: no
next: fix

## node: fix
agent: implementer
in: .graph/<run>/findings.json, .graph/<run>/qa-findings.json, the FAILED rows of .graph/<run>/qa.md
out: worktree commits, appended rows in .graph/<run>/followups.md
gate: no
next: merge

## node: merge
agent: planner
in: the reviewed diff, the gate verdict, .graph/<run>/qa/infra/rendered.diff, .graph/<run>/followups.md
out: .graph/<run>/ledger.md
gate: yes
next: END
