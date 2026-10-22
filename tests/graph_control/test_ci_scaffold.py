"""The run-once CI scaffold in templates/ci, applied to SYNTHETIC temp repos.

A stub `gh` on PATH logs its argv and answers `api --jq` by running jq over canned
status JSON, so `local-gate-status.sh` is exercised without the network.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.ci_workflows import load_workflows
from graph_control.doctor import Finding, diagnose

PLUGIN = Path(__file__).resolve().parents[2]
CI = PLUGIN / "templates" / "ci"
MANIFEST = json.loads((CI / "manifest.json").read_text())
STATUS = "scripts/ci/local-gate-status.sh"
GATE = "#!/usr/bin/env bash\nexit 0\n"
PROFILE = ("schema_version: 2\nruntime:\n  none: CLI verified through public commands\n"
           "ci:\n  gate: scripts/ci/gate.sh\n  hook: .githooks/pre-push\n")
TOOLS = ("bash", "git", "cat", "shasum", "sha256sum", "jq", "env", "nice", "nohup", "sleep")
SCAFFOLD = CI / "scaffold.py"
STUB_GH = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$STUB_LOG"
if [ "$1" = auth ]; then exit "${STUB_AUTH_RC:-0}"; fi
if [ "$1" = api ]; then
  for arg in "$@"; do [ "$arg" = POST ] && exit 0; done
  case "$2" in */statuses*) ;; */commits/*)
    printf x >> "$STUB_LOG.commits"; seen="$(<"$STUB_LOG.commits")"
    [ "${#seen}" -gt "${STUB_MISSING:-0}" ]; exit ;;
  esac
  while [ $# -gt 0 ]; do
    if [ "$1" = --jq ]; then exec jq -r "$2" "$STUB_JSON"; fi
    shift
  done
fi
"""
QOS = """on: push
jobs:
  verify:
    runs-on: self-hosted
    steps:
      - run: taskpolicy -b bash scripts/ci/gate.sh
"""


