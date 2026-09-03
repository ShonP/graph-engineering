---
description: Run a named playbook end to end - execute its nodes, honor its gates, dispatch each agent with the skills its task requires, and keep a resumable ledger.
argument-hint: "<goal> [--graph feature] [--auto-merge] [--resume <run-id>]"
---

# /graph-ship - the engine

Execute a playbook. **The engine is playbook-agnostic:** it reads `graphs/<name>.md` and runs whatever nodes it finds. It does not know what a feature is. That is what lets the same engine run a bug, a launch or a content workflow later without a branch being added here.

## Steps

1. **Load context.** Read `.claude/graph-profile.yaml`. If absent, tell the owner to run `/graph-init` and stop. Read `graphs/<name>.md`, defaulting to `feature`.

2. **Open the run.** Create `.graph/<run-id>/` with a UUIDv7 id. Copy the playbook into it, so the run records which version of the graph it executed. Start `ledger.md` with every node marked `pending`.

   On `--resume <run-id>`, read that ledger instead, skip nodes marked `done`, and resume at the first `pending`.

3. **Execute nodes in order.** Nodes sharing a `next` target are dispatched **in parallel - one message, several Task calls.** Sequential dispatch of parallel nodes is the most common way this loop silently loses its value.

4. **Dispatch discipline.** For each node:
   - Resolve the agent through `localAgents` first, then the plugin roster.
   - For implementation and fix nodes, pick the implementer by task size from the plan: `small` -> `implementer-simple` (sonnet), otherwise `implementer` (opus). An `ESCALATE` from `implementer-simple` re-dispatches the same task to `implementer` once, without counting as a fix round.
   - Derive the REQUIRED skill list from the profile's `routing`, matched against that task's files, plus the `always` entries.
   - Name those skills in the dispatch prompt as non-optional.
   - Pass the run directory, the profile path, the node's `in` artifacts, the node's `mode` if it declares one (the researcher runs one mode per dispatch), and the task's acceptance criteria.

   The agent never chooses its conditional skills. That decision lives here, because an agent that picks can quietly skip loading and write from priors instead.

5. **Honor gates.** A node with `gate: yes` stops and presents its artifact for the owner's approval before anything downstream runs.

   `--auto-merge` relaxes only the merge gate, only for this run, and only when zero blocking or important findings survive.

6. **Handle NEEDS_SETUP.** If an agent reports it, stop that leg and tell the owner which skill or dependency is missing. Do not re-dispatch without it, and do not let the agent improvise the competency. A result produced without the house patterns looks the same as one produced with them, which is precisely the danger.

7. **Fix loop.** Re-dispatch the implementer for each blocking and important finding, then re-run the review node scoped to the same diff. At most 3 rounds. Surface anything that survives as a labelled list for the owner. Nits never block.

8. **Update the ledger after every node:** status, artifact path, timestamp. This is what lets a run survive compaction and what `--resume` reads. Trust it over your own recollection of what you did.

9. **Report** the run id, each node's status, and the gate verdict.
