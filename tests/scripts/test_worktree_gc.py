"""worktree-gc.sh: remove linked worktrees already merged and clean (AC-W3-GC-01).

Every case builds a SYNTHETIC throwaway repo whose main checkout is on `main`,
plus linked worktrees: merged-clean (its commit fast-forwarded into main),
merged-dirty (merged, then an edit left in the tree) and unmerged (a commit
main does not have). Git runs with GIT_DIR and friends scrubbed, as a hook
running these tests from a linked worktree would otherwise leak its own repo.

--apply is scoped to one run's branch prefix: unscoped, it would remove other
sessions' freshly cut worktrees (review finding, wave 3 fix round 1). The prefix
the engine prescribes must be unique per run: a UUIDv7's first 8 characters are
its timestamp head, shared by runs opened within ~65 s (fix round 2).
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GC = ROOT / "scripts" / "worktree-gc.sh"
ENGINE = ROOT / "commands" / "graph-ship.md"
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


def engine_key(pattern, run_id):
    """The engine's prescribed branch or gc key, from graph-ship.md, instantiated for one run id."""
    match = re.search(pattern, ENGINE.read_text())
    assert match, f"graph-ship.md no longer prescribes {pattern}"
    key = match.group(1).replace("<run-id>", run_id).replace("<run8>", run_id[:8])
    assert "<" not in key, f"unknown placeholder in the engine's key: {match.group(1)}"
    return key


# SYNTHETIC UUIDv7 run ids opened 30 s apart: the first 8 hex digits are the top 32 bits of
# the millisecond timestamp (RFC 9562, 5.7), so both read 01a0f459; the random tails differ.
RUN_A, RUN_C = "01a0f459-1c2d-7a3b-8c4d-5e6f7a8b9c0d", "01a0f459-8d4e-7f10-9a21-b3c4d5e6f708"


def task_branch(run_id, task):
    return engine_key(r"git worktree add -b (<[^>]+>-)<task>", run_id) + task


def gc_prefix(run_id):
    return engine_key(r"worktree-gc\.sh --apply --base <run branch> --prefix (\S+?)`", run_id)


class DryRunAndApply(Fixture):
    def test_dry_run_lists_only_merged_clean_ac_w3_gc_01(self):
        code, out, _ = self.gc()
        self.assertEqual((code, out), (0, [f"would remove {self.clean} (merged-clean)"]))
        self.assertTrue(self.clean.is_dir())
        self.assertTrue(self.branch_exists("merged-clean"))

    def test_apply_removes_it_and_deletes_its_branch_ac_w3_gc_01(self):
        code, out, err = self.gc("--apply", "--prefix", "merged-")
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

    def test_apply_without_prefix_exits_2_and_removes_nothing(self):
        code, out, err = self.gc("--apply")
        self.assertEqual((code, out), (2, []))
        self.assertIn("--prefix", err)
        self.assertTrue(self.clean.is_dir())
        self.assertTrue(self.branch_exists("merged-clean"))

    def test_branch_d_refusal_keeps_the_branch_and_exits_1(self):
        # Merged into --base but not into the current HEAD: `git branch -d` refuses and -D is never used.
        side = self.add("side")
        self.commit(side, "side.txt")
        tree = git(self.repo, "rev-parse", "side^{tree}").stdout.strip()
        ahead = git(self.repo, "commit-tree", tree, "-p", "side", "-m", "integration").stdout.strip()
        git(self.repo, "branch", "integration", ahead)
        code, out, err = self.gc("--apply", "--base", "integration", "--prefix", "side")
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
        self.assertEqual(self.gc("--apply", "--prefix", "merged-")[:2], (0, []),
                         "nor attempted, so apply reports no refusal")
        self.assertTrue(self.clean.is_dir())

    def test_default_branch_worktree_is_kept(self):
        git(self.repo, "switch", "-q", "-c", "dev")
        default = self.add("main", options=[], commit="main")
        code, out, _ = self.gc("--base", "main")
        self.assertEqual((code, out), (0, [f"would remove {self.clean} (merged-clean)"]))
        self.assertTrue(default.is_dir())

    def test_detached_worktree_is_listed_as_detached(self):
        detached = self.add("detached", options=["--detach"], commit="merged-clean")
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
        self.assertEqual(self.gc("--prefix")[0], 2)
        self.assertEqual(self.gc("--apply", "--prefix", "")[0], 2)

    def test_outside_a_repository_exits_2(self):
        outside = self.tmp / "plain"
        outside.mkdir()
        env = dict(ENV, GIT_CEILING_DIRECTORIES=str(self.tmp))
        self.assertEqual(self.gc(cwd=outside, env=env)[0], 2)


