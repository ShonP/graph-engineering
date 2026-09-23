---
description: Run a named playbook end to end - execute its nodes, honor its gates, dispatch each agent with the skills its task requires, and keep a resumable ledger.
argument-hint: "<goal> [--graph feature] [--auto-merge] [--resume <run-id>]"
---

# /graph-ship - the engine

Execute a playbook. **The engine is playbook-agnostic:** it reads `graphs/<name>.md` and runs whatever nodes it finds. It does not know what a feature is. That is what lets the same engine run a bug or an infra workflow later without a branch being added here.

## Steps

1. **Load context.** Read `.claude/graph-profile.yaml`. If absent, tell the owner to run `/graph-init` and stop. Read `graphs/<name>.md`, defaulting to `feature`.

2. **Open the run.** Create `.graph/<run-id>/` with a UUIDv7 id. Copy the playbook into it, so the run records which version of the graph it executed. Start `ledger.md` with every node marked `pending`.

   On `--resume <run-id>`, read that ledger instead, skip nodes marked `done`, and resume at the first `pending`.

3. **Execute nodes in order.** Nodes sharing a `next` target are dispatched **in parallel - one message, several Task calls.** Sequential dispatch of parallel nodes is the most common way this loop silently loses its value.

4. **Dispatch discipline.** For each node:
   - Resolve the agent through `localAgents` first, then the plugin roster.
   - For implementation and fix nodes, pick the implementer by task size from the plan: `small` -> `implementer-simple` (sonnet), otherwise `implementer` (opus). An `ESCALATE` from `implementer-simple` re-dispatches the same task to `implementer` once, without counting as a fix round.
   - **Never override an agent's model.** Each roster agent declares its model in its frontmatter (`reviewer` and `implementer` on opus, `implementer-simple` on sonnet) and the dispatch takes it as is: no `model:` argument on the Task call, whatever the size of the diff. That covers scoped re-checks in the fix loop, pre-gate plan reviews and post-merge follow-ups. A "small diff, cheap reviewer" saving is the house anti-pattern here: the review is the gate, and a cheaper reviewer is how a defect the owner never sees gets through. The only model choice the engine makes is implementer versus implementer-simple, by task size, above.
   - Derive the REQUIRED skill list from the profile's `routing`, matched against that task's files, plus the `always` entries.
   - Name those skills in the dispatch prompt as non-optional.
   - Export `GRAPH_RUN_ID=<run-id>` for the qa dispatch, so the profile's `runtime` commands (`docker compose -p ge-${GRAPH_RUN_ID} ...`) stand up an isolated stack per run.
   - Pass the run directory, the profile path, the node's `in` artifacts, the node's `mode` if it declares one (the researcher runs one mode per dispatch), and the task's acceptance criteria.

   The agent never chooses its conditional skills. That decision lives here, because an agent that picks can quietly skip loading and write from priors instead.

5. **Honor gates.** A node with `gate: yes` stops and presents its artifact for the owner's approval before anything downstream runs.

   `--auto-merge` relaxes only the merge gate, only for this run, and only when zero blocking or important findings survive in either `findings.json` or `qa-findings.json` and qa reported `PASS`.

6. **Handle NEEDS_SETUP.** If an agent reports it, stop that leg and tell the owner which skill or dependency is missing. Do not re-dispatch without it, and do not let the agent improvise the competency. A result produced without the house patterns looks the same as one produced with them, which is precisely the danger.

7. **Fix loop.** The fix node takes every input the two legs produce: each blocking and important finding in the reviewer's `findings.json` and in qa's `qa-findings.json` (for example Schemathesis spec drift), and each `FAILED` qa row (its reproduction steps are the bug report). Re-dispatch the implementer for them, then re-run the review node scoped to the same diff **and** the qa node for the rows that failed plus any row whose files the fix touched. At most 3 rounds. Surface anything that survives as a labelled list for the owner. Nits never block.

   A repo whose profile sets `runtime.none` still runs the qa node; qa verifies through the public surface instead of a stood-up stack, so this rule does not trap libraries and CLIs. A qa `BLOCKED` is not a fix-loop input: the system could not be stood up, which is a missing `runtime` block, seed or env, not a code defect. Treat it like `NEEDS_SETUP` (step 6) and name what is missing. The merge gate does not open on a run whose qa leg never ran.

8. **Update the ledger after every node:** status, artifact path, timestamp. Follow-ups live beside it in `.graph/<run>/followups.md` (written by the plan node, appended by implementers); the engine never rewrites that file, and the merge node reads it. This is what lets a run survive compaction and what `--resume` reads. Trust it over your own recollection of what you did.

9. **Report** the run id, each node's status, and the gate verdict.
