---
name: retro
description: Use at the end of a playbook run when something leaked past the gate that should have caught it - a review or qa finding, a FAILED row, a post-deploy FAIL, a fix loop past one round, a NEEDS_SETUP or BLOCKED stop, or a defect class that recurs. Proposes changes for the owner; never edits rules on its own.
---

# Retro

Every run produces evidence of where the process leaked: a defect the reviewer
found that the implementer's own tests should have, a qa FAILED row the review
passed, a post-deploy FAIL everything before it passed, a fix loop that needed
three rounds. The retro reads that evidence and turns each leak into one rule
change, so the organisation learns instead of repeating. A guard beats a
prose rule: a guard runs on every change, a prose line has to be read.

Sources: Google SRE, [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)
- blameless by construction, focused on contributing causes and action items
that change the system, not on who.

## Fast path

When nothing leaked (the conditions are the engine's, graph-ship step 10), the
engine writes the one-line `retro.md` itself - `No leaks: <n> review rounds,
<m> qa rows verified` - and the retro agent is not dispatched. Everything below
runs only when something leaked.

## Inputs

- `.graph/<run>/classes.md`: the class of each blocking or important
  finding, appended by the engine after each review or qa round. Absent:
  derive the classes from the findings files.
- `ledger.md` and every round of review and qa output: the engine keeps
  earlier rounds per task as `findings.<task>.r<N>.json` beside each task's
  latest `findings.<task>.json`, and at run level `qa-findings.r<N>.json`
  and `qa.r<N>.md` beside the final `qa-findings.json` and `qa.md`.
- `post-deploy.md` when it exists, `followups.md`, and the implementer
  reports the ledger points to.
- Earlier runs' `.graph/*/retro.md`, for the classes seen before.

## Method

1. **List the leaks.** Every finding or FAILED row, with the node that caught
   it and the earliest node that *should* have (the implementer's tests, the
   plan's acceptance criteria, the reviewer, qa, post-deploy). A leak is any
   gap between the two. Also: fix loops that took more than one round, and
   `NEEDS_SETUP` / `BLOCKED` stops.
2. **Group by class**, not by instance - "authz not checked on a new
   endpoint", not "missing check in orders.py:42". One class, one action.
3. **Ask why the earlier gate missed it**, blamelessly: was the rule missing,
   the rule present but not loaded (routing), the rule loaded but vague, or the
   check impossible at that stage?
4. **Promote guard first**, one change per class. A class that recurs -
   twice or more in this run's `classes.md`, or named in an earlier run's
   `retro.md` - is proposed first as an executable guard, written as a diff
   into the repo, of one of three kinds:
   - a **test fixture**: a failing case of the class in the repo's own tests;
   - a **semgrep rule** in impact-map's `sibling.yaml` shape: `pattern-either`
     for the defect shape, `pattern-not-inside` for its guard;
   - a **lint configuration**: a rule switched on in the repo's linter, or a
     scripted check such as the plugin's `scripts/lint-no-plan-numbers.sh`.

   A first sighting gets a guard too when its class allows one. A prose line
   is only the fallback, for a class no guard can express (say why in one
   line): a rule pack (a path from the profile's `rules`), a routing row or a
   house skill. Precedence is house > vault-generated > community, so a retro
   rule is a house rule.
5. **Retire prose behind guards.** The retro proposes removing a class's prose
   line once its guard lands: in the same diff as the guard, or on its own
   when the guard landed earlier. A rule pack keeps only what no guard checks.
6. **Measure the lint-tier share**: the findings whose class a scripted check
   (test, semgrep rule, lint) could catch, over all findings in every review
   and qa round, any severity, reported as `lint-tier share: <k>/<n> (<pct>%)`.
   A number, never "most".
7. **Write** `.graph/<run>/retro.md`: the leak table, the classes with their
   sighting counts, the lint-tier share line, and the proposed changes as
   ready-to-apply diffs.

## Rules

- **Propose, never apply.** A rule change alters every future run; it goes to
  the owner as a diff (the engine lists it in the run's final report). The
  retro never edits a guard, rule pack, skill or profile itself.
- **Blameless.** Name the gate and the missing rule, never an agent's
  competence. "The reviewer lacked the tenant-isolation lens" is actionable;
  "the reviewer was careless" is not.
- **Specific or nothing.** "Be more careful with auth" is not a rule. "Every
  new route handler asserts the caller's tenant equals the resource's tenant;
  reviewer: missing = Blocking" is.
