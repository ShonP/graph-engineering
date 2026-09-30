import copy
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from helpers import dump, fixture
from graph_control.common import Invalid, file_hash, fingerprint
from graph_control.identity import snapshot
from graph_control.preflight import preflight
from graph_control.run import Run


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data, _, self.now = fixture(self.root)

    def check(self):
        return preflight(Run.parse(self.data), Path(self.data["profile"]), Path(self.data["graph"]), self.now)

    def profile(self, content):
        path = Path(self.data["profile"])
        path.write_text(content)
        self.data["profile_sha256"] = file_hash(path)

    def test_public_cli_preflight(self):
        self.assertIn("python", self.check())

    def test_runtime_missing_is_blocked(self):
        self.profile("stacks: {}\n")
        with self.assertRaisesRegex(Invalid, "runtime profile missing"):
            self.check()

    def test_reduced_graph_cannot_skip_qa(self):
        graph = Path(self.data["graph"])
        graph.write_text(graph.read_text().replace("## node: qa", "## node: absent-qa"))
        self.data["graph_sha256"] = file_hash(graph)
        with self.assertRaises(Invalid):
            self.check()

    def test_cannot_map_review_as_qa(self):
        self.data["capability_nodes"]["qa"] = "review"
        with self.assertRaisesRegex(Invalid, "required role"):
            self.check()

    def test_same_branch_wrong_worktree_and_dirty_changes(self):
        source = self.data["candidate"]["sources"][0]
        (Path(source["root"]) / "app.py").write_text("print('wrong candidate')\n")
        with self.assertRaisesRegex(Invalid, "candidate changed"):
            self.check()

    def test_untracked_contents_affect_identity(self):
        root = Path(self.data["candidate"]["sources"][0]["root"])
        first = snapshot(root, "app")
        path = root / "new.py"
        path.write_text("first")
        second = snapshot(root, "app")
        path.write_text("other")
        third = snapshot(root, "app")
        self.assertEqual(len({first.dirty_sha256, second.dirty_sha256, third.dirty_sha256}), 3)

    def test_model_and_skills_availability(self):
        self.data["actors"][1]["resolved_model"] = "unavailable"
        with self.assertRaisesRegex(Invalid, "model unavailable"):
            self.check()
        self.data["actors"][1]["resolved_model"] = "host-model"
        self.data["actors"][1]["skills"] = ["/missing/SKILL.md"]
        with self.assertRaisesRegex(Invalid, "skill unavailable"):
            self.check()

    def test_case_unknown_or_missing_cannot_hide_behind_ci_green(self):
        self.data["checks"][2]["case_ids"] = ["UNKNOWN"]
        with self.assertRaisesRegex(Invalid, "unknown case"):
            self.check()

    def test_profile_duplicate_keys_and_unavailable_command(self):
        self.profile("runtime: {}\nruntime: {}\n")
        with self.assertRaisesRegex(Invalid, "duplicate YAML"):
            self.check()
        self.profile("runtime: {none: CLI}\n")
        self.data["tools"].append("graph-control-nonexistent-tool")
        with self.assertRaisesRegex(Invalid, "executable unavailable"):
            self.check()

    def live(self):
        identity = {"worker_revision": self.data["candidate"]["sources"][0]["revision"],
                    "images_sha256": "1" * 64, "corpus_sha256": "2" * 64,
                    "sources_sha256": fingerprint(self.data["candidate"]["sources"]),
                    "run_id": self.data["id"], "instance_id": "unique-runtime-instance"}
        hashed = fingerprint(identity)
        identity.update(fingerprint=hashed, observed_at=self.now.isoformat())
        self.data["candidate"]["runtime"] = hashed
        self.data["runtime_identity"] = dump(self.root / "runtime.json", identity)
        self.profile("runtime:\n  command: make test-api-acceptance\napi:\n  collection: bruno\n  schema: /openapi.json\n")
        return identity

    def test_harness_runtime_command_supported_without_executing_it(self):
        self.live()
        self.data["requires_api"] = True
        self.check()

    def test_api_collection_must_exist_in_candidate(self):
        self.live()
        self.data["requires_api"] = True
        self.profile("runtime: {command: make test-api-acceptance}\napi: {collection: missing, schema: /openapi.json}\n")
        with self.assertRaisesRegex(Invalid, "Bruno collection unavailable"):
            self.check()

    def test_readiness_can_precede_runtime_but_candidate_gate_cannot(self):
        self.live()
        Path(self.data["runtime_identity"]).unlink()
        result = preflight(Run.parse(self.data), Path(self.data["profile"]), Path(self.data["graph"]),
                           self.now, readiness_only=True)
        self.assertEqual(result["phase"], "readiness")
        with self.assertRaises(FileNotFoundError):
            self.check()

    def test_stale_runtime_and_changed_corpus(self):
        identity = self.live()
        identity["observed_at"] = (self.now - timedelta(seconds=61)).isoformat()
        dump(Path(self.data["runtime_identity"]), identity)
        with self.assertRaisesRegex(Invalid, "expired"):
            self.check()
        identity["observed_at"] = self.now.isoformat()
        identity["corpus_sha256"] = "3" * 64
        dump(Path(self.data["runtime_identity"]), identity)
        with self.assertRaisesRegex(Invalid, "contents"):
            self.check()

    def test_runtime_cannot_attest_same_revision_different_dirty_source(self):
        self.live()
        root = Path(self.data["candidate"]["sources"][0]["root"])
        (root / "app.py").write_text("changed after runtime launch")
        self.data["candidate"]["sources"][0]["dirty_sha256"] = snapshot(root, "app").dirty_sha256
        with self.assertRaisesRegex(Invalid, "runtime source"):
            self.check()

    def test_bound_profile_drift(self):
        Path(self.data["profile"]).write_text("runtime: {none: changed}\n")
        with self.assertRaisesRegex(Invalid, "profile changed"):
            self.check()

    def test_design_missing_is_not_automatic_plan_approval(self):
        self.data["requires_design"] = True
        with self.assertRaisesRegex(Invalid, "design capability missing"):
            self.check()


if __name__ == "__main__":
    unittest.main()
