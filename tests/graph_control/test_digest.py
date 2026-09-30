"""graph-control digest over a SYNTHETIC git fixture repo: the stat by task when small, the sections when large.

Every case builds a throwaway repo, commits a base (plus dated history for churn), changes the
working tree and reads the markdown digest against that base.
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import helpers  # puts scripts/ on sys.path

if importlib.util.find_spec("wcmatch") is None:  # the PEP 723 pin; scripts/run-all-tests.sh installs it
    raise unittest.SkipTest("needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")

from graph_control import cli  # noqa: E402
from graph_control.commands import digest as digest_command  # noqa: E402
from graph_control.preflight import read_profile  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "graph-profile.yaml"
HEADER = "{files} files changed, +{added} -{deleted} (tracked changes; untracked files excluded)"


def git(repo, *args, days_ago=None):
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}}
    if days_ago is not None:
        stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                          check=True, capture_output=True, text=True, env=env).stdout.strip()


def lines(count, tag="x"):
    return "".join(f"{tag} {index}\n" for index in range(count))


def plan_file(path, tasks):
    """A valid plan.json with one case per task; `tasks` maps id -> (depends_on, writable_paths)."""
    data = helpers.plan_data()
    case, task = data["cases"][0], data["tasks"][0]
    data["cases"] = [dict(case, id=f"AC-{key}") for key in tasks]
    data["tasks"] = [dict(task, id=key, depends_on=deps, produces=[], writable_paths=globs, case_ids=[f"AC-{key}"])
                     for key, (deps, globs) in tasks.items()]
    return Path(helpers.dump(path, data))


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "test@example.invalid"],
                     ["config", "user.name", "Test"], ["config", "commit.gpgsign", "false"]):
            git(self.repo, *args)

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content)

    def commit(self, files, days_ago=None):
        for name, content in files.items():
            self.write(name, content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "history", days_ago=days_ago)
        return git(self.repo, "rev-parse", "HEAD")

    def profile(self, data):
        path = self.tmp / "profile.yaml"
        path.write_text(json.dumps(data))  # JSON is YAML
        return path

    def digest(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["digest", "--root", str(self.repo), f"--base={self.base}", *extra], modules=[digest_command])
        return code, out.getvalue()


class SmallDiff(Fixture):
    def setUp(self):
        super().setUp()
        self.base = self.commit({"app/stage/run.py": lines(4), "docs/guide.md": "# guide\n", "tools/x.sh": "echo\n"})
        self.write("app/stage/run.py", lines(3) + "changed\nadded\n")
        self.write("app/stage/new.py", lines(3))
        self.write("docs/guide.md", "# guide\nmore\n")
        self.write("tools/x.sh", "echo\nset -e\n")
        self.write("notes/untracked.txt", "never listed\n")
        git(self.repo, "add", "app/stage/new.py")

    def test_stat_is_grouped_by_task_with_unplanned_last(self):  # AC-W4-DG-01
        plan = plan_file(self.tmp / "plan.json", {"T1": ([], ["app/stage/**"]), "T2": (["T1"], ["docs/**"])})
        code, out = self.digest("--plan", str(plan))
        self.assertEqual(code, 0, out)
        self.assertEqual(out, "\n".join([
            f"## Change digest: {self.base[:8]}..working tree", HEADER.format(files=4, added=7, deleted=1), "",
            "### T1", "- `app/stage/new.py` +3 -0", "- `app/stage/run.py` +2 -1", "",
            "### T2", "- `docs/guide.md` +1 -0", "",
            "### unplanned", "- `tools/x.sh` +1 -0"]) + "\n")

    def test_without_a_plan_the_stat_is_one_list(self):
        code, out = self.digest()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[2:], ["", "- `app/stage/new.py` +3 -0", "- `app/stage/run.py` +2 -1",
                                                "- `docs/guide.md` +1 -0", "- `tools/x.sh` +1 -0"])

    def test_a_file_two_ordered_tasks_claim_names_both(self):
        plan = plan_file(self.tmp / "plan.json", {"T1": ([], ["app/**"]), "T2": (["T1"], ["app/stage/new.py"])})
        out = self.digest("--plan", str(plan))[1].splitlines()
        self.assertEqual(out[out.index("### T1, T2") + 1], "- `app/stage/new.py` +3 -0")
        self.assertEqual(out[out.index("### T1") + 1], "- `app/stage/run.py` +2 -1")

    def test_paths_are_code_spans_that_cannot_break_out(self):
        self.write("docs/a`b*c.md", "x\n")
        git(self.repo, "add", "docs/a`b*c.md")
        out = self.digest()[1]
        self.assertIn("- ``docs/a`b*c.md`` +1 -0\n", out)

    def test_base_that_is_an_option_is_blocked(self):
        self.base = "--output=/tmp/x"
        code, out = self.digest()
        self.assertEqual((code, json.loads(out)["status"]), (1, "BLOCKED"))


class LargeDiff(Fixture):
    def setUp(self):
        super().setUp()
        self.commit({"src/f0.py": lines(500), "api/routers/items.py": "items\n", "README.md": "r\n"}, days_ago=200)
        self.commit({**{f"src/f{i}.py": lines(70 - 10 * i) for i in range(1, 7)},
                     "tests/test_f.py": lines(1000)}, days_ago=10)
        self.base = self.commit({"src/f1.py": lines(60) + "tail\n"}, days_ago=5)  # f1 churn: 60 + 1
        for name in [f"src/f{i}.py" for i in range(7)] + ["tests/test_f.py", "api/routers/items.py"]:
            with (self.repo / name).open("a") as handle:
                handle.write(lines(10, "new"))
        self.write("api/routers/users.py", lines(40))
        self.write("svc/handlers/user.go", lines(5))
        self.write("src/brand_new.py", lines(8))
        self.write("tests/test_new.py", lines(200))
        self.write("docs/ux/changes/t1/before.png", b"\x89PNG\x00\x01")
        self.write("docs/ux/changes/t1/after.png", b"\x89PNG\x00\x02")
        git(self.repo, "add", "-A")
        api = [row for row in read_profile(TEMPLATE)["risk"] if row["id"] == "api-surface"]
        self.profile_path = self.profile({"risk": api, "digest": {"exclude": ["tests/**"]},
                                          "uxEvidence": {"path": "docs/ux/changes"}})

    def test_sections_loc_surfaces_hotspots_and_ux_evidence(self):  # AC-W4-DG-02
        code, out = self.digest("--profile", str(self.profile_path))
        self.assertEqual(code, 0, out)
        self.assertEqual(out, "\n".join([
            f"## Change digest: {self.base[:8]}..working tree", HEADER.format(files=15, added=343, deleted=0), "",
            "### Size", "- counted: 13 files, +133 -0", "- excluded by digest.exclude: 2 files, +210 -0", "",
            "### New public surfaces (2)", "- `api/routers/users.py`", "- `svc/handlers/user.go`", "",
            "### Hotspots: 90-day churn x changed lines",
            "- `src/f1.py` 61 x 10 = 610", "- `src/f2.py` 50 x 10 = 500", "- `src/f3.py` 40 x 10 = 400",
            "- `src/f4.py` 30 x 10 = 300", "- `src/f5.py` 20 x 10 = 200", "",
            "### UX evidence (2)", "- `docs/ux/changes/t1/after.png`", "- `docs/ux/changes/t1/before.png`"]) + "\n")

    def test_a_profile_without_the_keys_says_so(self):
        code, out = self.digest()
        self.assertEqual(code, 0, out)
        text = out.splitlines()
        self.assertIn("- excluded by digest.exclude: 0 files, +0 -0", text)
        self.assertIn("- no `api-surface` risk row in the profile", text)
        self.assertIn("- no uxEvidence.path in the profile", text)
        self.assertEqual(text[text.index("### Hotspots: 90-day churn x changed lines") + 1],
                         "- `tests/test_f.py` 1000 x 10 = 10000", "nothing is excluded without digest.exclude")

    def test_output_is_capped_at_60_lines(self):
        for index in range(80):
            self.write(f"api/routers/r{index:02d}.py", "r\n")
            self.write(f"docs/ux/changes/t2/shot{index:02d}.png", b"\x89PNG")
        git(self.repo, "add", "-A")
        out = self.digest("--profile", str(self.profile_path))[1].splitlines()
        self.assertLessEqual(len(out), 60)
        self.assertIn("### New public surfaces (82)", out)
        self.assertIn("- ... 67 more", out)
        self.assertIn("### UX evidence (82)", out)

    def test_read_only_nothing_in_the_repo_changes(self):  # AC-W4-DG-03
        def tree():
            return {str(path): (path.stat().st_size, path.stat().st_mtime_ns)
                    for path in sorted(self.repo.rglob("*")) if path.is_file()}

        status = git(self.repo, "status", "--porcelain=v1", "--untracked-files=all")  # refreshes the index
        # Stat-dirty after that: same content as the index, another mtime. A plain `git diff` rewrites .git/index.
        os.utime(self.repo / "README.md", (1_000_000_000, 1_000_000_000))
        before = tree()
        code, out = self.digest("--profile", str(self.profile_path))
        after = tree()
        self.assertEqual(code, 0, out)
        self.assertEqual(before, after, "digest wrote a file in the repo, .git included")
        self.assertEqual(git(self.repo, "status", "--porcelain=v1", "--untracked-files=all"), status)
        self.assertLessEqual(len(out.splitlines()), 60)


if __name__ == "__main__":
    unittest.main()
