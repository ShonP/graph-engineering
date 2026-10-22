"""Doctor CI runtime checks over SYNTHETIC repos built in temp dirs from inline strings.

Line numbers are hand-counted from the inline YAML; the loader tests and the run's
prior-art spike witness that compose marks match file lines.
"""

import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.ci_runtime import STATUS_SCRIPT, findings

GATE = "scripts/ci/gate.sh"
PROFILE = {"ci": {"gate": GATE, "hook": ".githooks/pre-push"}}
HOOK = "#!/usr/bin/env bash\nset -e\nbash scripts/ci/gate.sh\n"

GATE_TWICE = """on: pull_request
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Gate
        run: bash scripts/ci/gate.sh
"""

GATE_SKIPPED = """on: pull_request
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: local
        run: bash scripts/ci/local-gate-status.sh check
      - name: Gate
        if: steps.local.outputs.verified != 'true'
        run: bash scripts/ci/gate.sh
"""

QOS = """on: pull_request
jobs:
  verify:
    runs-on: self-hosted
    steps:
      - name: Gate
        run: taskpolicy -c background bash scripts/ci/gate.sh
      - name: Lint
        run: |
          ionice -c3 make lint
"""

QOS_HOOK = "#!/usr/bin/env bash\nset -e\ntaskpolicy -b bash scripts/ci/gate.sh\n"

TAGS = """on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - name: Fetch tags
        run: git fetch origin --tags
  b:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: "false"
      - name: Release
        run: bash scripts/release.sh
"""

RELEASE = "#!/usr/bin/env bash\nset -e\ngit push origin --tags\n"


