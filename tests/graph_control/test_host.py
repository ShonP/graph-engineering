"""host-check: host inspection before a wave (AC-W3-HC-01) and its CLI command.

Fixtures are SYNTHETIC: throwaway repos (plain, bare, and a clone behind its
origin) and inline profiles. Load is patched because the real load average
cannot be steered; docker is replaced by a subprocess spy, which is also what
proves a profile without docker or compose is never probed.
"""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli, host
from graph_control.commands import iter_commands

GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
ENV = {key: value for key, value in os.environ.items() if key not in GIT_VARS}
REAL_RUN = subprocess.run


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null", "-c", "user.email=t@example.invalid",
                    "-c", "user.name=Test", "-c", "commit.gpgsign=false", *args],
                   check=True, capture_output=True, env=ENV)


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.repo = self.tmp / "repo"
        git(self.tmp, "init", "-q", "-b", "main", str(self.repo))
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "base")
        self.calls = []
        self.docker = 0  # the spy's docker exit status, or an exception class to raise

    def spy(self, argv, *args, **kwargs):
        self.calls.append((list(argv), kwargs))
        if argv[0] != "docker":
            return REAL_RUN(argv, *args, **kwargs)
        if self.docker is subprocess.TimeoutExpired:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        if isinstance(self.docker, type):
            raise self.docker(argv[0])
        return subprocess.CompletedProcess(argv, self.docker, "", "")

    def check(self, *argv, root=None, profile=None, min_free_gb="0"):
        args = ["host-check", "--root", str(root or self.repo), "--min-free-gb", min_free_gb, *argv]
        if profile is not None:
            path = self.tmp / "graph-profile.yaml"
            path.write_text(profile)
            args += ["--profile", str(path)]
        out = io.StringIO()
        with mock.patch.object(host.subprocess, "run", side_effect=self.spy), contextlib.redirect_stdout(out):
            code = cli.main(args)
        return code, json.loads(out.getvalue())

    @staticmethod
    def found(result):
        return {finding["id"]: finding for finding in result["findings"]}

    def docker_calls(self):
        return [(argv, kwargs) for argv, kwargs in self.calls if argv[0] == "docker"]


class Disk(Fixture):
    def test_threshold_above_free_space_is_blocked_ac_w3_hc_01(self):
        code, result = self.check(min_free_gb="1000000000")
        self.assertEqual((code, result["status"]), (1, "BLOCKED"))
        finding = self.found(result)["disk-low"]
        self.assertEqual(finding["level"], "error")
        self.assertEqual(result["reason"], finding["message"])
        self.assertIn("1000000000 GB", finding["message"])

    def test_enough_free_space_passes(self):
        code, result = self.check()
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertNotIn("disk-low", self.found(result))

    def test_default_minimum_is_20_gb(self):
        self.assertEqual(cli.parser().parse_args(["host-check", "--root", "."]).min_free_gb, 20)

    def test_root_must_be_a_directory(self):
        code, result = self.check(root=self.tmp / "missing")
        self.assertEqual((code, result["status"]), (1, "BLOCKED"))
        self.assertIn("--root", result["reason"])


class Git(Fixture):
    def test_bare_repository_is_an_error_ac_w3_hc_01(self):
        bare = self.tmp / "bare.git"
        git(self.tmp, "init", "-q", "--bare", str(bare))
        code, result = self.check(root=bare)
        self.assertEqual((code, result["status"]), (0, "PASS"))
        self.assertEqual(self.found(result)["bare-repo"]["level"], "error")

    def test_plain_repository_has_no_git_findings(self):
        found = self.found(self.check()[1])
        self.assertNotIn("bare-repo", found)
        self.assertNotIn("base-behind", found)

    def test_default_branch_behind_its_upstream_is_info_from_local_refs(self):
        origin, other = self.tmp / "origin.git", self.tmp / "other"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(origin))
        git(self.repo, "remote", "add", "origin", str(origin))
        git(self.repo, "push", "-q", "-u", "origin", "main")
        git(self.repo, "remote", "set-head", "origin", "main")
        git(self.tmp, "clone", "-q", str(origin), str(other))
        for message in ("one", "two"):
            git(other, "commit", "-q", "--allow-empty", "-m", message)
        git(other, "push", "-q", "origin", "main")
        git(self.repo, "fetch", "-q", "origin")  # the fixture fetches; host-check never does
        self.calls.clear()
        finding = self.found(self.check()[1])["base-behind"]
        self.assertEqual(finding["level"], "info")
        self.assertIn("main is 2 commits behind origin/main", finding["message"])
        self.assertFalse([argv for argv, _ in self.calls if {"fetch", "pull", "remote"} & set(argv)])


class Docker(Fixture):
    COMPOSE = "runtime:\n  up: docker compose up -d --wait\n"

    def test_profile_without_docker_is_never_probed_ac_w3_hc_01(self):
        for profile in ("runtime:\n  up: npm run dev\n  command: ''\n", "runtime:\n  none: CLI only\n", None):
            with self.subTest(profile=profile):
                self.calls.clear()
                self.docker = 1
                self.assertNotIn("docker-unreachable", self.found(self.check(profile=profile)[1]))
                self.assertEqual(self.docker_calls(), [])

    def test_unreachable_docker_warns_and_is_probed_with_a_5_s_timeout(self):
        self.docker = 1
        finding = self.found(self.check(profile=self.COMPOSE)[1])["docker-unreachable"]
        self.assertEqual(finding["level"], "warn")
        (argv, kwargs), = self.docker_calls()
        self.assertEqual((argv, kwargs.get("timeout")), (["docker", "info"], 5))

    def test_runtime_command_naming_compose_is_probed(self):
        self.docker = 1
        result = self.check(profile="runtime:\n  command: bin/qa-harness --stack Compose\n")[1]
        self.assertIn("docker-unreachable", self.found(result))

    def test_missing_binary_and_timeout_warn(self):
        for failure in (FileNotFoundError, subprocess.TimeoutExpired):
            with self.subTest(failure=failure.__name__):
                self.docker = failure
                self.assertIn("docker-unreachable", self.found(self.check(profile=self.COMPOSE)[1]))

    def test_reachable_docker_has_no_finding(self):
        self.assertNotIn("docker-unreachable", self.found(self.check(profile=self.COMPOSE)[1]))
        self.assertEqual(len(self.docker_calls()), 1)


class Load(Fixture):
    def load(self, load1, cpus):
        with mock.patch.object(host.os, "getloadavg", return_value=(load1, 0.0, 0.0)), \
                mock.patch.object(host.os, "cpu_count", return_value=cpus):
            return self.found(self.check()[1])

    def test_load_at_or_above_core_count_warns(self):
        finding = self.load(8.0, 8)["load-high"]
        self.assertEqual(finding["level"], "warn")
        self.assertIn("8.00", finding["message"])

    def test_load_below_core_count_is_silent(self):
        self.assertNotIn("load-high", self.load(7.9, 8))


class Command(unittest.TestCase):
    def test_host_check_is_registered(self):
        self.assertIn("host-check", [module.NAME for module in iter_commands()])


if __name__ == "__main__":
    unittest.main()
