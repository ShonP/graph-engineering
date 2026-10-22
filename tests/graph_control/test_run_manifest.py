"""`run init` writes run.draft.json at open; `run bind` completes it into a run.json Run.parse accepts.

Fixtures are SYNTHETIC: a temp run dir named with an invented UUIDv7, a fake
plugin root, a one-line profile, and host observations taken from the helpers'
valid run.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import dump, fixture, plan_data
from graph_control import cli
from graph_control.common import file_hash, load
from graph_control.run import CAPABILITIES, Run

RUN_ID = "01a16429-bd22-7850-b231-66dfb8161418"
REPO = Path(__file__).resolve().parents[2]


class RunManifestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        self.valid, _, _ = fixture(root)
        self.run_dir = root / RUN_ID
        self.run_dir.mkdir()
        shutil.copy(REPO / "graphs/feature.md", self.run_dir / "graph.md")
        self.profile = root / "graph-profile.yaml"
        self.profile.write_text("runtime:\n  none: CLI verified through public commands\n")
        self.plugin = root / "plugin"
        (self.plugin / ".claude-plugin").mkdir(parents=True)
        (self.plugin / ".claude-plugin/plugin.json").write_text('{"name": "fixture", "version": "9.8.7"}')
        self.host = root / "host.json"
        dump(self.host, self.host_data())

    def host_data(self):
        return {"available_models": ["host-model"], "tools": ["git"],
                "resolution_source": "host capability discovery",
                "models": {role: {"requested": "policy-alias", "resolved": "host-model"} for role in CAPABILITIES},
                "checks": self.valid["checks"], "candidate": self.valid["candidate"], "runtime_identity": None}

    def cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["run", *argv])
        return code, json.loads(out.getvalue())

    def init(self, *extra):
        return self.cli("init", str(self.run_dir), "--profile", str(self.profile),
                        "--plugin-root", str(self.plugin), *extra)

    def bind(self):
        return self.cli("bind", str(self.run_dir), "--host", str(self.host))

    def write_plan(self):
        dump(self.run_dir / "plan.json", plan_data())

    def test_init_writes_only_the_draft(self):
        code, out = self.init("--requires-api")
        self.assertEqual((code, out["status"]), (0, "PASS"))
        self.assertEqual(sorted(p.name for p in self.run_dir.iterdir()), ["graph.md", "run.draft.json"])
        draft = load(self.run_dir / "run.draft.json")
        self.assertEqual(draft["id"], RUN_ID)
        self.assertEqual(draft["plugin_version"], "9.8.7")
        self.assertEqual(draft["plan"], str(self.run_dir / "plan.json"))
        self.assertEqual(draft["profile_sha256"], file_hash(self.profile))
        self.assertEqual(draft["graph_sha256"], file_hash(self.run_dir / "graph.md"))
        self.assertEqual(draft["capability_nodes"],
                         {"plan": "plan", "implement": "implement", "review": "review", "qa": "qa", "verify": "qa"})
        self.assertEqual((draft["requires_api"], draft["requires_design"]), (True, False))
        self.assertEqual(draft["runtime_max_age_seconds"], 120)

    def test_init_uses_a_verify_node_when_the_graph_has_one(self):
        shutil.copy(self.valid["graph"], self.run_dir / "graph.md")
        self.init()
        self.assertEqual(load(self.run_dir / "run.draft.json")["capability_nodes"]["verify"], "verify")

    def test_init_names_a_missing_capability_node(self):
        graph = self.run_dir / "graph.md"
        graph.write_text("## node: plan\nagent: planner\ngate: yes\nnext: implement\n\n"
                         "## node: implement\nagent: implementer\ngate: no\nnext: qa\n\n"
                         "## node: qa\nagent: qa\ngate: no\nnext: END\n")
        code, out = self.init()
        self.assertEqual((code, out["status"]), (1, "BLOCKED"))
        self.assertIn("review", out["reason"])
        self.assertFalse((self.run_dir / "run.draft.json").exists())

    def test_init_refuses_a_relative_profile(self):
        code, out = self.cli("init", str(self.run_dir), "--profile", "graph-profile.yaml",
                             "--plugin-root", str(self.plugin))
        self.assertEqual(code, 1)
        self.assertIn("--profile must be absolute", out["reason"])
        self.assertFalse((self.run_dir / "run.draft.json").exists())

    def test_init_refuses_a_plugin_manifest_that_is_not_an_object(self):
        (self.plugin / ".claude-plugin/plugin.json").write_text('["9.8.7"]')
        code, out = self.init()
        self.assertEqual(code, 1)
        self.assertEqual(out["reason"], "plugin.json must be an object")

    def test_init_twice_writes_the_same_bytes(self):
        self.init()
        first = (self.run_dir / "run.draft.json").read_bytes()
        self.init()
        self.assertEqual((self.run_dir / "run.draft.json").read_bytes(), first)

    def test_bind_before_plan_is_blocked(self):
        self.init()
        code, out = self.bind()
        self.assertEqual((code, out["status"]), (1, "BLOCKED"))
        self.assertEqual(out["reason"], f"missing {self.run_dir / 'plan.json'}")
        self.assertFalse((self.run_dir / "run.json").exists())

    def test_bind_without_a_draft_is_blocked(self):
        self.write_plan()
        code, out = self.bind()
        self.assertEqual(code, 1)
        self.assertIn("run.draft.json", out["reason"])

    def test_bind_writes_a_parsable_run(self):
        self.init()
        self.write_plan()
        code, out = self.bind()
        self.assertEqual((code, out["status"]), (0, "PASS"), out)
        data = load(self.run_dir / "run.json")
        run = Run.parse(data)
        self.assertEqual(out["run"], str(self.run_dir / "run.json"))
        self.assertEqual(sorted(out["actors"]), sorted(f"{role}-{RUN_ID}" for role in CAPABILITIES))
        self.assertEqual({actor.id for actor in run.actors}, {f"{actor.role}-{RUN_ID}" for actor in run.actors})
        self.assertEqual((out["changed"], out["warnings"]), ([], []))
        self.assertEqual(data["plan_sha256"], file_hash(self.run_dir / "plan.json"))
        self.assertEqual(run.plugin_version, "9.8.7")
        self.assertEqual(run.available_models, ("host-model",))
        self.assertTrue(all(actor.skills == () and actor.requested_model == "policy-alias" for actor in run.actors))

    def test_bind_rejects_an_invalid_plan(self):
        self.init()
        plan = plan_data()
        plan["tasks"] = []
        dump(self.run_dir / "plan.json", plan)
        code, _ = self.bind()
        self.assertEqual(code, 1)
        self.assertFalse((self.run_dir / "run.json").exists())

    def test_host_without_available_models_is_blocked(self):
        self.init()
        self.write_plan()
        host = self.host_data()
        del host["available_models"]
        dump(self.host, host)
        code, out = self.bind()
        self.assertEqual((code, out["status"]), (1, "BLOCKED"))
        self.assertIn("available_models", out["reason"])
        self.assertFalse((self.run_dir / "run.json").exists())

    def test_host_that_is_not_an_object_is_blocked(self):
        self.init()
        self.write_plan()
        dump(self.host, [self.host_data()])
        code, out = self.bind()
        self.assertEqual(code, 1)
        self.assertIn("must be an object", out["reason"])

    def test_host_with_an_unknown_key_is_blocked(self):
        self.init()
        self.write_plan()
        dump(self.host, {**self.host_data(), "session": "x"})
        code, out = self.bind()
        self.assertEqual(code, 1)
        self.assertIn("session", out["reason"])

    def test_host_missing_a_role_model_is_blocked(self):
        self.init()
        self.write_plan()
        host = self.host_data()
        del host["models"]["review"]
        dump(self.host, host)
        code, out = self.bind()
        self.assertEqual(code, 1)
        self.assertIn("review", out["reason"])

    def test_host_role_model_without_resolved_is_blocked(self):
        self.init()
        self.write_plan()
        host = self.host_data()
        del host["models"]["qa"]["resolved"]
        dump(self.host, host)
        code, out = self.bind()
        self.assertEqual(code, 1)
        self.assertIn("resolved", out["reason"])

    def test_run_that_fails_parse_writes_nothing(self):
        self.init()
        self.write_plan()
        host = self.host_data()
        host["models"]["qa"]["resolved"] = "missing-model"
        dump(self.host, host)
        code, out = self.bind()
        self.assertEqual(code, 1)
        self.assertIn("resolved model unavailable", out["reason"])
        self.assertFalse((self.run_dir / "run.json").exists())

    def test_profile_edited_between_init_and_bind_is_reported(self):
        self.init()
        self.write_plan()
        self.profile.write_text("runtime:\n  none: edited after init\n")
        code, out = self.bind()
        self.assertEqual(code, 0, out)
        self.assertEqual(out["changed"], ["profile"])
        self.assertEqual(load(self.run_dir / "run.json")["profile_sha256"], file_hash(self.profile))


if __name__ == "__main__":
    unittest.main()
