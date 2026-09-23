# bug - reproduce, root-cause, find the siblings, fix them all

The spec's bug graph (§5.2) was reproduce -> diagnose -> fix -> review ->
verify -> merge. This version keeps its agents and its `compose:` of
`superpowers:systematic-debugging`, and adds three things it lacked: the
reproduction is a **failing test** before anyone touches code, a **sibling
search** looks for the same bug shape elsewhere before the fix is planned, and
qa re-runs the reproduction against the running stack beside review.

No research MAP and no UX branch: a bug's prior art is its own reproduction.
The plan node gates, like every playbook's first code-moving decision: the
owner sees the triage pick, the root cause, the siblings and any scout-budget
fixes before a line of product code changes. By then reproduce, diagnose and
sibling search have run, so the gate is cheap to answer.

## node: report
agent: planner
in: the owner's bug report (text, issue, logs, stack trace)
out: .graph/<run>/report.md (symptom, expected, environment, severity, the smallest suspected entry points)
gate: no
next: reproduce

## node: reproduce
agent: qa
in: .graph/<run>/report.md, the profile's `runtime` block
out: a failing automated test in the worktree that reproduces the symptom through the public surface (Bruno request, Playwright spec, or an integration test), .graph/<run>/repro.md (the command, and its failing output)
gate: no
next: diagnose

## node: diagnose
agent: implementer
compose: superpowers:systematic-debugging
in: .graph/<run>/repro.md, the failing test
out: .graph/<run>/root-cause.md (the mechanism, the evidence that proves it, the bug's SHAPE as a searchable pattern) - no fix yet
gate: no
next: sibling-search

## node: sibling-search
agent: researcher
mode: impact
in: .graph/<run>/root-cause.md
out: .graph/<run>/research/impact.md (the blast radius of the fix plus the sibling-search hits, each triaged per `impact-map`)
gate: no
next: plan

## node: plan
agent: planner
in: .graph/<run>/report.md, .graph/<run>/root-cause.md, .graph/<run>/research/impact.md
out: .graph/<run>/plan.md (the fix task, one task per must-fix sibling, in-budget fix-in-PR tasks, `definition-of-done` rows stamped), .graph/<run>/followups.md
gate: yes
next: implement

## node: implement
agent: implementer
in: .graph/<run>/tasks/<n>.md, the failing test
out: worktree commits (the reproduction test now passes; a regression test per fixed sibling), appended rows in .graph/<run>/followups.md
gate: no
next: review, qa

## node: review
agent: reviewer
in: the worktree diff, .graph/<run>/root-cause.md
out: .graph/<run>/findings.json
gate: no
next: fix

## node: qa
agent: qa
in: the worktree, .graph/<run>/repro.md, the plan's acceptance criteria, the profile's `runtime` block
out: .graph/<run>/qa.md (the reproduction now passes on the running stack, plus every criterion), .graph/<run>/qa-findings.json, .graph/<run>/qa/
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
in: the reviewed diff, the gate verdict, .graph/<run>/plan.md, .graph/<run>/root-cause.md, .graph/<run>/followups.md
out: .graph/<run>/ledger.md
gate: yes
next: END
