---
name: retro
description: Use at the end of every playbook run - a blameless look at what each gate caught and what got past the gate that should have caught it, turned into concrete, reviewable rule changes (a line for a repo rule pack or a house skill) so the same class of defect is caught earlier next time. Proposes; never edits rules on its own.
---

# Retro

Every run produces evidence of where the process leaked: a defect the reviewer
found that the implementer's own tests should have, a qa FAILED row the review
passed, a post-deploy FAIL everything before it passed, a fix loop that needed
three rounds. The retro reads that evidence and turns each leak into one rule
change, so the organisation learns instead of repeating.

Sources: Google SRE, [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)
- blameless by construction, focused on contributing causes and action items
that change the system, not on who.

## Inputs

The run directory: `ledger.md`, every round of review and qa output - the
engine keeps earlier rounds as `findings.r<N>.json`, `qa-findings.r<N>.json`
and `qa.r<N>.md` beside the final `findings.json`, `qa-findings.json` and
`qa.md` - plus `post-deploy.md` when it exists, `followups.md`,
and the implementer reports the ledger points to.

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
4. **Propose one rule change per class** with the exact text and the exact
   target: the repo's own rule pack (a path from the profile's `rules`), a
   routing row in the profile, or a house skill in the plugin. Precedence is
   house > vault-generated > community, so a retro rule is a house rule.
5. **Write** `.graph/<run>/retro.md`: the leak table, the classes, and the
   proposed changes as ready-to-apply diffs. Nothing leaked: say so in one line
   - that is a result, not an empty report.

## Rules

- **Propose, never apply.** A rule change alters every future run; it goes to
  the owner as a diff (the engine lists it in the run's final report). The
  retro never edits a rule pack, skill or profile itself.
- **Blameless.** Name the gate and the missing rule, never an agent's
  competence. "The reviewer lacked the tenant-isolation lens" is actionable;
  "the reviewer was careless" is not.
- **Specific or nothing.** "Be more careful with auth" is not a rule. "Every
  new route handler asserts the caller's tenant equals the resource's tenant;
  reviewer: missing = Blocking" is.
