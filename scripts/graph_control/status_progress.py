"""DONE and NEXT rows of the full status view, from each run's plan.json, run.json and receipts.json.

Imported lazily by `status.render_full`, so the status line never loads it or the plan code below."""

from pathlib import Path

from .status import _json, _store, _tmp


def progress(root: Path, now: float) -> tuple[list[str], list[str]]:
    """DONE rows (tasks passing since the look stored in `$TMPDIR/graph-engineering-status-seen-<root hash>`) and
    NEXT rows (one per run with ready tasks: open tasks whose depends_on all pass, longest chain first). A case
    passes when each check's latest receipt for this run.json that lists it passes it with no blocking or important
    findings, and a task from the receipt that made all its cases pass. Running tasks are unknown here (they have no
    receipt yet), so a running task still shows as ready, and an unfinished plan always has a ready task. Stores this
    look when a run has a plan."""
    from . import common, state  # lazy, as the four below: the status line never needs them
    from .identity import timestamp
    from .plan import Plan
    from .plan_queue import ready_set
    from .receipts import Receipt
    plans, seen, done, upcoming = sorted(root.glob(".graph/*/plan.json")), _tmp("seen-{}", root), [], []
    last = stored if type(stored := _json(seen)) in (int, float) else 0.0
    for path in plans:
        run, store, name = path.parent / "run.json", path.parent / "receipts.json", path.parent.name[:8]
        try:
            plan, own = Plan.parse(common.load(path)), common.fingerprint(common.load(run)) if run.exists() else None
            items = list(map(Receipt.parse, state.store_items(store))) if store.exists() else []
            ordered = sorted((timestamp(r.observed_at), n, r) for n, r in enumerate(items) if r.run_sha256 == own)
        except (OSError, ValueError):
            continue
        checks, since = {}, {}
        for at, _, receipt in ordered:
            checks[receipt.check_id] = {case.id: case.status == "PASS" and not (receipt.blocking or receipt.important)
                                        for case in receipt.cases}
            passing = {key for key in set().union(*checks.values()) if all(c.get(key, True) for c in checks.values())}
            since = {task.id: since.get(task.id, (at, receipt.candidate.sources[0].revision[:8]))
                     for task in plan.tasks if set(task.case_ids) <= passing}
        done += [(at, f"  {name}: {key} at {rev}") for key, (at, rev) in since.items() if at.timestamp() > last]
        ready = ready_set(plan, done=since.keys(), running=(), width=len(plan.tasks))
        upcoming += [f"  {name}: ready: {', '.join(ready)}"] if ready else []
    if plans:
        _store(seen, now)
    return [row for _, row in sorted(done, key=lambda pair: pair[0])], upcoming
