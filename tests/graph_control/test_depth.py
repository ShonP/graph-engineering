"""Review depth from a diff: lint, single or panel, against a SYNTHETIC git fixture repo.

Every case builds a throwaway repo, commits a base, changes the working tree and
asks depth.decide (or the public CLI) for the verdict against that base.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401 - puts scripts/ on sys.path

if importlib.util.find_spec("wcmatch") is None:  # the PEP 723 pin; scripts/run-all-tests.sh installs it
    raise unittest.SkipTest("needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

from graph_control.common import Invalid  # noqa: E402
from graph_control.depth import decide  # noqa: E402

CLI = Path(__file__).resolve().parents[2] / "scripts" / "graph-control.py"
KEYS = {"depth", "changed_lines", "files", "risk_rows", "reasons", "untracked_excluded"}
LINT = "prose only: every changed file matches *.md, *.txt or docs/** and none matches instructionPaths"
RISK = {"risk": [{"id": "db-schema", "paths": ["**/{migrations,schemas}/**"]},
                 {"id": "credentials-and-access", "keywords": ["API_KEY"]}]}
SEAMS = {"stacks": {"web": {"paths": ["web/**"]}, "api": {"paths": ["api/**"]}}, "review": {"seams": [["web", "api"]]}}
BASE_FILES = {"README.md": "# fixture\n", "CLAUDE.md": "rules\n", "src/app.py": "API_KEY = read()\nprint('ok')\n",
              "web/page.ts": "export {}\n", "api/main.py": "pass\n", "docs/guide.rst": "guide\n",
              "db/migrations/0000.sql": "create table t (id int);\n", "logo.bin": b"\x00\x01\x02"}


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}}
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                          check=True, capture_output=True, text=True, env=env).stdout.strip()


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve() / "repo"
        self.repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "test@example.invalid"],
                     ["config", "user.name", "Test"], ["config", "commit.gpgsign", "false"]):
            git(self.repo, *args)
        for name, content in BASE_FILES.items():
            self.write(name, content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def write(self, name, content, track=False):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content)
        if track:
            git(self.repo, "add", name)

    def append(self, name, text):
        with (self.repo / name).open("a") as handle:
            handle.write(text)

    def decide(self, profile=None):
        result = decide(self.repo, self.base, profile or {})
        self.assertEqual(set(result), KEYS)
        self.assertIs(result["untracked_excluded"], True)
        return result


class Lint(Fixture):
    """AC-W2-DP-01."""

    def test_readme_only_change_is_lint(self):
        self.append("README.md", "more prose\n")
        result = self.decide()
        self.assertEqual(result, {"depth": "lint", "changed_lines": 1, "files": 1, "risk_rows": [],
                                  "reasons": [LINT], "untracked_excluded": True})

    def test_claude_md_in_instruction_paths_is_single(self):
        self.append("CLAUDE.md", "a new rule\n")
        self.assertEqual(self.decide()["depth"], "lint")
        self.assertEqual(self.decide({"instructionPaths": ["CLAUDE.md"]})["depth"], "single")

    def test_docs_tree_counts_as_prose_but_code_does_not(self):
        self.append("docs/guide.rst", "more\n")
        self.assertEqual(self.decide()["depth"], "lint")
        self.append("src/app.py", "print('more')\n")
        self.assertEqual(self.decide()["depth"], "single")

    def test_no_tracked_change_is_lint_and_says_untracked_is_excluded(self):
        self.write("src/new.py", "print('untracked')\n")
        result = self.decide()
        self.assertEqual((result["depth"], result["files"], result["changed_lines"]), ("lint", 0, 0))
        self.assertEqual(result["reasons"], ["no tracked change against base; untracked files are excluded"])

    def test_prose_over_the_line_budget_or_across_a_seam_stays_lint(self):
        self.write("web/README.md", "line\n" * 2001, track=True)
        self.write("api/README.md", "line\n", track=True)
        self.assertEqual(self.decide(SEAMS)["depth"], "lint")


class Risk(Fixture):
    """AC-W2-DP-02."""

    def test_change_under_a_risk_glob_is_panel(self):
        self.write("db/migrations/0001_init.sql", "create table t (id int);\n", track=True)
        result = self.decide(RISK)
        self.assertEqual((result["depth"], result["risk_rows"]), ("panel", ["db-schema"]))
        self.assertEqual(result["reasons"], ["risk rows: db-schema"])

    def test_added_line_with_a_keyword_matches(self):
        self.append("src/app.py", "client = connect(api_key)\n")
        self.assertEqual(self.decide(RISK)["risk_rows"], ["credentials-and-access"])

    def test_removed_line_with_a_keyword_does_not_match(self):
        self.write("src/app.py", "print('ok')\n")
        result = self.decide(RISK)
        self.assertEqual((result["depth"], result["risk_rows"]), ("single", []))

    def test_added_line_that_itself_starts_with_plus_plus_is_read(self):
        self.append("src/app.py", "++API_KEY_uses\n")
        self.assertEqual(self.decide(RISK)["risk_rows"], ["credentials-and-access"])

    def test_risk_row_beats_prose(self):
        self.write("docs/schemas/user.md", "a schema note\n", track=True)
        self.assertEqual(self.decide(RISK)["depth"], "panel")

    def test_untracked_file_under_a_risk_glob_is_excluded(self):
        self.write("db/migrations/0002.sql", "drop table t;\n")
        self.append("src/app.py", "print('more')\n")
        self.assertEqual(self.decide(RISK)["risk_rows"], [])

    def test_rename_out_of_a_risk_glob_matches_the_old_path_and_counts_one_file(self):
        (self.repo / "archive").mkdir()
        git(self.repo, "mv", "db/migrations/0000.sql", "archive/0000.sql")
        result = self.decide(RISK)
        self.assertEqual((result["depth"], result["files"], result["changed_lines"]), ("panel", 1, 0))


class SizeAndSeams(Fixture):
    """AC-W2-DP-03."""

    def test_2001_changed_lines_is_panel_and_2000_is_single(self):
        self.write("src/big.py", "x = 1\n" * 2000, track=True)
        self.assertEqual(self.decide()["depth"], "single")
        self.append("src/big.py", "x = 2\n")
        result = self.decide()
        self.assertEqual((result["depth"], result["changed_lines"]), ("panel", 2001))
        self.assertEqual(result["reasons"], ["2001 changed lines > review.panel_lines 2000"])

    def test_panel_lines_comes_from_the_profile(self):
        self.append("src/app.py", "a = 1\nb = 2\n")
        self.assertEqual(self.decide({"review": {"panel_lines": 1}})["depth"], "panel")

    def test_binary_change_counts_zero_lines(self):
        self.write("logo.bin", b"\x00\x09\x08\x07")
        result = self.decide()
        self.assertEqual((result["depth"], result["files"], result["changed_lines"]), ("single", 1, 0))

    def test_touching_every_stack_of_a_seam_is_panel(self):
        self.append("web/page.ts", "export const a = 1\n")
        self.append("api/main.py", "a = 1\n")
        result = self.decide(SEAMS)
        self.assertEqual((result["depth"], result["reasons"]), ("panel", ["seam web+api: every stack touched"]))

    def test_touching_one_stack_of_a_seam_is_single(self):
        self.append("web/page.ts", "export const a = 1\n")
        result = self.decide(SEAMS)
        self.assertEqual(result["depth"], "single")
        self.assertEqual(result["reasons"], ["default: no risk row or seam, 1 changed lines <= review.panel_lines 2000"])


class Validation(Fixture):
    def test_bad_input_is_invalid(self):
        self.append("src/app.py", "a = 1\n")
        bad = {
            "unknown base": ("no-such-branch", {}),
            "option as base": ("--output=/tmp/x", {}),
            "seam names an unknown stack": (self.base, {**SEAMS, "review": {"seams": [["web", "ios"]]}}),
            "seam of one stack": (self.base, {**SEAMS, "review": {"seams": [["web"]]}}),
            "panel_lines not an integer": (self.base, {"review": {"panel_lines": "2000"}}),
            "instructionPaths not a list": (self.base, {"instructionPaths": "CLAUDE.md"}),
            "bad risk row": (self.base, {"risk": [{"id": "x"}]}),
        }
        for name, (base, profile) in bad.items():
            with self.subTest(name), self.assertRaises(Invalid):
                decide(self.repo, base, profile)


class Cli(Fixture):
    def run_cli(self, base, profile_text):
        profile = self.repo.parent / "profile.yaml"
        profile.write_text(profile_text)
        return subprocess.run([sys.executable, str(CLI), "depth", "--root", str(self.repo), "--base", base,
                               "--profile", str(profile)], capture_output=True, text=True, timeout=60)

    def test_cli_prints_the_decision(self):
        self.write("db/migrations/0001.sql", "create table t (id int);\n", track=True)
        result = self.run_cli(self.base, "risk:\n  - id: db-schema\n    paths: ['**/migrations/**']\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "status": "PASS", "depth": "panel", "changed_lines": 1, "files": 1, "risk_rows": ["db-schema"],
            "reasons": ["risk rows: db-schema"], "untracked_excluded": True})

    def test_cli_blocks_on_an_unknown_base(self):
        result = self.run_cli("no-such-branch", "stacks: {}\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
