---
name: impact-map
description: Use before planning any change, and whenever an agent notices something wrong next to the code it is changing - maps the blast radius (callers, API/event/DB/config contracts, infra, tests) and triages every adjacent issue into must-fix, fix-in-PR or follow-up under a scout budget. The researcher's impact mode writes the map; the planner turns it into tasks; implementers and the bug playbook's sibling search reuse the triage.
---

# Impact map

A plan written from the goal alone fixes the named thing and breaks its
neighbours. The map is what the planner reads so the plan covers the callers,
the contracts and the infra the goal never mentioned - and so the obvious
adjacent problems get fixed, deliberately, instead of ignored or sprawled into.

## The map

Start from the entry points the goal names (files, symbols, routes, tables,
charts). Search, do not guess: `rg` for references. The `LSP` tool's find-references
is better where an agent has it, but the researcher's tool list does not
include it, so `rg` is the default; say which you used.

| Section | What goes in it | How |
| --- | --- | --- |
| Entry points | the files/symbols the goal changes | from the goal, confirmed to exist |
| Callers | inbound references, two hops out | `rg -n '<symbol>\b'`, then the callers of those callers |
| Contracts | API routes and schema, events/topics and their payloads, DB tables/columns, config keys and env vars, feature flags, public package exports | route registrations, schema files, publishers/subscribers, migrations, settings classes |
| Infra | manifests, charts, values, Argo apps, secrets, CI jobs that name the component | `rg` the service/image/env-var names under the repo's infra paths |
| Tests | tests covering each entry point and contract; gaps | `rg` the symbol under test dirs; note what is untested |
| Change types | the `definition-of-done` rows this change matches | classify from the sections above |
| Adjacent issues | everything wrong you saw inside this radius | triaged below |

Every row cites `file:line`. A contract you could not locate is written as
"not found" with the search you ran - an honest gap, not a guess.

## Triage (shared vocabulary)

Every adjacent issue gets exactly one class. The same three classes are used by
implementers mid-task and by the `bug` playbook's sibling search.

| Class | Rule | Goes to |
| --- | --- | --- |
| **must-fix** | the goal is wrong, unsafe or untestable without it: a caller that breaks, a contract that must move with it, a missing migration, a security hole on the touched path | a plan task, same as the goal's own |
| **fix-in-PR** | inside files the plan already touches, testable, no new design decision, and small (about 30 changed lines or fewer) - a missing test, a wrong error code, a stale comment, an obvious off-by-one | a `small` plan task, **within the scout budget** |
| **follow-up** | anything else: outside the touched files, needs a decision, large, or over budget | `.graph/<run>/followups.md`, carried into the PR body's `## Follow-ups`; not fixed in this run |

**Scout budget:** fix-in-PR items are capped at 3 per run, or 20% of the plan's
task count if that is larger. Past the cap, the rest are follow-ups. The budget
is what keeps "leave it better than you found it" from turning a two-hour fix
into a two-day refactor. **Only the planner spends it, at the plan node**, where
the owner sees every fix-in-PR task at the plan gate; it may raise the cap only
there. Nobody spends it later, so nothing has to count it across parallel
implementers.

Each triaged item: `class | file:line | what is wrong | why this class | the
test that would prove the fix`.

## For implementers mid-task

Something wrong next to your change is triaged with the same table, but you
do not fix it unless the plan already has a task for it:

- **must-fix** you found (the task cannot be correct without it): stop and
  report `NEEDS_CONTEXT` - it changes the plan, and the owner approved a plan
  without it.
- **anything else**, however small: append it to `.graph/<run>/followups.md`
  as a triage row, list it in your report, and leave the code alone. The
  budget was spent at plan time; an unplanned fix is scope creep the reviewer
  will flag.

## Anti-patterns

- A map with no file:line. Failure: the planner cannot tell a searched gap
  from an unsearched one.
- Fixing every smell in the radius. Failure: the diff the reviewer reads is
  mostly not the goal, and the goal's own defects hide in it.
- Dropping follow-ups because they are out of scope. Failure: the next person
  finds the same thing with no record it was already seen.
- Keeping follow-ups only in an agent's final message. Failure: compaction or
  `--resume` loses them; `followups.md` is the record.
