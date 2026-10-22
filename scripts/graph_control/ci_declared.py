import re
from pathlib import Path
from typing import Any

from graph_control.ci_workflows import Job, Step, Workflow, load_workflows, location

EXPENSIVE_GUESS = re.compile(r"playwright|cypress|detox|maestro|e2e|xcodebuild test|integration", re.IGNORECASE)
PROD_DATA_GUESS = re.compile(r"backup|migrate", re.IGNORECASE)
PROD_JOB_GUESS = re.compile(r"deploy.*prod|prod.*deploy", re.IGNORECASE)
DEPLOY_ROLES = ("dev", "smoke", "prod")

CONFIG_FIX = "fix the profile's ci block"
PROD_DATA_FIX = ("run backup or migrate only when a pending-migrations step reports some: "
                 "`if: steps.<id>.outputs.pending == 'true'`")
PROMOTE_FIX = "order deploy as dev -> smoke -> prod with `needs:`; this checks order only, not build-once promotion"
MISSING_FIX = "correct the declared run text, or drop the row"

Row = tuple[str, str, str, str]


def _expensive_fix(inputs: list[str]) -> str:
    return (f"skip this job when none of {', '.join(inputs)} changed, with a job-level `if:` on a changed-files "
            "output, not a workflow `paths:` filter (a required check skipped by `paths:` stays Pending; one "
            "skipped by `if:` reports Success)")


def _declare_fix(key: str) -> str:
    return f"declare `ci.{key}` in the profile so doctor checks it"


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _rows_of(value: Any, with_inputs: bool) -> bool:
    return isinstance(value, list) and all(
        isinstance(row, dict) and isinstance(row.get("run"), str) and row["run"]
        and (not with_inputs or _strings(row.get("inputs"))) for row in value)


SHAPES = {
    "affected": ("{<stack>: <command>}", lambda v: isinstance(v, dict) and all(
        isinstance(c, str) and c for c in v.values())),
    "expensive": ("[{run: <step text>, inputs: [<globs>]}]", lambda v: _rows_of(v, True)),
    "prod_data_steps": ("[{run: <step text>}]", lambda v: _rows_of(v, False)),
    "deploy": ("{dev, smoke, prod: <job id>} or {}", lambda v: isinstance(v, dict) and (not v or (
        set(v) == set(DEPLOY_ROLES) and all(isinstance(j, str) and j for j in v.values())))),
}


def _steps(workflows: list[Workflow]):
    for workflow in workflows:
        for job in workflow.jobs:
            for step in job.steps:
                yield workflow, job, step


def _has_paths(workflow: Workflow) -> bool:
    on = workflow.on if isinstance(workflow.on, dict) else {}
    return any(isinstance(on.get(event), dict) and _strings(on[event].get("paths")) and on[event]["paths"]
               for event in ("push", "pull_request"))


def _scoped(workflow: Workflow, job: Job, step: Step, affected: list[str]) -> bool:
    return bool(step.if_.strip() or job.if_.strip() or _has_paths(workflow)
                or any(command in other.run for other in job.steps for command in affected))


def _expensive(workflows: list[Workflow], declared: list[dict], affected: list[str]) -> list[Row]:
    rows = []
    for entry in declared:
        matches = [(w, j, s) for w, j, s in _steps(workflows) if entry["run"] in s.run]
        if not matches:
            rows.append(("info", "ci-declared-missing", f"ci.expensive: `{entry['run']}` appears in no workflow step",
                         MISSING_FIX))
        rows += [("warn", "ci-expensive-unscoped",
                  f"{location(w, s.line)}: job `{j.id}` runs `{entry['run']}` on every change",
                  _expensive_fix(entry["inputs"]))
                 for w, j, s in matches if not _scoped(w, j, s, affected)]
    if not declared:
        rows += [("info", "ci-expensive-guess",
                  f"{location(w, s.line)}: job `{j.id}` looks like an unscoped expensive suite; declare ci.expensive",
                  _declare_fix("expensive"))
                 for w, j, s in _steps(workflows) if EXPENSIVE_GUESS.search(s.run) and not _scoped(w, j, s, affected)]
    return rows


