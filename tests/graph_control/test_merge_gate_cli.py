import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

if importlib.util.find_spec("wcmatch") is None:
    raise unittest.SkipTest("needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

CLI = Path(__file__).resolve().parents[2] / "scripts" / "graph-control.py"
PROFILE = ".claude/graph-profile.yaml"
SHA = "c" * 40
GREEN = {"schema_version": 1, "verdict": "PASS", "reviewed": {"base": SHA, "head": SHA}, "findings": []}


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}}
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                          check=True, capture_output=True, text=True, env=env).stdout.strip()


def profile_text(mode, owner_classes=None):
    lines = ["gates:", f'  merge_auto: "{mode}"']
    if owner_classes is not None:
        lines.append(f"  owner_classes: [{', '.join(owner_classes)}]")
    return "\n".join(lines) + "\n"


class MergeGate(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "test@example.invalid"],
                     ["config", "user.name", "Test"], ["config", "commit.gpgsign", "false"]):
            git(self.repo, *args)
        self.run_dir = self.tmp / "run"
        self.run_dir.mkdir()
        helpers.dump(self.run_dir / "plan.json", helpers.plan_data())
        helpers.dump(self.run_dir / "findings.T1.json", GREEN)
        helpers.dump(self.run_dir / "qa-findings.json", GREEN)
        (self.run_dir / "qa.md").write_text("# qa\n\nFAIL early draft\nPASS\n")
        source = self.tmp / "receipts-source"
        source.mkdir()
        run, receipts, _ = helpers.fixture(source)
        helpers.dump(self.run_dir / "run.json", run)
        helpers.dump(self.run_dir / "receipts.json", {"schema_version": 1, "receipts": receipts})

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self, files, message):
        for name, content in files.items():
            self.write(name, content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", message)
        return git(self.repo, "rev-parse", "HEAD")

    def gate(self, base, *extra):
        result = subprocess.run([sys.executable, str(CLI), "merge-gate", str(self.run_dir), "--root", str(self.repo),
                                 "--base", base, *extra], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def assert_failed(self, out, prefix):
        self.assertTrue(any(reason.startswith(f"failed: {prefix}") for reason in out["reasons"]), out["reasons"])


class Base(MergeGate):
    def test_ac_t7_base_branch_profile_cannot_open_its_own_gate(self):
        base = self.commit({PROFILE: profile_text("off"), "src/app.py": "print('ok')\n"}, "base")
        self.commit({PROFILE: profile_text("when-green", []), "src/app.py": "print('more')\n"}, "branch")
        code, out = self.gate(base)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["status"], "PASS")
        self.assertIs(out["open"], False)
        self.assertEqual(out["mode"], "off")
        self.assertEqual(out["profile_source"], f"{base}:{PROFILE}")
        self.assertTrue(any(reason.startswith(f"failed: gate-floor {PROFILE}") for reason in out["reasons"]),
                        out["reasons"])

    def test_uncommitted_branch_profile_is_not_read_either(self):
        base = self.commit({PROFILE: profile_text("off"), "src/app.py": "print('ok')\n"}, "base")
        self.write(PROFILE, profile_text("when-green", []))
        self.write("src/app.py", "print('more')\n")
        code, out = self.gate(base)
        self.assertEqual((code, out["open"], out["mode"]), (0, False, "off"), out)
        self.assert_failed(out, "tree 2 uncommitted paths in the worktree")


class Committed(MergeGate):
    def test_uncommitted_revert_of_a_committed_floor_change_cannot_hide_it(self):
        base = self.commit({PROFILE: profile_text("when-green"), ".claude/graph-checks.json": "{}\n",
                            "src/app.py": "print('ok')\n"}, "base")
        self.commit({".claude/graph-checks.json": '{"x": 1}\n', "src/app.py": "print('more')\n"}, "branch")
        self.write(".claude/graph-checks.json", "{}\n")
        code, out = self.gate(base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assert_failed(out, "gate-floor .claude/graph-checks.json")
        self.assert_failed(out, "tree 1 uncommitted paths in the worktree, first .claude/graph-checks.json")

    def test_uncommitted_delete_of_an_owner_class_path_keeps_the_gate_shut(self):
        risk = "risk:\n  - id: spend\n    paths: [\"billing/**\"]\n"
        base = self.commit({PROFILE: profile_text("when-green") + risk, "src/app.py": "print('ok')\n"}, "base")
        self.commit({"billing/charge.py": "charge()\n"}, "branch")
        (self.repo / "billing" / "charge.py").unlink()
        code, out = self.gate(base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assert_failed(out, "tree 1 uncommitted paths in the worktree, first billing/charge.py")

    def test_untracked_file_keeps_the_gate_shut(self):
        base = self.commit({PROFILE: profile_text("when-green"), "src/app.py": "print('ok')\n"}, "base")
        self.commit({"src/app.py": "print('more')\n"}, "branch")
        self.write("notes.txt", "draft\n")
        code, out = self.gate(base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assert_failed(out, "tree 1 uncommitted paths in the worktree, first notes.txt")


class Open(MergeGate):
    def test_ac_t7_open_green_inputs_under_a_when_green_base_open_the_gate(self):
        base = self.commit({PROFILE: profile_text("when-green"), "src/app.py": "print('ok')\n"}, "base")
        self.commit({"src/app.py": "print('more')\n"}, "branch")
        code, out = self.gate(base)
        self.assertEqual(code, 0, out)
        self.assertIs(out["open"], True, out["reasons"])
        self.assertEqual(out["mode"], "when-green")
        self.assertEqual(out["risk_rows"], [])
        self.assertTrue(all(reason.startswith("held:") for reason in out["reasons"]), out["reasons"])

    def test_auto_merge_flag_sets_the_mode(self):
        base = self.commit({PROFILE: profile_text("off"), "src/app.py": "print('ok')\n"}, "base")
        self.commit({"src/app.py": "print('more')\n"}, "branch")
        code, out = self.gate(base, "--auto-merge")
        self.assertEqual((code, out["mode"], out["open"]), (0, "auto-merge", True), out)

    def test_profile_path_option_reads_that_file_at_base(self):
        base = self.commit({"conf/profile.yaml": profile_text("when-green"), "src/app.py": "print('ok')\n"}, "base")
        self.commit({"src/app.py": "print('more')\n"}, "branch")
        code, out = self.gate(base, "--profile-path", "conf/profile.yaml")
        self.assertEqual((code, out["mode"], out["profile_source"]), (0, "when-green", f"{base}:conf/profile.yaml"))


class AcT7Inputs(MergeGate):
    def setUp(self):
        super().setUp()
        self.base = self.commit({PROFILE: profile_text("when-green"), "src/app.py": "print('ok')\n"}, "base")
        self.commit({"src/app.py": "print('more')\n"}, "branch")

    def test_missing_latest_findings_file_blocks_and_names_it(self):
        missing = self.run_dir / "findings.T1.json"
        missing.unlink()
        code, out = self.gate(self.base)
        self.assertEqual((code, out["status"]), (1, "BLOCKED"), out)
        self.assertEqual(out["reason"], f"missing findings file: {missing}")

    def test_missing_qa_findings_file_blocks(self):
        (self.run_dir / "qa-findings.json").unlink()
        code, out = self.gate(self.base)
        self.assertEqual((code, out["status"]), (1, "BLOCKED"), out)
        self.assertIn("qa-findings.json", out["reason"])

    def test_open_important_finding_shuts_the_gate(self):
        finding = {"id": "F1", "severity": "important", "file": "src/app.py", "line": 1, "scenario": "s",
                   "rule": "r", "confidence": 0.9, "route": "patch", "needs_author_context": False, "status": "open"}
        helpers.dump(self.run_dir / "qa-findings.json", {**GREEN, "verdict": "FAIL", "findings": [finding]})
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False))
        self.assertIn("failed: findings 0 blocking, 1 important", out["reasons"])

    def test_missing_qa_md_shuts_the_gate(self):
        (self.run_dir / "qa.md").unlink()
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assert_failed(out, "qa")

    def test_qa_verdict_is_the_last_verdict_line(self):
        (self.run_dir / "qa.md").write_text("PASS draft\nnotes\n  INCOMPLETE: device lane\nPASSED is no verdict\n")
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assertIn("failed: qa verdict 'INCOMPLETE: device lane' is not PASS", out["reasons"])

    def test_static_only_pass_shuts_the_gate(self):
        (self.run_dir / "qa.md").write_text("# qa\n\n| AC-1 | VERIFIED |\n\nPASS (static-only)\n")
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assertIn("failed: qa PASS (static-only) is static-only, not a full PASS", out["reasons"])

    def test_pass_with_trailing_words_is_not_a_full_pass(self):
        (self.run_dir / "qa.md").write_text("PASS all cases\n")
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assert_failed(out, "qa verdict 'PASS all cases'")

    def test_missing_run_json_fails_verify(self):
        (self.run_dir / "run.json").unlink()
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assert_failed(out, "verify")
        self.assertTrue(any("run.json" in reason for reason in out["reasons"]), out["reasons"])

    def test_invalid_receipts_fail_verify_with_the_reason(self):
        helpers.dump(self.run_dir / "receipts.json", {"schema_version": 1, "receipts": []})
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assertTrue(any(reason.startswith("failed: verify") and "missing required check receipts" in reason
                            for reason in out["reasons"]), out["reasons"])

    def test_missing_qa_md_and_red_verify_list_both(self):
        (self.run_dir / "qa.md").unlink()
        (self.run_dir / "receipts.json").unlink()
        code, out = self.gate(self.base)
        self.assertEqual((code, out["open"]), (0, False), out)
        self.assert_failed(out, "qa")
        self.assert_failed(out, "verify")

    def test_no_profile_at_base_is_mode_off(self):
        tmp = self.tmp / "bare"
        tmp.mkdir()
        self.repo = tmp
        for args in (["init", "-q"], ["config", "user.email", "test@example.invalid"],
                     ["config", "user.name", "Test"], ["config", "commit.gpgsign", "false"]):
            git(self.repo, *args)
        base = self.commit({"src/app.py": "print('ok')\n"}, "base")
        self.commit({PROFILE: profile_text("when-green", []), "src/app.py": "print('more')\n"}, "branch")
        code, out = self.gate(base)
        self.assertEqual((code, out["open"], out["mode"]), (0, False, "off"), out)


class Refusals(MergeGate):
    def setUp(self):
        super().setUp()
        self.base = self.commit({PROFILE: profile_text("when-green"), "src/app.py": "print('ok')\n"}, "base")

    def test_profile_path_outside_the_repo_tree_blocks(self):
        for path in ("../profile.yaml", "/etc/profile.yaml", "-p", "a/../../b.yaml", ""):
            with self.subTest(path=path):
                code, out = self.gate(self.base, f"--profile-path={path}")
                self.assertEqual((code, out["status"]), (1, "BLOCKED"), out)
                self.assertIn("--profile-path must be a repo-relative path inside the tree", out["reason"])

    def test_profile_path_naming_a_directory_blocks(self):
        code, out = self.gate(self.base, "--profile-path", ".claude")
        self.assertEqual((code, out["status"]), (1, "BLOCKED"), out)
        self.assertIn("is a tree, not a profile file", out["reason"])

    def test_malformed_base_profile_blocks(self):
        base = self.commit({PROFILE: "gates: [unclosed\n"}, "malformed")
        code, out = self.gate(base)
        self.assertEqual((code, out["status"]), (1, "BLOCKED"), out)
        self.assertTrue(out["reason"].startswith(f"invalid profile YAML at {base}:{PROFILE}"), out)

    def test_base_profile_that_is_not_a_mapping_blocks(self):
        base = self.commit({PROFILE: "- merge_auto\n"}, "list")
        code, out = self.gate(base)
        self.assertEqual((code, out["reason"]), (1, "profile must be a YAML mapping"), out)

    def test_oversized_base_profile_blocks(self):
        base = self.commit({PROFILE: profile_text("when-green") + "#" * (1024 * 1024) + "\n"}, "huge")
        code, out = self.gate(base)
        self.assertEqual((code, out["status"], out["reason"]), (1, "BLOCKED", "profile exceeds 1 MiB"), out)

    def test_base_that_is_not_a_commit_blocks(self):
        code, out = self.gate("no-such-revision")
        self.assertEqual((code, out["status"]), (1, "BLOCKED"), out)

    def test_duplicate_key_in_base_profile_blocks(self):
        base = self.commit({PROFILE: 'gates:\n  merge_auto: "off"\n  merge_auto: "when-green"\n'}, "dup")
        code, out = self.gate(base)
        self.assertEqual((code, out["status"]), (1, "BLOCKED"), out)
        self.assertIn("duplicate YAML key", out["reason"])


if __name__ == "__main__":
    unittest.main()
