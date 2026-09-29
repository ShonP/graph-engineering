import copy
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from graph_control.common import file_hash, fingerprint
from graph_control.identity import snapshot


def plan_data():
    return {
        "schema_version": 1,
        "cases": [{"id": "AC-1", "given": "valid input", "when": "invoke the CLI", "then": "correct output",
                   "oracle": "exact returned value and exit status", "runner": "unittest",
                   "requires_real": False,
                   "witness": {"kind": "synthetic", "reference": "fixture.json", "claim": "known output"},
                   "transitions": []}],
        "tasks": [{"id": "T1", "depends_on": [], "produces": [{"id": "stage", "fields": ["status"]}],
                   "consumes": [], "writable_paths": ["app/stage/**"], "case_ids": ["AC-1"], "stateful": False}],
        "external_contracts": [],
    }


def dump(path, data):
    path.write_text(json.dumps(data))
    return str(path)


def fixture(root):
    root = root.resolve()
    repo = root / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "test@example.invalid"],
                 ["config", "user.name", "Test"], ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "app.py").write_text("print('ok')\n")
    (repo / "bruno").mkdir()
    (repo / "bruno/bruno.json").write_text('{"version":"1","name":"fixture","type":"collection"}')
    subprocess.run(["git", "-C", str(repo), "add", "app.py", "bruno/bruno.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture"], check=True)
    plan = root / "plan.json"
    dump(plan, plan_data())
    profile = root / "profile.yaml"
    profile.write_text("runtime:\n  none: CLI verified through public commands\ngates:\n  plan: owner\n")
    graph = root / "graph.md"
    graph.write_text("\n".join(
        f"## node: {node}\nagent: {agent}\ngate: {'yes' if node == 'plan' else 'no'}\nnext: {next_node}\n"
        for node, agent, next_node in [
            ("plan", "planner", "implement"), ("implement", "implementer", "review, qa"),
            ("review", "reviewer", "verify"), ("qa", "qa", "verify"), ("verify", "qa", "END")]))
    candidate = {"sources": [asdict(snapshot(repo, "app"))], "runtime": None,
                 "fixture_sha256": fingerprint([]), "schema_sha256": fingerprint([])}
    actors = [{"id": role + "-agent", "role": role, "requested_model": "policy-alias",
               "resolved_model": "host-model", "resolution_source": "host capability discovery",
               "skills": []} for role in ("plan", "implement", "review", "qa", "verify")]
    checks = [{"id": role, "capability": role, "kind": kind,
               "argv": [sys.executable, "-m", "unittest"], "cwd": str(repo),
               "case_ids": ["AC-1"], "max_age_seconds": 600}
              for role, kind in [("implement", "test"), ("review", "analysis"), ("qa", "public"), ("verify", "final")]]
    plugin_version = json.loads((Path(__file__).resolve().parents[2] / ".claude-plugin/plugin.json").read_text())["version"]
    run = {"schema_version": 1, "id": "fixture-run", "plugin_version": plugin_version,
           "plan": str(plan), "plan_sha256": file_hash(plan),
           "profile": str(profile), "profile_sha256": file_hash(profile),
           "graph": str(graph), "graph_sha256": file_hash(graph), "candidate": candidate,
           "capability_nodes": {role: role for role in ("plan", "implement", "review", "qa", "verify")},
           "checks": checks, "actors": actors, "available_models": ["host-model"], "tools": ["git"],
           "runtime_identity": None, "runtime_max_age_seconds": 60, "requires_api": False,
           "requires_design": False}
    log = root / "result.log"
    log.write_text("acceptance output\n")
    now = datetime.now(timezone.utc)
    receipts = [{"check_id": check["id"], "actor": check["capability"] + "-agent", "model": "host-model",
                 "run_sha256": fingerprint(run), "candidate": copy.deepcopy(candidate), "argv": check["argv"],
                 "cwd": check["cwd"], "status": "PASS", "exit_code": 0, "executed": 1, "skipped": 0,
                 "cases": [{"id": "AC-1", "status": "PASS"}], "observed_at": now.isoformat(),
                 "log_path": str(log), "log_sha256": file_hash(log), "findings": {"blocking": 0, "important": 0}}
                for check in checks]
    return run, receipts, now
