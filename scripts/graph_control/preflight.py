"""Inspect the effective playbook/profile and declared host capabilities."""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .common import Invalid, load, require
from .identity import validate_identity
from .plan import Plan
from .run import Run


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys rather than silently changing policy."""


def mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        require(isinstance(key, (str, int, float, bool)), "unsupported YAML mapping key")
        require(key not in result, f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def read_profile(path: Path) -> dict[str, Any]:
    require(path.stat().st_size <= 1024 * 1024, "profile exceeds 1 MiB")
    try:
        value = yaml.load(path.read_text(), Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise Invalid(f"invalid profile YAML: {error}") from error
    require(isinstance(value, dict), "profile must be a YAML mapping")
    return value


def read_graph(path: Path) -> dict[str, dict[str, str]]:
    nodes: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in path.read_text().splitlines():
        heading = re.fullmatch(r"## node: ([a-z][a-z0-9_-]*)", line.strip())
        if heading:
            name = heading.group(1)
            require(name not in nodes, f"duplicate graph node: {name}")
            current = nodes[name] = {}
        elif current is not None:
            field = re.fullmatch(r"(agent|gate|next):\s*(.+)", line.strip())
            if field:
                key, value = field.groups()
                require(key not in current, f"duplicate graph field: {key}")
                current[key] = value
    require(bool(nodes), "playbook contains no nodes")
    for name, fields in nodes.items():
        require({"agent", "gate", "next"} <= fields.keys(), f"{name}: incomplete graph node")
        require(fields["gate"] in {"yes", "no"}, f"{name}: invalid gate")
        for target in fields["next"].split(","):
            require(target.strip() == "END" or target.strip() in nodes, f"{name}: unknown next node")
    pending = set(nodes)
    completed: set[str] = set()
    while pending:
        ready = {name for name in pending if all(
            other in completed or name not in {x.strip() for x in fields["next"].split(",")}
            for other, fields in nodes.items())}
        require(bool(ready), "playbook contains a dependency cycle")
        completed.update(ready)
        pending -= ready
    return nodes


def preflight(run: Run, profile_path: Path, graph_path: Path, now: datetime,
              *, readiness_only: bool = False) -> dict[str, Any]:
    require(sys.version_info >= (3, 11), "Python >= 3.11 required")
    installed = load(Path(__file__).resolve().parents[2] / ".claude-plugin" / "plugin.json")
    require(run.plugin_version == installed["version"], "run plugin version differs from executing helper")
    require(profile_path.resolve() == Path(run.profile).resolve(), "profile path differs from run")
    require(graph_path.resolve() == Path(run.graph).resolve(), "graph path differs from run")
    plan = Plan.parse(load(Path(run.plan)))
    profile, nodes = read_profile(profile_path), read_graph(graph_path)
    roles = {"plan": "planner", "implement": "implementer", "review": "reviewer", "qa": "qa", "verify": "qa"}
    for capability, name in run.capability_nodes.items():
        require(name in nodes, f"required capability {capability}: node {name} missing")
        require(nodes[name]["agent"] == roles[capability],
                f"{capability}: node agent cannot satisfy required role")
    require(run.capability_nodes["review"] != run.capability_nodes["qa"], "review and QA need separate nodes")
    runtime = profile.get("runtime")
    require(isinstance(runtime, dict), "required runtime profile missing; configure runtime or public CLI/library surface")
    if run.candidate.runtime is None:
        require(isinstance(runtime.get("none"), str) and bool(runtime["none"].strip()),
                "static candidate requires explicit runtime.none public-surface reason")
        require(not run.requires_api, "API acceptance requires identified runtime")
    else:
        require(not runtime.get("none"), "live candidate contradicts runtime.none")
        harness = runtime.get("command")
        if not (isinstance(harness, str) and harness.strip()):
            for key in ("up", "seed", "down", "baseUrl"):
                require(isinstance(runtime.get(key), str) and bool(runtime[key].strip()), f"runtime.{key} missing")
            health = runtime.get("health")
            require(isinstance(health, dict) and bool(health.get("command") or (health.get("url") and health.get("expect"))),
                    "runtime.health missing")
    if run.requires_api:
        api = profile.get("api")
        require(isinstance(api, dict), "API profile missing")
        require(all(isinstance(api.get(key), str) and api[key].strip() for key in ("collection", "schema")),
                "api.collection and api.schema required")
        collection = Path(api["collection"])
        require(not collection.is_absolute() and ".." not in collection.parts,
                "api.collection must be relative to a candidate source")
        require(any((Path(source.root) / collection / "bruno.json").is_file() for source in run.candidate.sources),
                "Bruno collection unavailable in candidate sources")
    if run.requires_design:
        require("design" in nodes, "required design capability missing from saved playbook")
        gates = profile.get("gates", {})
        require(isinstance(gates, dict), "profile gates must be a mapping")
        require(not (gates.get("design") == "owner" and gates.get("plan") == "auto"
                     and nodes["design"]["gate"] != "yes"),
                "owner design gate cannot be replaced by an automatic plan gate")
    case_ids = {case.id for case in plan.cases}
    for check in run.checks:
        require(set(check.case_ids) <= case_ids, f"{check.id}: unknown case ID")
    for capability in ("qa", "verify"):
        covered = {case for check in run.checks if check.capability == capability for case in check.case_ids}
        require(covered == case_ids, f"{capability}: required acceptance cases missing from checks")
    executables = set(run.tools) | {check.argv[0] for check in run.checks}
    for executable in executables:
        require(shutil.which(executable) is not None, f"required executable unavailable: {executable}")
    for actor in run.actors:
        for skill in actor.skills:
            require(Path(skill).is_file(), f"{actor.id}: required skill unavailable: {skill}")
    validate_identity(run, now, readiness_only=readiness_only)
    return {"interpreter": sys.executable, "python": sys.version.split()[0],
            "phase": "readiness" if readiness_only else "candidate",
            "capabilities": run.capability_nodes, "models": {actor.id: actor.resolved_model for actor in run.actors}}