def _unconditional(job: Job, step: Step) -> bool:
    return "outputs." not in step.if_ and "outputs." not in job.if_


def _prod_data(workflows: list[Workflow], declared: list[dict]) -> list[Row]:
    if not declared:
        return [("info", "ci-prod-data-guess",
                 (f"{location(w, s.line)}: job `{j.id}` looks like an ungated prod backup or migrate; "
                  "declare ci.prod_data_steps"),
                 _declare_fix("prod_data_steps"))
                for w, j, s in _steps(workflows) if "prod" in j.id.lower()
                and PROD_DATA_GUESS.search(f"{s.run}\n{s.name}") and _unconditional(j, s)]
    return [("warn", "ci-prod-data-unconditional",
             f"{location(w, s.line)}: job `{j.id}` runs `{entry['run']}` on every run", PROD_DATA_FIX)
            for entry in declared for w, j, s in _steps(workflows) if entry["run"] in s.run and _unconditional(j, s)]


def _needs(workflow: Workflow, job_id: str) -> set[str]:
    by_id = {job.id: job for job in workflow.jobs}
    seen: set[str] = set()
    pending = list(by_id[job_id].needs) if job_id in by_id else []
    while pending:
        need = pending.pop()
        if need not in seen:
            seen.add(need)
            pending += by_id[need].needs if need in by_id else ()
    return seen


def _deploy(workflows: list[Workflow], deploy: dict[str, str]) -> list[Row]:
    if not deploy:
        return [("info", "ci-prod-guess",
                 f"{location(w, j.line)}: job `{j.id}` looks like a prod deploy with no smoke need; declare ci.deploy",
                 _declare_fix("deploy"))
                for w in workflows for j in w.jobs if PROD_JOB_GUESS.search(j.id)
                and not any("smoke" in need.lower() for need in _needs(w, j.id))]
    defined = {job.id for workflow in workflows for job in workflow.jobs}
    missing = [("warn", "ci-prod-no-promote", f"ci.deploy.{role}: job `{deploy[role]}` is defined in no workflow",
                PROMOTE_FIX) for role in DEPLOY_ROLES if deploy[role] not in defined]
    if missing:
        return missing
    rows = []
    for workflow in workflows:
        prod = next((job for job in workflow.jobs if job.id == deploy["prod"]), None)
        if not prod:
            continue
        if deploy["smoke"] not in _needs(workflow, prod.id):
            gap = f"does not need `{deploy['smoke']}`"
        elif deploy["dev"] not in _needs(workflow, deploy["smoke"]):
            gap = f"needs `{deploy['smoke']}`, which does not need `{deploy['dev']}`"
        else:
            continue
        rows.append(("warn", "ci-prod-no-promote", f"{location(workflow, prod.line)}: prod job `{prod.id}` {gap}",
                     PROMOTE_FIX))
    return rows


def findings(root: Path, profile: dict[str, Any]) -> list[Row]:
    ci = profile.get("ci") or {}
    if not isinstance(ci, dict):
        return []
    workflows, _ = load_workflows(root)
    values, rows = {}, []
    for key, (shape, valid) in SHAPES.items():
        value = ci.get(key) or ({} if key in ("affected", "deploy") else [])
        if valid(value):
            values[key] = value
        else:
            rows.append(("warn", "ci-config-invalid", f"ci.{key}: {shape}", CONFIG_FIX))
    if "affected" in values and "expensive" in values:
        rows += _expensive(workflows, values["expensive"], list(values["affected"].values()))
    if "prod_data_steps" in values:
        rows += _prod_data(workflows, values["prod_data_steps"])
    if "deploy" in values:
        rows += _deploy(workflows, values["deploy"])
    return rows
