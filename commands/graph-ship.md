---
description: Run a named playbook end to end - execute its nodes, honor its gates, dispatch each agent with the skills its task requires, and keep a resumable ledger.
argument-hint: "<goal> [--graph feature|bug|infra] [--auto-merge] [--resume <run-id>]"
---

# /graph-ship - the engine

Execute a playbook. **The engine is playbook-agnostic:** it reads `graphs/<name>.md` and runs whatever nodes it finds. It does not know what a feature is. That is what lets the same engine run `feature`, `bug` and `infra` without a branch per workflow here.

## Steps

1. **Load context.** Read `.claude/graph-profile.yaml`. If absent, tell the owner to run `/graph-init` and stop. Read `graphs/<name>.md` for the playbook `--graph` names.

   **`--resume <run-id>`: no triage.** Read the playbook copy in `.graph/<run-id>/` and the ledger's `playbook:` line; the run finishes on the graph it started with.

   **No `--graph` on a new run: triage.** Classify the goal and pick one playbook, then carry the choice and a one-line reason into step 2, which writes it as the first line of `ledger.md` (`playbook: bug - "checkout returns 500 when the cart is empty" describes wrong behaviour`):
   - **bug** - the goal describes existing behaviour that is wrong: an error, crash, regression, wrong result, a failing check, a stack trace, an issue labelled bug.
   - **infra** - the goal's target is deployment configuration only: Helm charts or values, kustomize overlays, Argo CD applications, Kubernetes manifests, gateway or policy resources, secrets wiring, cluster add-ons - and no application code.
   - **feature** - everything else, including chores and refactors (the planner scales the plan down) and changes that touch both app code and infra (the impact map classifies the infra tasks).

   When two fit, prefer the narrower one only if the goal says so outright; otherwise `feature`. Every shipped playbook gates before product code moves (feature, bug and infra all gate at `plan`), and the triage line is the first thing on that gate's exhibit, so a wrong pick is caught before any code - the owner reruns with `--graph`. Never ask before running: a wrong pick costs one gate, a question costs the owner's attention on every run. A playbook added later must keep a gate before its first code-writing node, or triage must ask the owner before running it.

2. **Open the run.** Create `.graph/<run-id>/` with a UUIDv7 id. Copy the playbook into it, so the run records which version of the graph it executed. Start `ledger.md` with the `playbook:` line first - `playbook: <name> - <reason>` from triage, or `playbook: <name> - --graph` when the owner named it - then every node marked `pending`.

   On `--resume <run-id>`, read that ledger instead, skip nodes marked `done` or `skipped`, and resume by recomputing the ready set (step 3): `waiting: <what>` nodes are checked first, and `blocked: <what>` nodes count as `pending` and are re-run, since resuming is how the owner says the missing piece is now there.

   **Worktree.** Before the first node whose agent writes to the repo (an implementer, or qa writing a reproduction test), create the run's worktree with `superpowers:using-git-worktrees` on a branch named for the run, and pass its path to every later dispatch. Every agent that writes, writes there.

3. **Execute the ready set.** A node is ready when every node whose `next` names it is `done` or `skipped` (the first node has none). `fix` counts as `done` only when the fix loop (step 7) exits, so `merge` never opens mid-loop. Dispatch **every ready node at once - one message, several Task calls** - then recompute the set as each finishes. In the feature playbook that sends all four research nodes together, then `design` as soon as `research-ux` and `research-competitor` are done while tech and impact may still run, and `plan` only once all of them are. Sequential dispatch of ready nodes is the most common way this loop silently loses its value.

   **`when: <flag>`** makes a node conditional on a line `<flag>: yes|no - <reason>` in `goal.md`. `no` marks it `skipped (<flag>: no - <reason>)` in the ledger, and the run continues to its `next`; `yes`, or no such line, runs it - a missing flag never skips work. The plan gate's exhibit shows the line, so a wrong `ui: no` is caught before code: when the owner rejects the plan over it, set the line to `yes` in `goal.md`, mark the skipped node `pending`, run it, then re-run `plan` - no new run needed.

