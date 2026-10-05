# Run throughput analysis: why runs are slow and lanes block

Date: 2026-10-05. Window: the 14 days to 2026-10-05.
Data: 1,045 subagent transcripts and 36 Workflow runs from `~/.claude/projects/**`, covering
forge-platform, fitness, game-studio, ninth-forge and graph-engineering, plus the `.graph/<run>/`
ledgers and `plan.json` files.

**Verdict: both complaints are real and measurable.** Implementers often run past 45 minutes,
and "parallel" runs mostly execute one agent at a time. The causes are structural (wave barriers,
plan shape, slow inner loops), not bad luck.

## How it was measured

- **Wall** is the first to last transcript timestamp of an agent.
- **Active** is wall time minus every gap over 10 minutes, so resumed agents and owner pauses do
  not inflate it.
- **Tool wait** is the time from each `tool_use` to its `tool_result`, grouped by Bash command
  class.
- **Concurrency** is the time-weighted number of agents running at once inside one Workflow.
- The analyzer scripts are `durations.py`, `tooltime.py` and `timeline.py`, kept in the session
  scratchpad. Promote them to `scripts/` if this needs re-measuring after the fixes.

## Finding 1: implementers run far past 45 minutes

| agent | runs | p50 active | p90 active | >45 min active | >2 h wall |
|---|---|---|---|---|---|
| implementer | 375 | 18m | 58m | 56 | 16 |
| implementer-simple | 60 | 9m | 24m | 3 | 2 |
| reviewer | 398 | 5m | 13m | 0 | 2 |
| researcher | 96 | 5m | 18m | 0 | 1 |
| planner | 31 | 14m | 34m | 1 | 0 |

Implementer active time by bucket (n=435): <15m 212, 15-30m 119, 30-45m 45, **45-90m 46, 90m+ 13**.
The 59 runs over 45 minutes are 14% of runs but **43% of all implementer hours**.

The worst cases:

- 222m: game-studio `T15` (device classes + runtime.sh)
- 185m: forge `Plan 6 task 17`
- 149m: fitness `impl-T4`
- 143m: forge `Plan 6 task 28`
- 141m: forge `Plan 6 task 23`
- 127m: forge `Plan 6 task 20`

## Finding 2: long implementers mostly wait; they are not thinking

| population | active | tool wait | of which sleep/poll loops | test | build |
|---|---|---|---|---|---|
| all implementers | 174.9h | 41% | 13% | 10% | 4% |
| implementers >45m | 74.5h | **52%** | **23%** | 7% | 8% |

There were 158 Bash calls of 5 minutes or more (23.4h in total), and 36 calls hit the 10-minute
Bash ceiling. The transcripts show three patterns.

- **The full proof is used as the dev loop.** game-studio T15 ran 12+ edit → full simulator and
  emulator cycle (15-29 min each, through `wait-run.sh`) → fail → edit iterations. forge task 17
  ran `scripts/integration.sh` in full at least 7 times, plus "run twice" flake checks. fitness T4
  repeated 4.5-minute `wait-run` attaches for about 2 hours.
- **Poll loops persist.** `until grep -q ...; do sleep 10; done` is still common in the forge
  runs, even though `agents/implementer.md:79` forbids it. The rule is prose, so nothing enforces
  it.
- **Shared-resource locks serialize work.** `lane-run.sh xcodebuild --slots 1` and the forge
  "you hold the cluster turn" briefs force tasks that look parallel to queue on one simulator or
  one cluster ("lane xcodebuild busy after 200 s").

## Finding 3: "parallel" runs execute one agent at a time

| workflow | wall | avg concurrency | time with exactly 1 agent | longest agent |
|---|---|---|---|---|
| sdd-graph (ninth-forge) | 561m | 1.2 | 88% | 31m |
| sdd-lanes | 440m | **1.0** | 100% | 72m |
| sdd-graph | 400m | 1.8 | 18% | 124m |
| sdd-graph | 321m | **1.0** | 100% | 68m |
| ge-0.15-build | 285m | 2.1 | 72% | 36m |
| sdd-lanes | 167m | **1.0** | 100% | 26m |

There are two causes.

1. **One lane holds every task.** In the hand-written superpowers SDD workflows, the lane shapes
   were `[14|1]`, `[9|5]`, `[8]`, `[6]`, `[6]` and `[3]`, each lane on a single shared worktree.
   Tasks within a lane run in sequence, and each one runs implement → review → fix → re-review in
   sequence. The 561-minute run is 76 agents with a median of 11 minutes each, chained end to end.
