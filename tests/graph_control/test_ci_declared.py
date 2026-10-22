import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.ci_declared import findings

EXPENSIVE = """on: push
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: E2E
        run: pnpm exec playwright test
"""

PROD_DATA = """on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - name: Backup
        run: bash scripts/db-backup.sh
"""

DEPLOY = """on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: make build
  deploy-dev:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - run: make deploy-dev
  smoke:
    needs: deploy-dev
    runs-on: ubuntu-latest
    steps:
      - run: make smoke
  deploy-prod:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - run: make deploy-prod
"""

GUESSES = """on: push
jobs:
  web:
    runs-on: ubuntu-latest
    steps:
      - name: E2E
        run: npx cypress run
  deploy-prod:
    runs-on: ubuntu-latest
    steps:
      - name: Migrate
        run: make db
"""

EXPENSIVE_ROW = {"run": "playwright test", "inputs": ["apps/web/**"]}
DEPLOY_KEY = {"dev": "deploy-dev", "smoke": "smoke", "prod": "deploy-prod"}
PROD_FIX = "if: steps.<id>.outputs.pending == 'true'"


def repo(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def run(text, ci):
    return findings(repo({".github/workflows/ci.yml": text}), {"ci": ci})


def rows_with(rows, id_):
    return [row for row in rows if row[1] == id_]


class ExpensiveUnscoped(unittest.TestCase):
    def test_unscoped_step_warns_at_its_line(self):
        [(level, _, message, fix)] = rows_with(run(EXPENSIVE, {"expensive": [EXPENSIVE_ROW]}),
                                               "ci-expensive-unscoped")
        self.assertEqual(level, "warn")
        self.assertIn(".github/workflows/ci.yml:7", message)
        self.assertIn("`e2e`", message)
        self.assertIn("apps/web/**", fix)
        self.assertIn("job-level `if:`", fix)
        self.assertIn("stays Pending", fix)

    def test_scoped_twins(self):
        twins = {
            "job if": EXPENSIVE.replace("  e2e:\n", "  e2e:\n    if: needs.changes.outputs.web == 'true'\n"),
            "step if": EXPENSIVE.replace("        run: pnpm", "        if: env.WEB == 'true'\n        run: pnpm"),
            "affected": EXPENSIVE.replace("      - name: E2E", "      - run: pnpm turbo query affected --exit-code\n"
                                          "      - name: E2E"),
            "pull_request paths": EXPENSIVE.replace("on: push", "on:\n  pull_request:\n    paths: ['apps/web/**']"),
            "push paths": EXPENSIVE.replace("on: push", "on:\n  push:\n    paths:\n      - apps/web/**"),
        }
        ci = {"expensive": [EXPENSIVE_ROW], "affected": {"web": "turbo query affected --exit-code"}}
        for label, text in twins.items():
            self.assertEqual(rows_with(run(text, ci), "ci-expensive-unscoped"), [], label)

    def test_affected_in_another_job_does_not_scope(self):
        text = EXPENSIVE + "  changes:\n    runs-on: ubuntu-latest\n    steps:\n" \
                           "      - run: turbo query affected --exit-code\n"
        ci = {"expensive": [EXPENSIVE_ROW], "affected": {"web": "turbo query affected --exit-code"}}
        self.assertEqual(len(rows_with(run(text, ci), "ci-expensive-unscoped")), 1)

    def test_empty_paths_and_branch_filter_do_not_scope(self):
        for trigger in ("on:\n  pull_request:\n    paths: []", "on:\n  push:\n    branches: [main]",
                        "on: [push, pull_request]"):
            rows = run(EXPENSIVE.replace("on: push", trigger), {"expensive": [EXPENSIVE_ROW]})
            self.assertEqual(len(rows_with(rows, "ci-expensive-unscoped")), 1, trigger)

    def test_declared_run_in_no_workflow(self):
        ci = {"expensive": [EXPENSIVE_ROW, {"run": "detox test", "inputs": ["apps/app/**"]}]}
        [row] = rows_with(run(EXPENSIVE, ci), "ci-declared-missing")
        self.assertEqual(row[0], "info")
        self.assertIn("detox test", row[2])
        self.assertIn("ci.expensive", row[2])


class ProdDataUnconditional(unittest.TestCase):
    def test_unconditional_step_warns(self):
        [(level, _, message, fix)] = rows_with(run(PROD_DATA, {"prod_data_steps": [{"run": "db-backup"}]}),
                                               "ci-prod-data-unconditional")
        self.assertEqual(level, "warn")
        self.assertIn(".github/workflows/ci.yml:6", message)
        self.assertIn(PROD_FIX, fix)

    def test_condition_without_outputs_still_warns(self):
        text = PROD_DATA.replace("        run:", "        if: github.ref == 'refs/heads/main'\n        run:")
        self.assertEqual(len(rows_with(run(text, {"prod_data_steps": [{"run": "db-backup"}]}),
                                       "ci-prod-data-unconditional")), 1)

    def test_outputs_twins(self):
        twins = (PROD_DATA.replace("        run:", "        if: steps.pending.outputs.pending == 'true'\n        run:"),
                 PROD_DATA.replace("  release:\n", "  release:\n    if: needs.plan.outputs.pending == 'true'\n"))
        for text in twins:
            self.assertEqual(rows_with(run(text, {"prod_data_steps": [{"run": "db-backup"}]}),
                                       "ci-prod-data-unconditional"), [])


class ProdNoPromote(unittest.TestCase):
    def test_prod_needs_only_build(self):
        [(level, _, message, fix)] = rows_with(run(DEPLOY, {"deploy": DEPLOY_KEY}), "ci-prod-no-promote")
        self.assertEqual(level, "warn")
        self.assertIn(".github/workflows/ci.yml:17", message)
        self.assertIn("`smoke`", message)
        self.assertIn("dev -> smoke -> prod", fix)
        self.assertIn("not build-once promotion", fix)

    def test_smoke_does_not_need_dev(self):
        text = DEPLOY.replace("    needs: deploy-dev\n", "    needs: build\n").replace(
            "  deploy-prod:\n    needs: build", "  deploy-prod:\n    needs: [smoke]")
        [row] = rows_with(run(text, {"deploy": DEPLOY_KEY}), "ci-prod-no-promote")
        self.assertIn(".github/workflows/ci.yml:17", row[2])
        self.assertIn("`deploy-dev`", row[2])

    def test_promote_twin(self):
        text = DEPLOY.replace("  deploy-prod:\n    needs: build", "  deploy-prod:\n    needs: [build, smoke]")
        self.assertEqual(rows_with(run(text, {"deploy": DEPLOY_KEY}), "ci-prod-no-promote"), [])

    def test_reusable_workflow_jobs_count_as_defined(self):
        text = DEPLOY.replace("  deploy-dev:\n    needs: build\n    runs-on: ubuntu-latest\n    steps:\n"
                              "      - run: make deploy-dev\n",
                              "  deploy-dev:\n    needs: build\n    uses: ./.github/workflows/_deploy.yml\n").replace(
            "  deploy-prod:\n    needs: build\n    runs-on: ubuntu-latest\n    steps:\n      - run: make deploy-prod\n",
            "  deploy-prod:\n    needs: smoke\n    uses: ./.github/workflows/_deploy.yml\n")
        self.assertEqual(run(text, {"deploy": DEPLOY_KEY}), [])
        [guess] = rows_with(run(text.replace("needs: smoke", "needs: build"), {}), "ci-prod-guess")
        self.assertIn("`deploy-prod`", guess[2])

    def test_declared_id_no_job_defines(self):
        [row] = rows_with(run(DEPLOY, {"deploy": {**DEPLOY_KEY, "dev": "deploy-staging"}}), "ci-prod-no-promote")
        self.assertEqual(row[0], "warn")
        self.assertIn("ci.deploy.dev", row[2])
        self.assertIn("`deploy-staging`", row[2])


class Heuristics(unittest.TestCase):
    def test_undeclared_guesses_are_info_only(self):
        for profile in ({}, {"ci": {"affected": {}, "expensive": [], "prod_data_steps": [], "deploy": {}}}):
            rows = findings(repo({".github/workflows/ci.yml": GUESSES}), profile)
            self.assertEqual({row[0] for row in rows}, {"info"})
            ids = {row[1]: row for row in rows}
            self.assertEqual(set(ids), {"ci-expensive-guess", "ci-prod-data-guess", "ci-prod-guess"})
            self.assertIn("ci.expensive", ids["ci-expensive-guess"][2])
            self.assertIn(".github/workflows/ci.yml:6", ids["ci-expensive-guess"][2])
            self.assertIn("ci.prod_data_steps", ids["ci-prod-data-guess"][2])
            self.assertIn(".github/workflows/ci.yml:11", ids["ci-prod-data-guess"][2])
            self.assertIn("ci.deploy", ids["ci-prod-guess"][2])
            self.assertIn(".github/workflows/ci.yml:8", ids["ci-prod-guess"][2])

    def test_guess_twins(self):
        text = GUESSES.replace("  web:\n", "  web:\n    if: needs.changes.outputs.web == 'true'\n").replace(
            "  deploy-prod:\n", "  smoke-test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make smoke\n"
                                "  deploy-prod:\n    needs: smoke-test\n").replace(
            "      - name: Migrate\n", "      - name: Migrate\n        if: steps.p.outputs.pending == 'true'\n")
        self.assertEqual(findings(repo({".github/workflows/ci.yml": text}), {}), [])

    def test_prod_data_guess_needs_prod_job(self):
        text = GUESSES.replace("deploy-prod", "deploy-dev")
        self.assertEqual(rows_with(findings(repo({".github/workflows/ci.yml": text}), {}), "ci-prod-data-guess"), [])

    def test_declared_keys_silence_guesses(self):
        ci = {"expensive": [{"run": "cypress run", "inputs": ["apps/web/**"]}], "prod_data_steps": [{"run": "make db"}],
              "deploy": {"dev": "web", "smoke": "web", "prod": "deploy-prod"}}
        ids = {row[1] for row in run(GUESSES, ci)}
        self.assertFalse(ids & {"ci-expensive-guess", "ci-prod-data-guess", "ci-prod-guess"})


class ConfigInvalid(unittest.TestCase):
    def test_malformed_keys_warn_once_and_skip(self):
        cases = {
            "affected": ["turbo"],
            "expensive": "playwright test",
            "prod_data_steps": [{"run": 3}],
            "deploy": {"dev": "deploy-dev"},
        }
        for key, value in cases.items():
            rows = run(GUESSES, {key: value})
            [row] = rows_with(rows, "ci-config-invalid")
            self.assertEqual(row[0], "warn")
            self.assertTrue(row[2].startswith(f"ci.{key}: "), row[2])
            self.assertEqual(row[3], "fix the profile's ci block")
        self.assertEqual(rows_with(run(EXPENSIVE, {"expensive": [{"inputs": ["a"]}]}), "ci-expensive-unscoped"), [])
        self.assertEqual(rows_with(run(EXPENSIVE, {"expensive": [{"run": "x", "inputs": "a"}]}),
                                   "ci-config-invalid")[0][2][:12], "ci.expensive")

    def test_non_mapping_ci_is_left_to_the_runtime_row(self):
        for ci in (True, ["x"], "on"):
            self.assertEqual(run(GUESSES, ci), [], ci)

    def test_skipped_check_emits_nothing_else(self):
        rows = run(GUESSES, {"deploy": "deploy-prod"})
        self.assertEqual(rows_with(rows, "ci-prod-guess") + rows_with(rows, "ci-prod-no-promote"), [])

    def test_invalid_workflow_rows_are_not_repeated(self):
        rows = findings(repo({".github/workflows/ci.yml": "on: [\n"}), {})
        self.assertEqual(rows, [])

    def test_no_workflows(self):
        self.assertEqual(findings(repo({}), {"ci": {"expensive": [], "deploy": {}}}), [])
