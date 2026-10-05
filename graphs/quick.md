# quick

The small-ask playbook, picked by the router in graph-ship step 1: a defined
intent on at most 5 files, or any risk row on a small ask. It keeps what
catches defects on a small change and drops the rest. One planner dispatch
writes the goal and the plan as one exhibit, so the owner reads one page at
one gate. `impact` stays because a small diff still has callers
(`impact-map`); ux and competitor research do not run, and `design` runs only
when the goal has a user-facing surface (`when: ui`). Review reads the change
and qa runs it once for the merge unit, both feeding one fix loop. The engine
writes `goal.md` at intake, renders the merge exhibit itself, and writes the
one-line retro when nothing leaked; none of those is a dispatch.

## node: intake
agent: engine
in: the owner's stated goal, the router's lane line and matched risk rows (graph-ship step 1)
out: .graph/<run>/goal.md (the intent in one paragraph, the files the goal names, the matched risk row ids or `risk: none`, and the `ui: yes|no - <reason>` line that decides whether `design` runs)
gate: no
next: impact, design

## node: impact
agent: researcher
mode: impact
in: .graph/<run>/goal.md, the repo
out: .graph/<run>/research/impact.md (callers, contracts, tests, definition-of-done rows, triaged adjacent issues, per `impact-map`)
gate: no
next: plan

## node: design
agent: ux-designer
when: ui
in: .graph/<run>/goal.md, the running app (the profile's `runtime`)
out: .graph/<run>/design/experience.md at the size `ux-journey`'s scale rule picks, ending in UI acceptance rows
gate: no
next: plan

## node: plan
agent: planner
in: .graph/<run>/goal.md, .graph/<run>/research/impact.md, the experience spec from `design` when it ran
out: .graph/<run>/plan.md (goal and plan as one exhibit: the intent and the lane and risk line on top, then every task stamped with its `definition-of-done` rows and, for UI tasks, the spec's UI acceptance rows), .graph/<run>/plan.json (validated contracts, witnesses and acceptance cases), .graph/<run>/followups.md
gate: yes
next: implement

## node: implement
agent: implementer
in: .graph/<run>/tasks/<n>.md
out: worktree commits, appended rows in .graph/<run>/followups.md
gate: no
next: review, qa

## node: review
agent: reviewer
in: the worktree diff
out: .graph/<run>/findings.<task>.json (one per task)
gate: no
next: fix

## node: qa
agent: qa
in: the worktree, the plan's acceptance criteria, the profile's `runtime` block
out: .graph/<run>/qa.md (criterion table), .graph/<run>/qa-findings.json, .graph/<run>/qa/ (evidence)
gate: no
next: fix

## node: fix
agent: implementer
in: .graph/<run>/findings.<task>.json (one per task), .graph/<run>/qa-findings.json, the FAILED rows of .graph/<run>/qa.md
out: worktree commits, appended rows in .graph/<run>/followups.md
gate: no
next: merge

## node: merge
agent: engine
in: the reviewed diff, the gate verdict, .graph/<run>/followups.md
out: .graph/<run>/merge.md (the exhibit the engine renders per graph-ship step 5, also the PR body), .graph/<run>/ledger.md
gate: yes
next: post-deploy

## node: post-deploy
agent: qa
skills: [post-deploy-verification]
in: the merged change, the profile's `deploy` block
out: .graph/<run>/post-deploy.md (PASS / FAIL with a rollback recommendation / BLOCKED / SKIPPED), .graph/<run>/post-deploy/
gate: no
next: retro

## node: retro
agent: retro
in: the whole run directory
out: .graph/<run>/retro.md (leaks, classes, proposed rule changes as diffs, never applied; the engine writes the one-line fast-path version itself when nothing leaked, per graph-ship step 10)
gate: no
next: END