def repo(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def rows_with(rows, id_):
    return [row for row in rows if row[1] == id_]


class GateTwice(unittest.TestCase):
    def test_hook_and_workflow_both_run_gate(self):
        rows = findings(repo({".github/workflows/ci.yml": GATE_TWICE, ".githooks/pre-push": HOOK}), PROFILE)
        [(level, id_, message, fix)] = rows_with(rows, "ci-gate-twice")
        self.assertEqual((level, id_), ("warn", "ci-gate-twice"))
        self.assertIn(".github/workflows/ci.yml:8", message)
        self.assertIn(".githooks/pre-push", message)
        self.assertIn("bash scripts/ci/local-gate-status.sh check", fix)
        self.assertIn("steps.<id>.outputs.verified != 'true'", fix)

    def test_husky_hook_fallback(self):
        rows = findings(repo({".github/workflows/ci.yml": GATE_TWICE, ".husky/pre-push": HOOK}), PROFILE)
        [row] = rows_with(rows, "ci-gate-twice")
        self.assertIn(".husky/pre-push", row[2])

    def test_status_step_twin(self):
        rows = findings(repo({".github/workflows/ci.yml": GATE_SKIPPED, ".githooks/pre-push": HOOK}), PROFILE)
        self.assertEqual(rows_with(rows, "ci-gate-twice"), [])
        self.assertIn(STATUS_SCRIPT, GATE_SKIPPED)

    def test_gate_unset(self):
        root = repo({".github/workflows/ci.yml": GATE_TWICE, ".githooks/pre-push": HOOK})
        for profile in ({}, {"ci": {"gate": "", "hook": ".githooks/pre-push"}}):
            self.assertEqual(rows_with(findings(root, profile), "ci-gate-twice"), [])

    def test_hook_without_gate(self):
        root = repo({".github/workflows/ci.yml": GATE_TWICE, ".githooks/pre-push": "#!/bin/sh\nmake lint\n"})
        self.assertEqual(rows_with(findings(root, PROFILE), "ci-gate-twice"), [])

    def test_no_hook(self):
        self.assertEqual(rows_with(findings(repo({".github/workflows/ci.yml": GATE_TWICE}), PROFILE),
                         "ci-gate-twice"), [])


class BackgroundQos(unittest.TestCase):
    def test_workflow_and_hook(self):
        rows = findings(repo({".github/workflows/ci.yml": QOS, ".githooks/pre-push": QOS_HOOK}), {})
        found = rows_with(rows, "ci-background-qos")
        self.assertEqual([row[0] for row in found], ["warn"] * 3)
        self.assertIn(".github/workflows/ci.yml:7", found[0][2])
        self.assertIn(".github/workflows/ci.yml:9", found[1][2])
        self.assertIn(".githooks/pre-push:3", found[2][2])
        for row in found:
            self.assertIn("nice -n 10", row[3])

    def test_maintenance_utility_and_ionice_spaced(self):
        for command in ("taskpolicy -c maintenance make", "taskpolicy -c utility make", "ionice -c 3 make"):
            hook = f"#!/bin/sh\n{command}\n"
            [row] = rows_with(findings(repo({".githooks/pre-push": hook}), {}), "ci-background-qos")
            self.assertIn(".githooks/pre-push:2", row[2])

    def test_nice_twin(self):
        root = repo({".github/workflows/ci.yml": QOS.replace("taskpolicy -c background", "nice -n 10")
                     .replace("ionice -c3", "nice -n 10"),
                     ".githooks/pre-push": QOS_HOOK.replace("taskpolicy -b", "nice -n 10")})
        self.assertEqual(rows_with(findings(root, {}), "ci-background-qos"), [])

    def test_foreground_taskpolicy_and_best_effort_ionice(self):
        hook = "#!/bin/sh\ntaskpolicy -c user-interactive make\nionice -c 2 make\n"
        self.assertEqual(rows_with(findings(repo({".githooks/pre-push": hook}), {}), "ci-background-qos"), [])

    def test_profile_hook_path(self):
        root = repo({"hooks/pre-push": QOS_HOOK})
        [row] = rows_with(findings(root, {"ci": {"gate": "", "hook": "hooks/pre-push"}}), "ci-background-qos")
        self.assertIn("hooks/pre-push:3", row[2])


class TagsNoCredentials(unittest.TestCase):
    def test_direct_and_script(self):
        root = repo({".github/workflows/ci.yml": TAGS, "scripts/release.sh": RELEASE})
        a, b = rows_with(findings(root, {}), "ci-tags-no-credentials")
        self.assertEqual((a[0], b[0]), ("warn", "warn"))
        self.assertIn(".github/workflows/ci.yml:8", a[2])
        self.assertIn(".github/workflows/ci.yml:10", a[2])
        self.assertIn(".github/workflows/ci.yml:16", b[2])
        self.assertIn("scripts/release.sh", b[2])
        self.assertIn("persist-credentials: true", a[3])
        self.assertIn("artipacked", a[3])

    def test_true_twin(self):
        root = repo({".github/workflows/ci.yml": TAGS.replace('"false"', "true").replace("false", "true"),
                     "scripts/release.sh": RELEASE})
        self.assertEqual(rows_with(findings(root, {}), "ci-tags-no-credentials"), [])

    def test_default_credentials(self):
        text = TAGS.replace("        with:\n          persist-credentials: false\n", "").replace(
            '        with:\n          persist-credentials: "false"\n', "        with:\n          fetch-depth: 0\n")
        root = repo({".github/workflows/ci.yml": text, "scripts/release.sh": RELEASE})
        self.assertEqual(rows_with(findings(root, {}), "ci-tags-no-credentials"), [])

    def test_two_level_chain(self):
        root = repo({".github/workflows/ci.yml": TAGS.replace("git fetch origin --tags", "make test"),
                     "scripts/release.sh": "#!/bin/sh\nbash scripts/inner.sh\n",
                     "scripts/inner.sh": RELEASE})
        self.assertEqual(rows_with(findings(root, {}), "ci-tags-no-credentials"), [])

    def test_dot_slash_script_and_refspec_forms(self):
        for command in ("git fetch origin refs/tags/*:refs/tags/*", "git pull --tags",
                        "git push --follow-tags", "git push origin refs/tags/v1"):
            text = TAGS.replace("git fetch origin --tags", command).replace("bash scripts/release.sh",
                                                                            "./scripts/release.sh")
            root = repo({".github/workflows/ci.yml": text, "scripts/release.sh": RELEASE})
            self.assertEqual(len(rows_with(findings(root, {}), "ci-tags-no-credentials")), 2, command)

    def test_script_outside_repo_ignored(self):
        outside = repo({"release.sh": RELEASE})
        text = TAGS.replace("git fetch origin --tags", "make test").replace(
            "bash scripts/release.sh", f"bash ../{outside.name}/release.sh")
        self.assertEqual(rows_with(findings(repo({".github/workflows/ci.yml": text}), {}),
                                   "ci-tags-no-credentials"), [])

    def test_tag_step_in_other_job(self):
        text = TAGS.replace("bash scripts/release.sh", "make test").replace(
            "persist-credentials: false", "persist-credentials: true")
        self.assertEqual(rows_with(findings(repo({".github/workflows/ci.yml": text}), {}),
                                   "ci-tags-no-credentials"), [])


    def test_shell_flags_before_the_script(self):
        text = TAGS.replace("git fetch origin --tags", "make test").replace(
            "bash scripts/release.sh", "bash -e scripts/release.sh")
        root = repo({".github/workflows/ci.yml": text, "scripts/release.sh": RELEASE})
        [row] = rows_with(findings(root, {}), "ci-tags-no-credentials")
        self.assertIn("scripts/release.sh", row[2])


SCAFFOLD_JOB = GATE_SKIPPED.replace("bash scripts/ci/gate.sh", "nice -n 10 bash scripts/check.sh")


class GateMissing(unittest.TestCase):
    def test_hook_calls_a_missing_gate(self):
        hook = "#!/usr/bin/env bash\nset -e\nnice -n 10 bash scripts/check.sh </dev/null\n"
        [(level, _, message, fix)] = rows_with(findings(repo({".githooks/pre-push": hook}), {}), "ci-gate-missing")
        self.assertEqual(level, "warn")
        self.assertIn(".githooks/pre-push:3", message)
        self.assertIn("`scripts/check.sh`", message)
        self.assertIn("ci.gate", fix)

    def test_scaffolded_job_calls_a_missing_gate(self):
        root = repo({".github/workflows/gate.yml": SCAFFOLD_JOB, STATUS: "#!/bin/sh\n"})
        [row] = rows_with(findings(root, {}), "ci-gate-missing")
        self.assertIn(".github/workflows/gate.yml:11", row[2])
        self.assertIn("`scripts/check.sh`", row[2])

    def test_present_scripts_and_inline_commands_twin(self):
        hook = "#!/bin/sh\nbash scripts/check.sh\nbash -c 'make lint'\nbash -o pipefail -c x\n"
        root = repo({".githooks/pre-push": hook, ".github/workflows/gate.yml": SCAFFOLD_JOB,
                     "scripts/check.sh": "#!/bin/sh\n", STATUS: "#!/bin/sh\n"})
        self.assertEqual(rows_with(findings(root, {}), "ci-gate-missing"), [])

    def test_unscaffolded_job_scripts_are_not_checked(self):
        root = repo({".github/workflows/ci.yml": GATE_TWICE})
        self.assertEqual(rows_with(findings(root, {}), "ci-gate-missing"), [])


STATUS = "scripts/ci/local-gate-status.sh"


class ConfigInvalid(unittest.TestCase):
    def test_non_mapping_ci_is_one_row_and_runs_the_rest(self):
        for ci in (True, ["x"], "on"):
            rows = findings(repo({".githooks/pre-push": QOS_HOOK, GATE: "#!/bin/sh\n"}), {"ci": ci})
            self.assertEqual([row[1] for row in rows], ["ci-config-invalid", "ci-background-qos"], ci)
            self.assertEqual(rows[0][0], "warn")
            self.assertTrue(rows[0][2].startswith("ci: "), rows[0][2])

    def test_bad_gate_or_hook_is_one_row_and_skips_that_check(self):
        root = repo({".github/workflows/ci.yml": GATE_TWICE, ".githooks/pre-push": HOOK, "outside": HOOK})
        cases = {"hook": ["/etc/passwd", "../outside", 7, ["a"]], "gate": [5, "a b.sh", "../x.sh", [GATE]]}
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    rows = findings(root, {"ci": {**PROFILE["ci"], key: value}})
                    [row] = rows_with(rows, "ci-config-invalid")
                    self.assertTrue(row[2].startswith(f"ci.{key}: "))
                    self.assertEqual(rows_with(rows, "ci-gate-twice"), [])
        self.assertEqual(len(rows_with(findings(root, PROFILE), "ci-gate-twice")), 1)


class Providers(unittest.TestCase):
    def test_gitlab_only(self):
        rows = findings(repo({".gitlab-ci.yml": "stages: [test]\n"}), PROFILE)
        self.assertEqual(rows, [("info", "ci-not-checked", "CI provider not checked: .gitlab-ci.yml",
                                 "doctor reads GitHub Actions only; review this file by hand")])

    def test_invalid_workflow_rows_once(self):
        rows = findings(repo({".github/workflows/a.yml": "jobs: [unclosed\n"}), PROFILE)
        self.assertEqual([row[1] for row in rows], ["ci-workflow-invalid"])

    def test_empty_repo(self):
        self.assertEqual(findings(repo({}), PROFILE), [])


if __name__ == "__main__":
    unittest.main()
