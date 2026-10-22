"""run init / run bind: build run.json instead of hand-copying it.

`run init <run-dir>` writes what is known at run open to run.draft.json and
never run.json. `run bind <run-dir> --host host.json` completes the draft once
plan.json exists: plan, profile and graph hashes computed now, one actor per
capability with an id derived from the run id, host observations copied in,
then Run.parse before run.json is written atomically. Nothing is written when
the result does not parse.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from ..common import file_hash, load, obj, require, text

NAME = "run"
HELP = "run init writes run.draft.json at open; run bind completes it into run.json after plan.json exists"
DRAFT = "run.draft.json"
ROLES = ("plan", "implement", "review", "qa", "verify")
DRAFT_FIELDS = ("schema_version id plugin_version plan profile profile_sha256 graph graph_sha256 "
                "capability_nodes requires_api requires_design runtime_max_age_seconds")
HOST_FIELDS = {"available_models", "tools", "resolution_source", "models", "checks", "candidate", "runtime_identity"}
HOST_COPIED = ("available_models", "tools", "checks", "candidate", "runtime_identity")


def add_arguments(parser: ArgumentParser) -> None:
    steps = parser.add_subparsers(dest="run_step", required=True)
    start = steps.add_parser("init", help="write <run-dir>/run.draft.json from the copied playbook and the profile")
    start.add_argument("run_dir", type=Path)
    start.add_argument("--profile", required=True, type=Path, help="absolute path of the repo's graph profile")
    start.add_argument("--plugin-root", required=True, type=Path, help="absolute plugin root holding .claude-plugin/plugin.json")
    start.add_argument("--requires-api", action="store_true")
    start.add_argument("--requires-design", action="store_true")
    finish = steps.add_parser("bind", help="complete the draft into <run-dir>/run.json once plan.json exists")
    finish.add_argument("run_dir", type=Path)
    finish.add_argument("--host", required=True, type=Path, help="engine-written host observations")


def existing(path: Path) -> Path:
    require(path.is_file(), f"missing {path}")
    return path


def capability_nodes(graph: Path) -> dict[str, str]:
    from ..preflight import read_graph

    nodes = read_graph(graph)
    wanted = {role: role for role in ROLES[:-1]} | {"verify": "verify" if "verify" in nodes else "qa"}
    missing = sorted(set(wanted.values()) - nodes.keys())
    require(not missing, f"{graph} lacks capability nodes: {', '.join(missing)}")
    return wanted


def plugin_version(root: Path) -> str:
    manifest = load(existing(root / ".claude-plugin/plugin.json"))
    require(isinstance(manifest, dict), "plugin.json must be an object")
    return text(manifest.get("version"))


def init(args: Namespace) -> dict[str, Any]:
    from ..state import write

    for flag, path in (("--profile", args.profile), ("--plugin-root", args.plugin_root)):
        require(path.is_absolute(), f"{flag} must be absolute: {path}")
    run_dir = args.run_dir.resolve()
    graph, profile = existing(run_dir / "graph.md"), existing(args.profile)
    draft = {"schema_version": 1, "id": run_dir.name, "plugin_version": plugin_version(args.plugin_root),
             "plan": str(run_dir / "plan.json"), "profile": str(profile), "profile_sha256": file_hash(profile),
             "graph": str(graph), "graph_sha256": file_hash(graph), "capability_nodes": capability_nodes(graph),
             "requires_api": args.requires_api, "requires_design": args.requires_design,
             "runtime_max_age_seconds": 120}
    write(run_dir / DRAFT, draft)
    return {"draft": str(run_dir / DRAFT)}


def host_observations(path: Path) -> dict[str, Any]:
    host = load(path)
    require(isinstance(host, dict), f"{path} must be an object")
    missing, unknown = sorted(HOST_FIELDS - host.keys()), sorted(host.keys() - HOST_FIELDS)
    require(not missing, f"{path} missing fields: {', '.join(missing)}")
    require(not unknown, f"{path} unknown fields: {', '.join(unknown)}")
    models = obj(host["models"], " ".join(ROLES))
    for role in ROLES:
        obj(models[role], "requested resolved")
    return host


def bind(args: Namespace) -> dict[str, Any]:
    from ..plan import Plan
    from ..run import Run, actor_id
    from ..state import write

    run_dir = args.run_dir.resolve()
    draft = obj(load(existing(run_dir / DRAFT)), DRAFT_FIELDS)
    plan = existing(run_dir / "plan.json")
    Plan.parse(load(plan))
    host = host_observations(args.host)
    hashes = {name: file_hash(existing(Path(draft[name]))) for name in ("profile", "graph")}
    changed = [name for name, value in hashes.items() if draft[f"{name}_sha256"] != value]
    actors = [{"id": actor_id(role, draft["id"]), "role": role,
               "requested_model": host["models"][role]["requested"], "resolved_model": host["models"][role]["resolved"],
               "resolution_source": host["resolution_source"], "skills": []} for role in ROLES]
    candidate = {**draft, "plan_sha256": file_hash(plan), "profile_sha256": hashes["profile"],
                 "graph_sha256": hashes["graph"], "actors": actors, **{key: host[key] for key in HOST_COPIED}}
    parsed = Run.parse(candidate)
    target = run_dir / "run.json"
    write(target, candidate)
    return {"run": str(target), "actors": [actor["id"] for actor in actors], "changed": changed,
            "warnings": parsed.warnings}


def run(args: Namespace) -> dict[str, Any]:
    return init(args) if args.run_step == "init" else bind(args)