2. **Wave barriers in the engine.** `docs/engine/run.md:17-19` says: "No pipelining: each wave
   runs its own review and qa legs and fix loop ... a dependent wave waits until the previous
   wave's fix loop exits." The slowest task in a wave therefore gates every task in the next
   wave, including tasks that do not depend on it.

**Live example (game-studio run `01a10bff`, today).** Wave 1 was T01, T15 and T21. T21 finished
at 14:14Z and T01 at 14:53Z. T15 ran until about 18:05Z (232m wall). Wave 2 holds T02, T03 and
T06, whose only dependency is T01, plus T07, which also needs T15. T02, T03 and T06 sat idle for
**about 3h10m** after their only dependency was done.

## Finding 4: plans are deep chains with oversized tasks

The game-studio plan has 23 tasks in **10 waves**, with a 9-deep critical path:
T01 → T03 → T04 → T05 → T12 → T13 → T14 → T16 → T18. Because the barrier runs per wave, the floor
on wall time is 10 × (slowest task + review + fix).

Task size is under-constrained:

- T01 alone has **29 writable paths**.
- The planner's only size signal is `small|standard` (`agents/planner.md:95`).
- There is no time estimate, no file cap and no cap on verification cost.
- T15 mixed building tooling with proving it on every device class, which is the most expensive
  verification in the repo.

## Not the problem

- **Fix loops** are 15% of implementer hours. 40 tasks needed one round and only 7 went past
  round 1.
- **Reviewers** are fast: p90 is 13 minutes.
- **Workflow scheduler gaps** are zero: there is no idle time between agents. The time is lost
  inside agents and to serialization, not by the orchestrator.

## Recommendations, highest leverage first

Prior art: ready-queue DAG scheduling (`make -j`, Bazel and Airflow all start a node the moment
its inputs exist; none uses level barriers) and time-boxing work items. Rejected: simply raising
the wave width above 4. Width is not the bottleneck, because concurrency averages below 2.

1. **Replace wave barriers with a ready queue.** Start a task as soon as its `depends_on` tasks
   are merged into the run branch. Keep "at most 4 opus writers" as a semaphore, not a barrier.
   Each task flows implement → review → fix → merge on its own, and the repo gate runs per merge,
   memoized by `graph-control check --reuse`.
   - Change `docs/engine/run.md:17-19`.
   - Add `graph-control ready <plan.json> --done <ids>` next to `waves`.
   - Expected gain: the 3h10m stall above disappears.
2. **Give every task a time budget and enforce it in `validate-plan`.**
   - Each task carries `estimate_min` and must be 45 or less.
   - `validate-plan` fails a task with more than about 8 writable paths, or one that combines
     build and full-device or full-cluster proof.
   - The planner also minimizes critical-path depth: contracts and interfaces go first, then
     consumers fan out. Print the critical-path length at the plan gate next to the wave count.
3. **Time-box the implementer.** At 45 minutes the implementer commits what is green and returns
   `PARTIAL` with the remaining scope. The engine turns the remainder into a new task and does not
   let the run grind on. The budget goes in every brief, and the engine tracks elapsed time per
   dispatch.
4. **Fast inner loop, expensive proof once.**
   - Implementers iterate on focused tests only, then run one full suite at the end.
   - Full device, cluster or integration proof moves to the qa node or the per-merge gate.
   - This needs an executable guard, not prose: `wait-run.sh` counts full-suite invocations per
     `GRAPH_RUN_ID` task and refuses the third without an explicit `--reason`.
   - The existing "no sleep/until loops" rule becomes a PreToolUse hook that blocks
     `until ...; sleep` for implementer agents.
5. **Unblock shared resources.**
   - Raise the `xcodebuild` lane to 2 slots on this host, or give each task its own simulator.
   - Replace "hold the cluster turn" with per-task namespaces. Otherwise the resource lock
     re-serializes whatever change 1 parallelizes.
6. **Hand-written SDD workflows should not chain 6-14 tasks in one lane on one worktree.** Route
   them through `/graph-ship`, which already does per-task worktrees, or ship a saved workflow
   template that uses per-task worktrees and the same ready queue.

## Re-measure

After changes 1-4 ship, re-run the analyzer over the next 14 days. The targets are:

- implementer p90 active of 45 minutes or less
- no implementer over 90 minutes
- average Workflow concurrency of 2.5 or more
- zero "ready but blocked by a sibling" minutes
