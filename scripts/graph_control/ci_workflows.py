from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

OTHER_PROVIDERS = (
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    ".buildkite/pipeline.yml",
    ".drone.yml",
)


@dataclass(frozen=True)
class Step:
    job: str
    index: int
    name: str
    uses: str
    run: str
    if_: str
    with_: dict[str, str]
    line: int
    lines: dict[str, int]


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    needs: tuple[str, ...]
    if_: str
    steps: tuple[Step, ...]
    line: int


@dataclass(frozen=True)
class Workflow:
    path: str
    on: Any
    jobs: tuple[Job, ...]


def _line(node: Node) -> int:
    return node.start_mark.line + 1


def _plain(node: Node | None) -> Any:
    if isinstance(node, MappingNode):
        return {_plain(key): _plain(value) for key, value in node.value}
    if isinstance(node, SequenceNode):
        return [_plain(item) for item in node.value]
    return node.value if isinstance(node, ScalarNode) else None


def _pairs(node: MappingNode) -> dict[str, tuple[Node, Node]]:
    return {key.value: (key, value) for key, value in node.value if isinstance(key, ScalarNode)}


def _text(pairs: dict[str, tuple[Node, Node]], key: str) -> str:
    value = pairs.get(key, (None, None))[1]
    return value.value if isinstance(value, ScalarNode) else ""


def _step(job: str, index: int, node: MappingNode) -> Step:
    pairs = _pairs(node)
    lines = {key: _line(key_node) for key, (key_node, _) in pairs.items()}
    with_: dict[str, str] = {}
    with_node = pairs.get("with", (None, None))[1]
    if isinstance(with_node, MappingNode):
        for key, (key_node, value) in _pairs(with_node).items():
            lines[f"with.{key}"] = _line(key_node)
            if isinstance(value, ScalarNode):
                with_[key] = value.value
    return Step(job, index, _text(pairs, "name"), _text(pairs, "uses"), _text(pairs, "run"),
                _text(pairs, "if"), with_, _line(node), lines)


def _job(key: ScalarNode, node: Node) -> Job | None:
    if not isinstance(node, MappingNode):
        return None
    pairs = _pairs(node)
    steps = pairs.get("steps", (None, None))[1]
    if not isinstance(steps, SequenceNode):
        return None
    needs = _plain(pairs.get("needs", (None, None))[1])
    needs = (needs,) if isinstance(needs, str) else tuple(n for n in needs or () if isinstance(n, str))
    return Job(key.value, _text(pairs, "name"), needs, _text(pairs, "if"),
               tuple(_step(key.value, i, s) for i, s in enumerate(steps.value) if isinstance(s, MappingNode)),
               _line(key))


def _workflow(rel: str, root: MappingNode) -> Workflow:
    pairs = _pairs(root)
    jobs_node = pairs.get("jobs", (None, None))[1]
    jobs = []
    if isinstance(jobs_node, MappingNode):
        for key, value in jobs_node.value:
            job = _job(key, value) if isinstance(key, ScalarNode) else None
            if job:
                jobs.append(job)
    return Workflow(rel, _plain(pairs.get("on", (None, None))[1]), tuple(jobs))


def load_workflows(root: Path) -> tuple[list[Workflow], list[tuple[str, str, str, str]]]:
    folder = root / ".github" / "workflows"
    if not folder.is_dir():
        return [], []
    workflows, rows = [], []
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml"))
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            node = yaml.compose(path.read_text(), Loader=yaml.SafeLoader)
            if not isinstance(node, MappingNode):
                raise ValueError("root is not a mapping")
        except (yaml.YAMLError, ValueError, OSError) as exc:
            first = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
            rows.append(("warn", "ci-workflow-invalid", f"{rel}: {first}", "fix the YAML; doctor skipped this file"))
            continue
        workflows.append(_workflow(rel, node))
    return workflows, rows


def other_providers(root: Path) -> list[str]:
    return [rel for rel in OTHER_PROVIDERS if (root / rel).is_file()]


def location(workflow: Workflow, line: int) -> str:
    return f"{workflow.path}:{line}"
