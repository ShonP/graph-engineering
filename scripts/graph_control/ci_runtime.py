import re
from pathlib import Path
from typing import Any

from graph_control.ci_workflows import Step, Workflow, load_workflows, location, other_providers, repo_path

STATUS_SCRIPT = "local-gate-status.sh"
HUSKY_HOOK = ".husky/pre-push"

BACKGROUND_QOS = re.compile(r"\btaskpolicy\b[^\n]*?\s(?:-b\b|-c\s*(?:background|maintenance|utility)\b)"
                            r"|\bionice\b[^\n]*?\s-c\s*3\b")
TAG_COMMAND = re.compile(r"\bgit\s+(?:fetch|pull)\b[^\n;&|]*\s--tags\b"
                         r"|\bgit\s+fetch\b[^\n;&|]*\brefs/tags"
                         r"|\bgit\s+push\b[^\n;&|]*(?:\s--tags\b|\s--follow-tags\b|\brefs/tags)")
SCRIPT_CALL = re.compile(r"(?:^\s*\./|(?:^|[\s;&|(])(?:bash|sh)\s+(?:-[abd-zA-Z]+\s+)*[\"']?(?:\./)?)"
                         r"([^\s;&|\"'$()-][^\s;&|\"'$()]*)", re.M)

GATE_FIX = ("add the verified-local skip: a step `bash scripts/ci/local-gate-status.sh check` with an `id`, and "
            "`if: steps.<id>.outputs.verified != 'true'` on the gate step (see `templates/ci/gate.yml`); the full "
            "gate stays the fallback")
QOS_FIX = "drop the background QoS; run the gate under `nice -n 10`, which keeps performance cores"
TAGS_FIX = ("set `persist-credentials: true` explicitly on this job's checkout, the remediation zizmor's `artipacked` "
            "audit gives for a needed credential, keep `permissions: contents: read` on the job, or pass the token "
            "only to the tag step; do not remove `false` from other jobs")
PROVIDER_FIX = "doctor reads GitHub Actions only; review this file by hand"
MISSING_FIX = "call the profile's `ci.gate` script, or re-render the scaffold with /graph-init --upgrade"
CONFIG_FIX = "fix the profile's ci block"
SHAPES = {"gate": "a repo-relative script path", "hook": "a repo-relative hook path"}

Row = tuple[str, str, str, str]


def _config(profile: dict[str, Any]) -> tuple[dict[str, str | None], list[Row]]:
    ci = profile.get("ci")
    values: dict[str, str | None] = {"gate": "", "hook": ".githooks/pre-push"}
    if ci is None:
        return values, []
    if not isinstance(ci, dict):
        return values, [("warn", "ci-config-invalid", f"ci: a mapping, got {type(ci).__name__}", CONFIG_FIX)]
    rows = []
    for key, shape in SHAPES.items():
        value = ci.get(key)
        if repo_path(value):
            values[key] = value
        elif value not in (None, ""):
            values[key] = None
            rows.append(("warn", "ci-config-invalid", f"ci.{key}: {shape}", CONFIG_FIX))
    return values, rows


def _hook(root: Path, rel_hook: str | None) -> tuple[str, str] | None:
    if rel_hook is None:
        return None
    for rel in (rel_hook, HUSKY_HOOK):
        if (root / rel).is_file():
            return rel, (root / rel).read_text(errors="replace")
    return None


def _run_line(step: Step) -> int:
    return step.lines.get("run", step.line)


def _gate_twice(workflows: list[Workflow], gate: str, hook: tuple[str, str] | None) -> list[Row]:
    if not gate or not hook or gate not in hook[1]:
        return []
    rows = []
    for workflow in workflows:
        for job in workflow.jobs:
            gate_steps = [step for step in job.steps if gate in step.run]
            if gate_steps and not any(STATUS_SCRIPT in step.run for step in job.steps):
                where = location(workflow, _run_line(gate_steps[0]))
                rows.append(("warn", "ci-gate-twice", f"{where}: job `{job.id}` runs `{gate}`, which the pre-push "
                             f"hook {hook[0]} already ran", GATE_FIX))
    return rows


def _scripts(text: str) -> list[str]:
    return [rel for rel in SCRIPT_CALL.findall(text) if "/" in rel or rel.endswith(".sh")]


def _gate_missing(root: Path, workflows: list[Workflow], hook: tuple[str, str] | None) -> list[Row]:
    calls = [(f"{hook[0]}:{number}", rel) for number, text in enumerate(hook[1].splitlines(), 1)
             for rel in _scripts(text)] if hook else []
    calls += [(location(workflow, _run_line(step)), rel) for workflow in workflows for job in workflow.jobs
              if any(STATUS_SCRIPT in step.run for step in job.steps) for step in job.steps for rel in _scripts(step.run)]
    return [("warn", "ci-gate-missing", f"{where}: calls `{rel}`, which does not exist", MISSING_FIX)
            for where, rel in calls if not (root / rel).is_file()]


def _background_qos(workflows: list[Workflow], hook: tuple[str, str] | None) -> list[Row]:
    places = [location(workflow, _run_line(step)) for workflow in workflows for job in workflow.jobs
              for step in job.steps if BACKGROUND_QOS.search(step.run)]
    if hook:
        places += [f"{hook[0]}:{number}" for number, text in enumerate(hook[1].splitlines(), 1)
                   if BACKGROUND_QOS.search(text)]
    return [("warn", "ci-background-qos", f"{where}: background QoS puts the gate on efficiency cores", QOS_FIX)
            for where in places]


def _tag_source(root: Path, workflow: Workflow, step: Step) -> str | None:
    if TAG_COMMAND.search(step.run):
        return location(workflow, _run_line(step))
    for rel in SCRIPT_CALL.findall(step.run):
        path = (root / rel).resolve()
        if path.is_relative_to(root.resolve()) and path.is_file() \
                and TAG_COMMAND.search(path.read_text(errors="replace")):
            return path.relative_to(root.resolve()).as_posix()
    return None


def _tags_no_credentials(root: Path, workflows: list[Workflow]) -> list[Row]:
    rows = []
    for workflow in workflows:
        for job in workflow.jobs:
            checkout = next((step for step in job.steps if step.uses.startswith("actions/checkout")
                             and step.with_.get("persist-credentials", "").lower() == "false"), None)
            source = checkout and next(filter(None, (_tag_source(root, workflow, s) for s in job.steps)), None)
            if source:
                where = location(workflow, checkout.lines["with.persist-credentials"])
                rows.append(("warn", "ci-tags-no-credentials", f"{where}: job `{job.id}` checks out with "
                             f"persist-credentials false, but {source} fetches or pushes tags", TAGS_FIX))
    return rows


def findings(root: Path, profile: dict[str, Any]) -> list[Row]:
    ci, rows = _config(profile)
    workflows, workflow_rows = load_workflows(root)
    rows += workflow_rows
    hook = _hook(root, ci["hook"])
    rows += _gate_twice(workflows, ci["gate"] or "", hook)
    rows += _gate_missing(root, workflows, hook)
    rows += _background_qos(workflows, hook)
    rows += _tags_no_credentials(root, workflows)
    rows += [("info", "ci-not-checked", f"CI provider not checked: {rel}", PROVIDER_FIX)
             for rel in other_providers(root)]
    return rows