class Scope(Fixture):
    """A run's own task worktrees go; other sessions' worktrees never do."""

    def test_worktree_at_the_base_tip_is_kept(self):
        # Another session just cut and bootstrapped it: no commits of its own, so nothing is merged.
        fresh = self.add("runB")
        (fresh / "node_modules").mkdir()
        self.assertEqual(self.gc()[1], [f"would remove {self.clean} (merged-clean)"])
        self.assertEqual(self.gc("--apply", "--prefix", "runB")[:2], (0, []))
        self.assertTrue(fresh.is_dir())
        self.assertTrue(self.branch_exists("runB"))

    def test_prefix_keeps_other_runs_merged_worktrees(self):
        ours, theirs = self.add("aaaa1111-t1"), self.add("bbbb2222-t1")
        self.commit(ours, "ours.txt")
        self.commit(theirs, "theirs.txt")
        git(self.repo, "merge", "-q", "--no-ff", "--no-edit", "aaaa1111-t1", "bbbb2222-t1")
        code, out, err = self.gc("--apply", "--prefix", "aaaa1111-")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, [f"removed {ours} (aaaa1111-t1)", "deleted branch aaaa1111-t1"])
        self.assertTrue(theirs.is_dir())
        self.assertTrue(self.clean.is_dir(), "a merged worktree outside the prefix stays")

    def test_prefix_never_matches_a_detached_worktree(self):
        detached = self.add("detached", options=["--detach"], commit="merged-clean")
        self.assertIn(f"would remove {detached} (detached)", self.gc()[1])
        self.assertEqual(self.gc("--prefix", "d")[:2], (0, []))

    def cut_task(self, run_id, task, commit):
        """`git worktree add -b <engine branch key><task>` at an explicit base, as the engine does."""
        return self.add(f"{run_id[-4:]}-{task}", options=["-b", task_branch(run_id, task)], commit=commit)

    def test_runs_sharing_their_first_8_characters_cut_the_same_task_name(self):
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.cut_task(RUN_C, "t1", head)
        ours = self.cut_task(RUN_A, "t1", head)  # a shared key makes git refuse: the task is BLOCKED
        self.assertTrue(ours.is_dir())
        self.assertNotEqual(task_branch(RUN_A, "t1"), task_branch(RUN_C, "t1"))

    def test_scoped_gc_keeps_a_run_sharing_its_first_8_characters(self):
        # Run C just cut its wave-1 task from its run branch head (still main's tip) and bootstrapped
        # it; run A, from its run worktree, merged its own task back and runs the prescribed gc.
        (self.repo / ".git" / "info" / "exclude").write_text("node_modules/\n")
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        theirs = self.cut_task(RUN_C, "t9", head)
        (theirs / "node_modules").mkdir()
        (theirs / "node_modules" / "dep.js").write_text("installed\n")
        run = self.add("runA")
        ours = self.cut_task(RUN_A, "t1", head)
        self.commit(ours, "t1.txt")
        git(run, "merge", "-q", "--no-ff", "--no-edit", task_branch(RUN_A, "t1"))
        code, out, err = self.gc("--apply", "--base", "runA", "--prefix", gc_prefix(RUN_A), cwd=run)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, [f"removed {ours} ({task_branch(RUN_A, 't1')})",
                               f"deleted branch {task_branch(RUN_A, 't1')}"])
        self.assertTrue((theirs / "node_modules" / "dep.js").is_file(), "run C's tree and its ignored files stay")
        self.assertTrue(self.branch_exists(task_branch(RUN_C, "t9")))

    def test_task_branches_merged_into_a_run_branch(self):
        # The engine's shape: task worktrees cut from the run branch head, merged back
        # into the run branch (not main) with --no-ff, the gc run from the run worktree.
        run = self.add("run1")
        head = git(run, "rev-parse", "HEAD").stdout.strip()
        tasks = [self.add(f"run1-t{n}", options=["-b", f"run1-t{n}"], commit=head) for n in (1, 2)]
        for n, tree in enumerate(tasks, 1):
            self.commit(tree, f"t{n}.txt")
            git(run, "merge", "-q", "--no-ff", "--no-edit", f"run1-t{n}")
        other = self.add("runB")  # a concurrent session's fresh worktree
        self.assertEqual(self.gc(cwd=run)[1], [f"would remove {self.clean} (merged-clean)"],
                         "against main, the run's task worktrees are not merged yet")
        code, out, err = self.gc("--apply", "--base", "run1", "--prefix", "run1-", cwd=run)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, [f"removed {tasks[0]} (run1-t1)", "deleted branch run1-t1",
                               f"removed {tasks[1]} (run1-t2)", "deleted branch run1-t2"])
        for tree in tasks:
            self.assertFalse(tree.exists())
        for kept in (run, other, self.clean, self.repo):
            self.assertTrue(kept.is_dir(), kept)
        self.assertTrue(self.branch_exists("run1"))


if __name__ == "__main__":
    unittest.main()
