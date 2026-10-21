"""hygiene run-end: main checkout clean, run worktrees gone, run branch merged, no stray files."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from hygiene_fixture import git, make_repo, stage
from graph_control import cli

RUN = "01a15ebd-acme"
BRANCH = f"graph/{RUN}"


class RunEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = make_repo(self.tmp, origin=True)
        self.profile = self.tmp / "profile.yaml"
        self.profile.write_text("{}\n", encoding="utf-8")
        stage(self.root, "acme-widget.txt", "widget\n")
        stage(self.root, ".graph/ledger.md", "ledger\n")
        git(self.root, "commit", "-q", "-m", "base")
        git(self.root, "branch", BRANCH)
        self.advance(BRANCH)
        git(self.root, "merge", "-q", "--ff-only", BRANCH)
        git(self.root, "push", "-q", "origin", "main")
        git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    def advance(self, branch):
        sha = git(self.root, "commit-tree", f"{branch}^{{tree}}", "-p", branch, "-m", "run work")
        git(self.root, "update-ref", f"refs/heads/{branch}", sha)

    def snapshot(self):
        return git(self.root, "status", "--porcelain"), git(self.root, "worktree", "list", "--porcelain")

    def invoke(self, *argv, integration="pr", branch=BRANCH):
        before = self.snapshot()
        out = io.StringIO()
        extra = ["--branch", branch] if branch else []
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["hygiene", "--root", str(self.root), "--profile", str(self.profile),
                             "--run-end", RUN, *extra, "--integration", integration, "--only", "run-end", *argv])
        self.assertEqual(self.snapshot(), before)
        result = json.loads(out.getvalue())
        self.assertEqual(code, 1 if result["status"] == "FAIL" else 0)
        return result

    def ids(self, result, level=None):
        return sorted(f["id"] for f in result["findings"] if level in (None, f["level"]))

    def worktree(self, name, branch=None):
        path = self.tmp / "wt" / name
        git(self.root, "worktree", "add", "-q", *(["-b", branch] if branch else ["--detach"]), str(path), "main")
        return path

    def dirty(self):
        (self.root / "acme-widget.txt").write_text("changed\n", encoding="utf-8")
        self.worktree(f"{RUN}-T1", f"{RUN}-T1")
        (self.root / "notes.txt").write_text("stray\n", encoding="utf-8")
        self.advance(BRANCH)

    def test_clean_run_passes(self):
        result = self.invoke()
        self.assertEqual((result["status"], result["run_end"], result["findings"]), ("PASS", "CLEAN", []))
        self.assertEqual(self.invoke(branch=None)["run_end"], "CLEAN")

    def test_modified_tracked_file_is_main_dirty(self):
        (self.root / "acme-widget.txt").write_text("changed\n", encoding="utf-8")
        result = self.invoke()
        self.assertEqual(result["run_end"], "DIRTY (1)")
        [finding] = result["findings"]
        self.assertEqual((finding["level"], finding["id"], finding["path"]), ("error", "main-dirty", "acme-widget.txt"))

    def test_staged_rename_names_the_new_path(self):
        git(self.root, "mv", "acme-widget.txt", "acme-gadget.txt")
        self.assertEqual([f["path"] for f in self.invoke()["findings"]], ["acme-gadget.txt"])

    def test_graph_changes_are_ignored(self):
        (self.root / ".graph" / "ledger.md").write_text("more\n", encoding="utf-8")
        (self.root / ".graph" / "run.json").write_text("{}\n", encoding="utf-8")
        self.assertEqual(self.invoke()["run_end"], "CLEAN")

    def test_run_worktree_is_left(self):
        path = self.worktree("acme-task", f"{RUN}-T1")
        [finding] = self.invoke()["findings"]
        self.assertEqual((finding["level"], finding["id"], finding["path"]), ("error", "worktree-left", str(path)))
        self.assertIn(f"--prefix {RUN}-", finding["fix"])

    def test_integration_worktree_is_a_warning_until_landing(self):
        path = self.tmp / "wt" / RUN
        git(self.root, "worktree", "add", "-q", str(path), BRANCH)
        result = self.invoke()
        [finding] = result["findings"]
        self.assertEqual((result["run_end"], finding["level"], finding["id"], finding["path"]),
                         ("CLEAN", "warn", "worktree-left", str(path)))
        self.assertIn(f"git worktree remove {path}", finding["fix"])
        git(self.root, "worktree", "remove", str(path))
        detached = self.tmp / "wt2" / RUN
        git(self.root, "worktree", "add", "-q", "--detach", str(detached), "main")
        self.assertEqual([(f["level"], f["id"]) for f in self.invoke()["findings"]], [("warn", "worktree-left")])

    def test_run_worktree_matched_by_directory_name(self):
        self.worktree(f"{RUN}-T2")
        self.assertEqual(self.ids(self.invoke()), ["worktree-left"])

    def test_other_session_worktree_is_never_reported(self):
        self.worktree("other-T1", "other-T1")
        self.worktree("acme-widget", f"other-{RUN}-T1")
        self.assertEqual(self.invoke()["run_end"], "CLEAN")

    def test_removed_but_unpruned_worktree_needs_prune(self):
        shutil.rmtree(self.worktree(f"{RUN}-T3", f"{RUN}-T3"))
        [finding] = self.invoke()["findings"]
        self.assertEqual((finding["id"], finding["fix"]), ("worktree-left", "git worktree prune"))

    def test_untracked_file_is_stray(self):
        (self.root / "notes.txt").write_text("stray\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("build/\n", encoding="utf-8")
        (self.root / "build").mkdir()
        (self.root / "build" / "out.bin").write_bytes(b"\0")
        (self.root / ".graph" / "scratch.md").write_text("x\n", encoding="utf-8")
        result = self.invoke()
        self.assertEqual([(f["level"], f["id"], f["path"]) for f in result["findings"]],
                         [("error", "stray-file", ".gitignore"), ("error", "stray-file", "notes.txt")])

    def test_unmerged_branch_waits_under_pr(self):
        self.advance(BRANCH)
        result = self.invoke(integration="pr")
        self.assertEqual((result["run_end"], self.ids(result, "info")), ("CLEAN", ["waiting-merge"]))

    def test_unmerged_branch_fails_under_push_main(self):
        self.advance(BRANCH)
        result = self.invoke(integration="push-main")
        self.assertEqual((result["run_end"], self.ids(result, "error")), ("DIRTY (1)", ["branch-unmerged"]))

    def test_missing_branch_waits_with_reason(self):
        [finding] = self.invoke(integration="push-main", branch="graph/acme-missing")["findings"]
        self.assertEqual((finding["level"], finding["id"]), ("info", "waiting-merge"))
        self.assertIn("graph/acme-missing not found", finding["message"])

    def test_no_origin_waits_with_reason(self):
        git(self.root, "remote", "remove", "origin")
        [finding] = self.invoke(integration="push-main")["findings"]
        self.assertEqual((finding["level"], finding["id"]), ("info", "waiting-merge"))
        self.assertTrue(finding["message"].endswith(": no origin"), finding["message"])

    def test_origin_head_wins_over_main(self):
        git(self.root, "update-ref", "refs/remotes/origin/release", f"{BRANCH}~1")
        git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/release")
        self.assertEqual(self.ids(self.invoke(integration="push-main")), ["branch-unmerged"])

    def test_default_ref_falls_back_without_origin_head(self):
        git(self.root, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        self.assertEqual(self.invoke(integration="push-main")["run_end"], "CLEAN")
        self.advance(BRANCH)
        self.assertEqual(self.ids(self.invoke(integration="push-main")), ["branch-unmerged"])

    def test_origin_without_default_branch_waits(self):
        git(self.root, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        git(self.root, "update-ref", "-d", "refs/remotes/origin/main")
        [finding] = self.invoke(integration="push-main")["findings"]
        self.assertEqual((finding["level"], finding["id"]), ("info", "waiting-merge"))

    def test_detached_main_checkout_is_not_dirty(self):
        git(self.root, "checkout", "-q", "--detach")
        self.assertEqual(self.invoke()["run_end"], "CLEAN")

    def test_every_defect_counts(self):
        self.dirty()
        result = self.invoke(integration="push-main")
        self.assertEqual(result["run_end"], "DIRTY (4)")
        self.assertEqual(self.ids(result), ["branch-unmerged", "main-dirty", "stray-file", "worktree-left"])

    def test_each_check_opts_out_alone(self):
        self.dirty()
        every = {"main-dirty", "worktree-left", "branch-unmerged", "stray-file"}
        for key, ident in (("mainClean", "main-dirty"), ("worktrees", "worktree-left"),
                           ("branchMerged", "branch-unmerged"), ("strayFiles", "stray-file")):
            with self.subTest(key=key):
                self.profile.write_text(f"hygiene:\n  runEnd: {{{key}: false}}\n", encoding="utf-8")
                result = self.invoke(integration="push-main")
                self.assertEqual(set(self.ids(result)), every - {ident})
                self.assertEqual(result["run_end"], "DIRTY (3)")


if __name__ == "__main__":
    unittest.main()
