"""worktree-gc.sh: remove linked worktrees already merged and clean (AC-W3-GC-01).

Every case builds a SYNTHETIC throwaway repo whose main checkout is on `main`,
plus linked worktrees: merged-clean (its commit fast-forwarded into main),
merged-dirty (merged, then an edit left in the tree) and unmerged (a commit
main does not have). Git runs with GIT_DIR and friends scrubbed, as a hook
running these tests from a linked worktree would otherwise leak its own repo.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GC = Path(__file__).resolve().parents[2] / "scripts" / "worktree-gc.sh"
GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
ENV = {key: value for key, value in os.environ.items() if key not in GIT_VARS}


def git(cwd, *args, check=True):
    result = subprocess.run(["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null", *args],
                            capture_output=True, text=True, env=ENV, check=False)
    if check and result.returncode:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.repo = self.tmp / "repo"
        git(self.tmp, "init", "-q", "-b", "main", str(self.repo))
        for key, value in (("user.email", "test@example.invalid"), ("user.name", "Test"), ("commit.gpgsign", "false")):
            git(self.repo, "config", key, value)
        self.commit(self.repo, "base.txt")
        self.clean = self.add("merged-clean")
        self.commit(self.clean, "clean.txt")
        self.dirty = self.add("merged-dirty")
        self.commit(self.dirty, "dirty.txt")
        git(self.repo, "merge", "-q", "--ff-only", "merged-clean")
        git(self.repo, "merge", "-q", "--no-edit", "merged-dirty")
        (self.dirty / "dirty.txt").write_text("edited, not committed\n")
        self.unmerged = self.add("unmerged")
        self.commit(self.unmerged, "unmerged.txt")

    def commit(self, tree, name):
        (tree / name).write_text(f"{name}\n")
        git(tree, "add", name)
        git(tree, "commit", "-qm", name)

    def add(self, name, options=None, commit=None):
        path = self.tmp / f"wt-{name}"
        options = ["-b", name] if options is None else options
        git(self.repo, "worktree", "add", "-q", *options, str(path), *([commit] if commit else []))
        return path

    def gc(self, *args, cwd=None, env=None):
        result = subprocess.run(["bash", str(GC), *args], cwd=cwd or self.repo, env=env or ENV,
                                capture_output=True, text=True, check=False)
        return result.returncode, result.stdout.splitlines(), result.stderr

    def branch_exists(self, name):
        return git(self.repo, "show-ref", "--verify", "-q", f"refs/heads/{name}", check=False).returncode == 0


class DryRunAndApply(Fixture):
    def test_dry_run_lists_only_merged_clean_ac_w3_gc_01(self):
        code, out, _ = self.gc()
        self.assertEqual((code, out), (0, [f"would remove {self.clean} (merged-clean)"]))
        self.assertTrue(self.clean.is_dir())
        self.assertTrue(self.branch_exists("merged-clean"))

    def test_apply_removes_it_and_deletes_its_branch_ac_w3_gc_01(self):
        code, out, err = self.gc("--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, [f"removed {self.clean} (merged-clean)", "deleted branch merged-clean"])
        self.assertFalse(self.clean.exists())
        self.assertFalse(self.branch_exists("merged-clean"))
        for path, branch in ((self.dirty, "merged-dirty"), (self.unmerged, "unmerged")):
            self.assertTrue(path.is_dir())
            self.assertTrue(self.branch_exists(branch))
        self.assertEqual((self.dirty / "dirty.txt").read_text(), "edited, not committed\n")
        listed = git(self.repo, "worktree", "list", "--porcelain").stdout
        self.assertNotIn(str(self.clean), listed)
        self.assertIn(f"worktree {self.repo}\n", listed)
        self.assertEqual(self.gc()[1], [], "a second run finds nothing")

    def test_branch_d_refusal_keeps_the_branch_and_exits_1(self):
        # Merged into --base but not into the current HEAD: `git branch -d` refuses and -D is never used.
        side = self.add("side")
        self.commit(side, "side.txt")
        git(self.repo, "branch", "integration", "side")
        code, out, err = self.gc("--apply", "--base", "integration")
        self.assertEqual(code, 1)
        self.assertIn(f"removed {side} (side)", out)
        self.assertNotIn("deleted branch side", out)
        self.assertTrue(self.branch_exists("side"))
        self.assertIn("not fully merged", err)

    def test_untracked_file_counts_as_dirty(self):
        (self.clean / "notes.txt").write_text("untracked\n")
        self.assertEqual(self.gc()[1], [])


class Exclusions(Fixture):
    def test_worktree_holding_the_current_directory_is_kept(self):
        (self.clean / "sub").mkdir()
        self.assertEqual(self.gc(cwd=self.clean / "sub")[1], [])

    def test_locked_worktree_is_kept(self):
        git(self.repo, "worktree", "lock", str(self.clean))
        self.assertEqual(self.gc()[:2], (0, []), "a locked tree is never proposed")
        self.assertEqual(self.gc("--apply")[:2], (0, []), "nor attempted, so apply reports no refusal")
        self.assertTrue(self.clean.is_dir())

    def test_default_branch_worktree_is_kept(self):
        git(self.repo, "switch", "-q", "-c", "dev")
        default = self.add("main", options=[], commit="main")
        code, out, _ = self.gc("--base", "main")
        self.assertEqual((code, out), (0, [f"would remove {self.clean} (merged-clean)"]))
        self.assertTrue(default.is_dir())

    def test_detached_worktree_is_listed_as_detached(self):
        detached = self.add("detached", options=["--detach"])
        self.assertIn(f"would remove {detached} (detached)", self.gc()[1])

    def test_inherited_git_dir_is_ignored(self):
        other = self.tmp / "other"
        git(self.tmp, "init", "-q", str(other))
        env = dict(ENV, GIT_DIR=str(other / ".git"), GIT_WORK_TREE=str(other))
        self.assertEqual(self.gc(env=env)[1], [f"would remove {self.clean} (merged-clean)"])


class Base(Fixture):
    def test_base_defaults_to_origin_head(self):
        origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", str(origin))
        git(self.repo, "remote", "add", "origin", str(origin))
        git(self.repo, "push", "-q", "origin", "main~2:refs/heads/main")  # before either merge
        git(self.repo, "remote", "set-head", "origin", "main")
        self.assertEqual(self.gc()[1], [], "merged-clean is not in origin/main yet")
        self.assertEqual(self.gc("--base", "main")[1], [f"would remove {self.clean} (merged-clean)"])

    def test_unknown_base_exits_2(self):
        code, out, err = self.gc("--base", "no-such-ref")
        self.assertEqual((code, out), (2, []))
        self.assertIn("no-such-ref", err)

    def test_usage_error_exits_2(self):
        self.assertEqual(self.gc("--force")[0], 2)
        self.assertEqual(self.gc("--base")[0], 2)

    def test_outside_a_repository_exits_2(self):
        outside = self.tmp / "plain"
        outside.mkdir()
        env = dict(ENV, GIT_CEILING_DIRECTORIES=str(self.tmp))
        self.assertEqual(self.gc(cwd=outside, env=env)[0], 2)


if __name__ == "__main__":
    unittest.main()
