# Running a hand-written SDD plan on a ready queue

The plugin ships one host workflow, `workflows/sdd-ready-queue.js`, which Claude Code loads as
`/graph-engineering:sdd-ready-queue` (a plugin's `workflows/` directory is discovered with no
manifest field; the name is `<plugin>:<meta.name>`). It runs a plan you already have: each task in
its own worktree, at most 4 writers at once, and each task merged into the run branch as soon as it
passes review, so its dependents start without waiting for unrelated siblings.

## When to use which

| You have | Use |
| --- | --- |
| An ask, a bug, a feature idea | `/graph-ship "<ask>"`. It sizes the ask, plans, and holds the plan, review and qa gates. Preferred. |
| A finished plan (superpowers `writing-plans`, or your own task list with `depends_on`) that you want implemented by hand, without the engine's gates | this workflow |

The workflow has no plan gate, no qa leg and no decision cards: a task it cannot finish is parked
and reported, never re-planned. If you need those, use `/graph-ship`.

## Why a ready queue, and why 4 writers

Hand-written subagent-driven runs put 6 to 14 tasks in one lane on one shared worktree; each task
ran implement, review, fix and re-review in sequence, so average concurrency was 1.0 and a
561-minute run was 76 agents chained end to end (`docs/research/2026-10-05-run-throughput-analysis.md`,
Finding 3). This workflow has no lanes and no barrier: a task starts the moment every dependency is
merged and a writer slot is free. Ready tasks start longest remaining chain first, then in input
order, the same rule as `graph-control ready`. The cap is 4 writers (`max_writers` defaults to 4 and
is clamped to 1..4), the engine's writer cap; every implementer and fix round holds a slot.

## Args

Pass `args` as a JSON object, not as a JSON-encoded string:

```json
{
  "run_id": "01a10d5a-a003-70ea-802c-920bf24850ed",
  "run_branch": "feature/ready-queue",
  "repo_root": "/abs/path/to/repo",
  "worktree_root": "/abs/path/to/repo/.worktrees",
  "max_writers": 4,
  "dry_run": true,
  "tasks": [
    { "id": "T01", "depends_on": [], "size": "standard", "brief": "docs/plans/t01.md", "estimate_min": 10 },
    { "id": "T02", "depends_on": ["T01"], "size": "small", "brief": "docs/plans/t02.md", "estimate_min": 30 }
  ]
}
```

- `id`: letters, digits, `.`, `_`, `-`; unique. `depends_on`: ids in this list.
- `size`: `small` dispatches `graph-engineering:implementer-simple`, anything else
  `graph-engineering:implementer`.
- `brief`: the task brief (a path or the text); required for a live run.
- `estimate_min`: minutes; required for a dry run.
- `run_id`, `run_branch`, `repo_root`, `worktree_root`: required for a live run. Paths are absolute.

Invalid args (an unknown dependency, a cycle, a duplicate id, a bad path) return `{error}` and run
nothing.

## Invoke it

1. Allow it once in `.claude/settings.json` (or answer the prompt): add
   `Workflow(graph-engineering:sdd-ready-queue)` to `permissions.allow`. In `claude -p` there is no
   prompt, so the allow rule is required.
2. **Dry run first.** Ask Claude to run the workflow `graph-engineering:sdd-ready-queue` with your
   args and `"dry_run": true`. The dry run calls no agent: it simulates the queue on a virtual clock
   where each task takes `estimate_min` and review and merge take 0, and returns
   `{trace: [{id, start, end}], order, makespan, max_writers}`. Check that independent tasks start
   early and the long chain starts first. The same args always give the same trace.
3. Run it live with `"dry_run": false`.

## What a live run does per task

1. An implementer creates the task worktree from the run branch head
   (`git worktree add -b <run_id>-<id> <worktree_root>/<run_id>-<id> <sha>`) and checks
   `git merge-base --is-ancestor`. The host's `isolation: 'worktree'` is not used: it branches from
   the default branch, not the run branch.
2. A `graph-engineering:reviewer` reviews the branch. Blocking or important findings go to up to 3
   fresh fix rounds, each followed by a new review.
3. A merge step, serialized across all tasks, runs `git merge --no-ff <run_id>-<id>` in the
   worktree holding the run branch, then removes that task's worktree and branch only
   (`git worktree remove`, `git branch -d`, no force). It does not run `worktree-gc.sh --prefix`:
   that mode would also remove a sibling's clean worktree cut from an older run head before its
   implementer has written anything.

| Implementer status | What happens |
| --- | --- |
| `DONE`, `DONE_WITH_CONCERNS` | review, fix rounds, merge |
| `PARTIAL` | the green work is reviewed and merged, then `<id>b` is queued with the remaining scope and cases; it depends on `<id>`, and every dependent of `<id>` also waits for `<id>b`. A remainder that returns `PARTIAL` again is parked. |
| `ESCALATE` | one re-dispatch to `graph-engineering:implementer`; a second `ESCALATE` parks |
| `BLOCKED`, `NEEDS_CONTEXT`, `NEEDS_SETUP`, no result | parked |

A parked task parks its dependents; independent tasks continue. Every dispatch, merge, park and
remainder is a `log()` line. The result is `{merged, parked, remainders, trace}`; each parked entry
names its worktree (or `null` if it never started) for you to inspect and remove.

Rollback: revert the commit that added `workflows/sdd-ready-queue.js`; the slash command goes with
it.
