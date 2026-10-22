"""The CI workflow loader over SYNTHETIC repos built in temp dirs from inline YAML.

Line numbers in WORKFLOW are hand-counted; the spike in the run's prior-art note
is the real witness that compose marks match file lines.
"""

import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.ci_workflows import load_workflows, location, other_providers

WORKFLOW = """name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  build:
    name: Build
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          persist-credentials: false
          fetch-depth: 0
      - name: Test
        run: make test
  deploy:
    needs: [build]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - run: make deploy
        if: success()
"""


def repo(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


class Lines(unittest.TestCase):
    def check(self, text):
        workflows, rows = load_workflows(repo({".github/workflows/ci.yml": text}))
        self.assertEqual(rows, [])
        [wf] = workflows
        self.assertEqual(wf.path, ".github/workflows/ci.yml")
        self.assertEqual(wf.on, {"push": {"branches": ["main"]}, "pull_request": ""})
        build, deploy = wf.jobs
        self.assertEqual((build.id, build.name, build.needs, build.line), ("build", "Build", (), 7))
        self.assertEqual((deploy.id, deploy.needs, deploy.if_, deploy.line),
                         ("deploy", ("build",), "github.ref == 'refs/heads/main'", 18))
        checkout, test = build.steps
        self.assertEqual((checkout.job, checkout.index, checkout.name, checkout.uses, checkout.line),
                         ("build", 0, "Checkout", "actions/checkout@v4", 11))
        self.assertEqual(checkout.lines, {"name": 11, "uses": 12, "with": 13,
                                          "with.persist-credentials": 14, "with.fetch-depth": 15})
        self.assertEqual(checkout.with_, {"persist-credentials": "false", "fetch-depth": "0"})
        self.assertEqual((test.index, test.run, test.line, test.lines), (1, "make test", 16, {"name": 16, "run": 17}))
        [step] = deploy.steps
        self.assertEqual((step.job, step.run, step.if_, step.line, step.lines),
                         ("deploy", "make deploy", "success()", 23, {"run": 23, "if": 24}))
        self.assertEqual(location(wf, 14), ".github/workflows/ci.yml:14")

    def test_plain_false(self):
        self.check(WORKFLOW)

    def test_quoted_false(self):
        self.check(WORKFLOW.replace("persist-credentials: false", 'persist-credentials: "false"'))


class Edge(unittest.TestCase):
    def test_no_workflow_dir(self):
        self.assertEqual(load_workflows(repo({"README.md": "x\n"})), ([], []))

    def test_malformed_beside_good(self):
        root = repo({".github/workflows/a.yml": "jobs: [unclosed\n",
                     ".github/workflows/b.yaml": WORKFLOW,
                     ".github/workflows/c.yml": "- just\n- a list\n",
                     ".github/workflows/notes.txt": "x: 1\n"})
        workflows, rows = load_workflows(root)
        self.assertEqual([wf.path for wf in workflows], [".github/workflows/b.yaml"])
        self.assertEqual([(r[0], r[1], r[3]) for r in rows],
                         [("warn", "ci-workflow-invalid", "fix the YAML; doctor skipped this file")] * 2)
        self.assertTrue(rows[0][2].startswith(".github/workflows/a.yml: "))
        self.assertNotIn("\n", rows[0][2])
        self.assertTrue(rows[1][2].startswith(".github/workflows/c.yml: "))

    def test_skipped_shapes_and_string_needs(self):
        text = """on: push
jobs:
  lint:
    - not a mapping
  build:
    steps: not-a-list
  test:
    needs: build
    steps:
      - run: make test
"""
        [wf], rows = load_workflows(repo({".github/workflows/ci.yml": text}))
        self.assertEqual(rows, [])
        self.assertEqual(wf.on, "push")
        self.assertEqual([job.id for job in wf.jobs], ["test"])
        self.assertEqual(wf.jobs[0].needs, ("build",))

    def test_reusable_workflow_job_is_kept_with_its_needs(self):
        text = """on: push
jobs:
  deploy-prod:
    needs: [smoke]
    uses: ./.github/workflows/_deploy.yml
  broken:
    uses: [x]
"""
        [wf], _ = load_workflows(repo({".github/workflows/ci.yml": text}))
        [job] = wf.jobs
        self.assertEqual((job.id, job.needs, job.steps, job.line), ("deploy-prod", ("smoke",), (), 3))

    def test_other_providers(self):
        root = repo({".gitlab-ci.yml": "stages: [test]\n", ".circleci/config.yml": "version: 2.1\n"})
        self.assertEqual(other_providers(root), [".gitlab-ci.yml", ".circleci/config.yml"])
        self.assertEqual(other_providers(repo({})), [])


if __name__ == "__main__":
    unittest.main()