4. **Dispatch discipline.** For each node:
   - Resolve the agent through `localAgents` first, then the plugin roster.
   - For implementation and fix nodes, pick the implementer by task size from the plan: `small` -> `implementer-simple` (sonnet), otherwise `implementer` (opus). An `ESCALATE` from `implementer-simple` re-dispatches the same task to `implementer` once, without counting as a fix round.
   - **Never override an agent's model.** Each roster agent declares its model in its frontmatter (`reviewer` and `implementer` on opus, `implementer-simple` on sonnet) and the dispatch takes it as is: no `model:` argument on the Task call, whatever the size of the diff. That covers scoped re-checks in the fix loop, pre-gate plan reviews and post-merge follow-ups. A "small diff, cheap reviewer" saving is the house anti-pattern here: the review is the gate, and a cheaper reviewer is how a defect the owner never sees gets through. The only model choice the engine makes is implementer versus implementer-simple, by task size, above.
   - Derive the REQUIRED skill list from the profile's `routing`, matched against that task's files, plus the `always` entry for the node's role (`impl` for implementers, `review` for the reviewer, `design` for the ux-designer), plus any skill the node itself names in `skills:` or `compose:` (a `compose:` skill, such as `superpowers:systematic-debugging` on the bug playbook's diagnose node, is the protocol that node follows).
   - Name those skills in the dispatch prompt as non-optional.
   - Name the stack id in every dispatch that may stand up `runtime`: `GRAPH_RUN_ID=<run-id>` for the `qa`-agent nodes (`qa`, `reproduce`, `verify`, `post-deploy`), `GRAPH_RUN_ID=<run-id>-design` for `design`, and `GRAPH_RUN_ID=<run-id>-t<task number>` for each implementer task, so parallel tasks never share a stack or wipe each other's database. It goes in the prompt as text, not as an export: a subagent's Bash calls do not inherit the engine's environment, and each call is a fresh shell. The agent prefixes every runtime command with it; the profile's `${GRAPH_RUN_ID:?}` fails loudly if it is ever missing.
   - Pass the node's `out:` contract verbatim - it is the agent's definition of done for that node (a diagnose node's `out:` says "no fix yet"; the agent must honour it).
   - Pass the run directory, the profile path, the node's `in` artifacts, the node's `mode` if it declares one (the researcher runs one mode per dispatch), and the task's acceptance criteria.

   The agent never chooses its conditional skills. That decision lives here, because an agent that picks can quietly skip loading and write from priors instead.

5. **Honor gates.** A node with `gate: yes` stops and presents, for the owner's approval before anything downstream runs: its artifact; the ledger's `playbook:` line (which playbook, and why); at the plan gate, `goal.md`'s `ui:` line and - when `design` ran - the plan's `## Experience` section with its as-is and to-be images shown, not linked, since this is where the owner approves where things go; and at the merge gate, qa's verdict line verbatim - `PASS`, or `PASS (static-only)` with the skipped live steps listed, so an infra run verified without a cluster never looks like one verified with one.

   `--auto-merge` relaxes only the merge gate, only for this run, and only when zero blocking or important findings survive in the latest round's `findings.json` and `qa-findings.json` - both files present, since an absent file is not zero findings - and qa reported a full `PASS` - `PASS (static-only)` from an infra run without a throwaway cluster does not qualify.

6. **Handle NEEDS_SETUP.** If an agent reports it, stop that leg and tell the owner which skill or dependency is missing. Do not re-dispatch without it, and do not let the agent improvise the competency. A result produced without the house patterns looks the same as one produced with them, which is precisely the danger.

7. **Fix loop.** The fix node takes every input the two legs produce: each blocking and important finding in the reviewer's `findings.json` and in qa's `qa-findings.json` (for example Schemathesis spec drift), and each `FAILED` qa row (its reproduction steps are the bug report). Before each re-run, keep the round: rename `findings.json`, `qa-findings.json` and `qa.md` to `*.r<N>.*` (round 1 = the first review), so the next round writes fresh files and `retro` can see what every round caught, not only what survived. Re-dispatch the implementer for them, then re-run every node that feeds `fix` - the reviewer's node scoped to the same diff, and the qa-agent node (`qa`, or `verify` in the infra playbook) for the rows that failed, any row whose files the fix touched, and every check that produced a finding in the previous round's `qa-findings.r<N>.json` (Schemathesis drift re-runs Schemathesis) - so the fresh `qa-findings.json` says whether each one is gone rather than silently dropping it. At most 3 rounds. Surface anything that survives as a labelled list for the owner. Nits never block.

   A repo whose profile sets `runtime.none` still runs the qa node; qa verifies through the public surface instead of a stood-up stack, so this rule does not trap libraries and CLIs. A qa `BLOCKED` is not a fix-loop input: the system could not be stood up, which is a missing `runtime` block, seed or env, not a code defect. Treat it like `NEEDS_SETUP` (step 6) and name what is missing. The merge gate does not open on a run whose qa leg never ran. A `design` node's `BLOCKED` (a configured `runtime` that would not come up for the as-is captures) is handled like `NEEDS_SETUP` (step 6) too: mark it `blocked: <what>`, tell the owner what is missing, and `--resume` re-runs it - never design blind, and never let `plan` run without it.

8. **Update the ledger after every node:** status, artifact path, timestamp. Follow-ups live beside it in `.graph/<run>/followups.md` (written by the plan node, appended by implementers); the engine never rewrites that file, and the merge node reads it. This is what lets a run survive compaction and what `--resume` reads. Trust it over your own recollection of what you did.

9. **After the merge gate.** Approval and merging are two ledger states:
   - **`approved`** - the owner approved the merge gate. The engine pushes the run branch and opens the PR with `gh pr create` if none exists (body: the merge exhibit - diff summary, evidence, `## Follow-ups`), and records its number. With `--auto-merge` and the conditions in step 5 met, the engine is the one that merges: `gh pr merge <n> --merge`.
   - **`merged: <sha>`** - the PR is merged. The engine checks with `gh pr view <n> --json state,mergeCommit` (or, off GitHub, `git merge-base --is-ancestor <run branch head> origin/<default>` after a fetch) and records the merge commit SHA, which `post-deploy` waits to see serving.

   The `post-deploy` node needs `merged:`. If the owner has not merged yet, mark it `waiting: merge` and stop; `--resume <run-id>` checks again. An empty `deploy.wait` makes it `SKIPPED` and the run goes on to `retro`. A post-deploy `FAIL` is never a fix-loop input and never triggers an automatic rollback: its rollback recommendation goes to the owner at once.

10. **Report** the run id, each node's status, the gate verdicts, the post-deploy verdict, and the retro's proposed rule changes as diffs for the owner to apply or decline. The engine applies none of them.