class Repo:
    def __init__(self, case: unittest.TestCase):
        base = Path(case.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root, self.tools, self.stub = base / "repo", base / "tools", base / "stub"
        self.log, self.output, self.json = base / "gh.log", base / "github_output", base / "statuses.json"
        for folder in (self.root, self.tools, self.stub):
            folder.mkdir()
        for tool in TOOLS:
            found = shutil.which(tool)
            if found:
                (self.tools / tool).symlink_to(found)
        case.assertTrue((self.tools / "jq").exists(), "the stub gh needs jq on PATH")
        (self.stub / "gh").write_text(STUB_GH)
        (self.stub / "gh").chmod(0o755)
        self.log.write_text("")
        self.output.write_text("")
        self.statuses([])
        self.git("init", "-q")
        self.write("scripts/ci/gate.sh", GATE)
        self.write("uv.lock", "version = 1\n")
        self.write(".claude/graph-profile.yaml", PROFILE)
        self.scaffold()
        self.git("add", "-A")
        self.git("commit", "-qm", "init")

    def env(self, gh: bool = True, **extra: str) -> dict[str, str]:
        path = f"{self.stub}{os.pathsep}{self.tools}" if gh else str(self.tools)
        return {"PATH": path, "HOME": str(self.root.parent), "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "STUB_LOG": str(self.log), "STUB_JSON": str(self.json), **extra}

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, env=self.env(), check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def scaffold(self, gate: str = "scripts/ci/gate.sh", write: bool = True) -> subprocess.CompletedProcess:
        argv = [sys.executable, str(SCAFFOLD), "--root", str(self.root), f"--gate={gate}"]
        return subprocess.run(argv + (["--write"] if write else []), env=self.env(), capture_output=True, text=True,
                              timeout=60)

    def copy_verbatim(self) -> None:
        for entry in MANIFEST["files"]:
            target = self.root / entry["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(CI / entry["source"], target)

    def hooks_path(self) -> str:
        return subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=self.root, env=self.env(),
                              capture_output=True, text=True).stdout.strip()

    def statuses(self, rows: list[dict[str, str]]) -> None:
        self.json.write_text(json.dumps(rows))

    def run(self, *args: str, gh: bool = True, stdin: str = "", **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([shutil.which("bash"), *args], cwd=self.root, env=self.env(gh, **extra),
                              input=stdin, capture_output=True, text=True, timeout=60)

    def key(self) -> str:
        return self.run(STATUS, "key").stdout.strip()

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines()

    def posted(self) -> list[str]:
        return [line for line in self.calls() if "POST" in line]

    def wait_posted(self, count: int = 1) -> list[str]:
        deadline = time.monotonic() + 20
        while len(self.posted()) < count and time.monotonic() < deadline:
            time.sleep(0.1)
        return self.posted()

    def publisher_log(self) -> Path:
        return self.root / ".git" / "local-gate.log"

    def wait_log(self, needle: str) -> str:
        deadline = time.monotonic() + 20
        while needle not in (text := self.publisher_log().read_text() if self.publisher_log().exists() else "") \
                and time.monotonic() < deadline:
            time.sleep(0.1)
        return text


def status(state: str, description: str, context: str = "local-gate") -> dict[str, str]:
    return {"state": state, "description": description, "context": context}


class Manifest(unittest.TestCase):
    def test_manifest_lists_the_three_scaffold_files_with_modes(self):
        rows = {(e["source"], e["target"], e["mode"]) for e in MANIFEST["files"]}
        self.assertEqual(rows, {("pre-push", ".githooks/pre-push", "755"),
                                ("local-gate-status.sh", STATUS, "755"),
                                ("gate.yml", ".github/workflows/gate.yml", "644")})
        for source, _, _ in rows:
            self.assertTrue((CI / source).is_file(), source)

    def test_scaffold_never_writes_the_gate_script(self):
        self.assertNotIn("scripts/ci/gate.sh", {e["target"] for e in MANIFEST["files"]})


class Key(unittest.TestCase):
    def test_key_hashes_gate_script_then_existing_lockfiles_in_order(self):
        repo = Repo(self)
        repo.write("go.sum", "sum\n")
        expected = hashlib.sha256(GATE.encode() + b"version = 1\n" + b"sum\n").hexdigest()
        result = repo.run(STATUS, "key")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, expected))

    def test_key_reads_the_gate_script_named_by_gate_script(self):
        repo = Repo(self)
        repo.write("ci/other.sh", "other\n")
        expected = hashlib.sha256(b"other\n" + b"version = 1\n").hexdigest()
        self.assertEqual(repo.run(STATUS, "key", GATE_SCRIPT="ci/other.sh").stdout.strip(), expected)

    def test_missing_gate_script_has_no_key(self):
        repo = Repo(self)
        result = repo.run(STATUS, "key", GATE_SCRIPT="ci/missing.sh")
        self.assertEqual((result.returncode != 0, result.stdout), (True, ""))


class Check(unittest.TestCase):
    def assertUnverified(self, repo: Repo, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("verified=false", result.stdout)
        self.assertEqual(repo.output.read_text(), "verified=false\n")

    def test_no_gh_on_path_is_unverified(self):
        repo = Repo(self)
        repo.statuses([status("success", f"key={repo.key()}")])
        self.assertUnverified(repo, repo.run(STATUS, "check", gh=False, GH_TOKEN="t", GITHUB_OUTPUT=str(repo.output)))

    def test_no_token_is_unverified(self):
        repo = Repo(self)
        repo.statuses([status("success", f"key={repo.key()}")])
        self.assertUnverified(repo, repo.run(STATUS, "check", GITHUB_OUTPUT=str(repo.output)))

    def test_status_with_another_key_is_unverified(self):
        repo = Repo(self)
        stale = repo.key()
        repo.write("uv.lock", "version = 2\n")
        repo.git("commit", "-qam", "bump lock")
        repo.statuses([status("success", f"key={stale}")])
        self.assertUnverified(repo, repo.run(STATUS, "check", GH_TOKEN="t", GITHUB_OUTPUT=str(repo.output)))

    def test_newest_local_gate_status_decides(self):
        repo = Repo(self)
        key = repo.key()
        repo.statuses([status("success", "other", context="ci"), status("failure", f"key={key}"),
                       status("success", f"key={key}")])
        self.assertUnverified(repo, repo.run(STATUS, "check", GH_TOKEN="t", GITHUB_OUTPUT=str(repo.output)))

    def test_pending_status_with_the_key_is_unverified(self):
        repo = Repo(self)
        repo.statuses([status("pending", f"key={repo.key()}")])
        self.assertUnverified(repo, repo.run(STATUS, "check", GITHUB_TOKEN="t", GITHUB_OUTPUT=str(repo.output)))

    def test_matching_status_is_verified_on_head(self):
        repo = Repo(self)
        repo.statuses([status("success", "x", context="ci"), status("success", f"key={repo.key()}")])
        result = repo.run(STATUS, "check", GH_TOKEN="t", GITHUB_OUTPUT=str(repo.output))
        self.assertEqual((result.returncode, repo.output.read_text()), (0, "verified=true\n"), result.stderr)
        self.assertIn("verified=true", result.stdout)
        head = repo.git("rev-parse", "HEAD")
        self.assertTrue(any(f"commits/{head}/statuses" in call for call in repo.calls()), repo.calls())

    def test_sha_argument_then_github_sha_pick_the_commit(self):
        repo = Repo(self)
        repo.statuses([status("success", f"key={repo.key()}")])
        repo.run(STATUS, "check", "a" * 40, GH_TOKEN="t", GITHUB_SHA="b" * 40)
        repo.run(STATUS, "check", GH_TOKEN="t", GITHUB_SHA="b" * 40)
        api = [call for call in repo.calls() if call.startswith("api")]
        self.assertIn(f"commits/{'a' * 40}/statuses", api[0])
        self.assertIn(f"commits/{'b' * 40}/statuses", api[1])


class Publish(unittest.TestCase):
    def assertRefused(self, repo: Repo, result: subprocess.CompletedProcess, reason: str) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("local-gate: not published:", result.stdout)
        self.assertIn(reason, result.stdout)
        self.assertEqual(repo.posted(), [])

    def test_untracked_file_refuses_as_dirty(self):
        repo = Repo(self)
        repo.write("new.txt", "x\n")
        self.assertRefused(repo, repo.run(STATUS, "publish"), "dirty")

    def test_modified_file_refuses_as_dirty(self):
        repo = Repo(self)
        repo.write("uv.lock", "changed\n")
        self.assertRefused(repo, repo.run(STATUS, "publish"), "dirty")

    def test_missing_gh_refuses(self):
        repo = Repo(self)
        self.assertRefused(repo, repo.run(STATUS, "publish", gh=False), "gh not found")

    def test_unauthenticated_gh_refuses(self):
        repo = Repo(self)
        self.assertRefused(repo, repo.run(STATUS, "publish", STUB_AUTH_RC="1"), "auth")

    def test_clean_authenticated_tree_posts_the_key_on_head_in_the_background(self):
        repo = Repo(self)
        key, head = repo.key(), repo.git("rev-parse", "HEAD")
        result = repo.run(STATUS, "publish")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("once the remote has it", result.stdout)
        self.assertEqual(repo.wait_posted(), [f"api -X POST repos/{{owner}}/{{repo}}/statuses/{head} -f state=success "
                                              f"-f context=local-gate -f description=key={key}"])

    def test_publish_returns_before_the_remote_has_the_commit(self):
        repo = Repo(self)
        started = time.monotonic()
        result = repo.run(STATUS, "publish", STUB_MISSING="1000", LOCAL_GATE_WAIT="2", LOCAL_GATE_POLL="0.2")
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not on the remote", repo.wait_log("not on the remote"))
        self.assertEqual(repo.posted(), [])


class Post(unittest.TestCase):
    def test_posts_only_after_the_remote_has_the_commit(self):
        repo = Repo(self)
        head = repo.git("rev-parse", "HEAD")
        result = repo.run(STATUS, "post", head, "k", STUB_MISSING="2", LOCAL_GATE_POLL="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [call for call in repo.calls() if call.startswith("api")]
        self.assertEqual([("POST" in call, f"commits/{head}" in call) for call in calls],
                         [(False, True)] * 3 + [(True, False)])
        self.assertIn("published key=k", result.stdout)

    def test_gives_up_at_the_deadline_without_posting(self):
        repo = Repo(self)
        result = repo.run(STATUS, "post", "a" * 40, "k", STUB_MISSING="1000", LOCAL_GATE_WAIT="1",
                          LOCAL_GATE_POLL="0.2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not published", result.stdout)
        self.assertIn("not on the remote", result.stdout)
        self.assertEqual(repo.posted(), [])


class PrePush(unittest.TestCase):
    def push(self, repo: Repo, sha: str) -> subprocess.CompletedProcess:
        return repo.run(".githooks/pre-push", "origin", "url",
                        stdin=f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n")

    def test_green_gate_on_pushed_head_publishes(self):
        repo = Repo(self)
        result = self.push(repo, repo.git("rev-parse", "HEAD"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(repo.wait_posted()), 1)

    def test_pushing_another_sha_does_not_publish(self):
        repo = Repo(self)
        self.assertEqual(self.push(repo, "c" * 40).returncode, 0)
        self.assertFalse(repo.publisher_log().exists())
        self.assertEqual(repo.posted(), [])

    def test_red_gate_fails_the_push_and_publishes_nothing(self):
        repo = Repo(self)
        repo.write("scripts/ci/gate.sh", "#!/usr/bin/env bash\nexit 3\n")
        repo.git("commit", "-qam", "red gate")
        self.assertNotEqual(self.push(repo, repo.git("rev-parse", "HEAD")).returncode, 0)
        self.assertEqual(repo.posted(), [])

    def test_hook_runs_the_gate_under_nice_never_taskpolicy(self):
        hook = (CI / "pre-push").read_text()
        self.assertIn("nice -n 10 bash", hook)
        self.assertNotIn("taskpolicy", hook)


class Workflow(unittest.TestCase):
    def test_gate_job_skips_only_on_a_verified_local_gate(self):
        repo = Repo(self)
        [workflow], rows = load_workflows(repo.root)
        self.assertEqual(rows, [])
        self.assertEqual(set(workflow.on), {"push", "pull_request"})
        self.assertNotIn("paths", json.dumps(workflow.on))
        [job] = workflow.jobs
        self.assertEqual(job.id, "gate")
        checkout, local, gate = job.steps
        self.assertTrue(checkout.uses.startswith("actions/checkout@"))
        self.assertEqual(checkout.with_, {})
        self.assertEqual(local.run.strip(), f"bash {STATUS} check || true")
        self.assertEqual(gate.run.strip(), "nice -n 10 bash scripts/ci/gate.sh")
        self.assertIn("bash __CI_GATE__.sh", (CI / "gate.yml").read_text())
        self.assertEqual(gate.if_, "steps.local.outputs.verified != 'true'")
        text = (CI / "gate.yml").read_text()
        self.assertIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn("contents: read", text)
        self.assertIn("statuses: read", text)


class Render(unittest.TestCase):
    def test_gate_is_rendered_into_every_target(self):
        repo = Repo(self)
        repo.write("scripts/check.sh", GATE)
        for entry in MANIFEST["files"]:
            (repo.root / entry["target"]).unlink()
        result = repo.scaffold("scripts/check.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in MANIFEST["files"]:
            target = repo.root / entry["target"]
            text = target.read_text()
            self.assertNotIn("__CI_GATE__", text)
            self.assertIn("scripts/check.sh", text)
            self.assertEqual(oct(target.stat().st_mode & 0o777)[2:], entry["mode"])
        self.assertEqual(load_workflows(repo.root)[0][0].jobs[0].steps[2].run.strip(),
                         "nice -n 10 bash scripts/check.sh")

    def test_unsafe_or_missing_gate_refuses_and_writes_nothing(self):
        repo = Repo(self)
        for entry in MANIFEST["files"]:
            (repo.root / entry["target"]).unlink()
        for gate in ("../x.sh", "a b.sh", "x;rm.sh", "/abs.sh", "scripts/missing.sh", "-x.sh"):
            with self.subTest(gate):
                result = repo.scaffold(gate)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("ci.gate", result.stderr)
                self.assertFalse(any((repo.root / e["target"]).exists() for e in MANIFEST["files"]))

    def test_existing_different_target_is_kept(self):
        repo = Repo(self)
        repo.write(".github/workflows/gate.yml", "custom\n")
        result = repo.scaffold()
        self.assertEqual((repo.root / ".github/workflows/gate.yml").read_text(), "custom\n")
        self.assertIn("kept .github/workflows/gate.yml", result.stdout)
        self.assertIn("unchanged .githooks/pre-push", result.stdout)

    def test_dry_run_writes_nothing(self):
        repo = Repo(self)
        repo.git("config", "--unset", "core.hooksPath")
        (repo.root / ".githooks/pre-push").unlink()
        result = repo.scaffold(write=False)
        self.assertIn("would write .githooks/pre-push", result.stdout)
        self.assertFalse((repo.root / ".githooks/pre-push").exists())
        self.assertEqual(repo.hooks_path(), "")

    def test_no_other_hooks_sets_hooks_path(self):
        self.assertEqual(Repo(self).hooks_path(), ".githooks")

    def test_existing_hook_setup_keeps_hooks_path_and_says_how_to_chain(self):
        cases = {".husky": lambda r: r.write(".husky/pre-commit", "x\n"),
                 ".pre-commit-config.yaml": lambda r: r.write(".pre-commit-config.yaml", "repos: []\n"),
                 "lefthook.yml": lambda r: r.write("lefthook.yml", "pre-push: {}\n"),
                 ".git/hooks/pre-commit": lambda r: r.write(".git/hooks/pre-commit", "x\n"),
                 "core.hooksPath=hooks": lambda r: r.git("config", "core.hooksPath", "hooks")}
        for name, arrange in cases.items():
            with self.subTest(name):
                repo = Repo(self)
                repo.git("config", "--unset", "core.hooksPath")
                arrange(repo)
                before = repo.hooks_path()
                result = repo.scaffold()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(repo.hooks_path(), before)
                self.assertIn(name, result.stdout)
                self.assertIn(".githooks/pre-push", result.stdout)
                self.assertIn("core.hooksPath not set", result.stdout)


class Doctor(unittest.TestCase):
    def test_verbatim_copy_with_another_gate_is_flagged(self):
        repo = Repo(self)
        repo.write("scripts/check.sh", GATE)
        (repo.root / "scripts/ci/gate.sh").unlink()
        repo.write(".claude/graph-profile.yaml", PROFILE.replace("scripts/ci/gate.sh", "scripts/check.sh"))
        repo.copy_verbatim()
        missing = [f.message for f in diagnose(repo.root, PLUGIN, quick=False) if f.id == "ci-gate-missing"]
        self.assertEqual(len(missing), 2, missing)
        self.assertTrue(all("`__CI_GATE__.sh`" in message for message in missing), missing)

    def test_rendered_scaffold_with_another_gate_is_clean(self):
        repo = Repo(self)
        repo.write("scripts/check.sh", GATE)
        (repo.root / "scripts/ci/gate.sh").unlink()
        for entry in MANIFEST["files"]:
            (repo.root / entry["target"]).unlink()
        repo.write(".claude/graph-profile.yaml", PROFILE.replace("scripts/ci/gate.sh", "scripts/check.sh"))
        self.assertEqual(repo.scaffold("scripts/check.sh").returncode, 0)
        rows = [f for f in diagnose(repo.root, PLUGIN, quick=False)
                if f.id.startswith("ci-") and f.level in ("warn", "error")]
        self.assertEqual(rows, [])

    def test_scaffolded_repo_has_no_ci_warning_or_error(self):
        repo = Repo(self)
        rows = [f for f in diagnose(repo.root, PLUGIN, quick=False)
                if f.id.startswith("ci-") and f.level in ("warn", "error")]
        self.assertEqual(rows, [])

    def test_full_mode_reports_ci_findings_and_quick_mode_none(self):
        repo = Repo(self)
        repo.write(".github/workflows/gate.yml", QOS)
        full = diagnose(repo.root, PLUGIN, quick=False)
        qos = [f for f in full if f.id == "ci-background-qos"]
        self.assertEqual(len(qos), 1)
        self.assertIsInstance(qos[0], Finding)
        self.assertEqual(qos[0].level, "warn")
        self.assertEqual([f for f in diagnose(repo.root, PLUGIN, quick=True) if f.id.startswith("ci-")], [])

    def test_full_mode_reports_declared_ci_findings(self):
        repo = Repo(self)
        repo.write(".claude/graph-profile.yaml", PROFILE + "  deploy: {dev: d, smoke: s, prod: p}\n")
        self.assertIn("ci-prod-no-promote", {f.id for f in diagnose(repo.root, PLUGIN, quick=False)})

    def test_quick_mode_imports_no_ci_module(self):
        repo = Repo(self)
        repo.write(".github/workflows/gate.yml", QOS)
        probe = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                 "from graph_control.doctor import diagnose; diagnose(Path(sys.argv[2]), Path(sys.argv[3]), quick=True); "
                 "print(sorted(m for m in sys.modules if m.startswith('graph_control.ci_')))")
        result = subprocess.run([sys.executable, "-c", probe, str(PLUGIN / "scripts"), str(repo.root), str(PLUGIN)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "[]")


class Modes(unittest.TestCase):
    def test_executable_templates_carry_an_exec_bit_in_the_manifest_only(self):
        for entry in MANIFEST["files"]:
            self.assertIn(entry["mode"], ("755", "644"))
            if entry["mode"] == "755":
                self.assertTrue((CI / entry["source"]).read_text().startswith("#!/usr/bin/env bash\n"))

    def test_unknown_mode_exits_nonzero(self):
        repo = Repo(self)
        result = repo.run(STATUS, "bogus")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", result.stderr)


if __name__ == "__main__":
    unittest.main()
