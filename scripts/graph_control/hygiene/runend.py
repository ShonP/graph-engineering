"""run-end: a run is not done while the main checkout is dirty, a run worktree remains, the run branch
is unmerged or a stray file exists. Reads git only, never fetches and never removes anything."""

import subprocess
from pathlib import Path

from . import Context, Finding

ID = "run-end"
MODES = frozenset({"run-end"})
QUICK = False
IGNORED = ".graph/"
DEFAULTS = ("refs/remotes/origin/main", "refs/remotes/origin/master")


def _git(ctx: Context, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ctx.root), *args], capture_output=True, text=True)


def _paths(raw: str) -> list[str]:
    return [path for path in raw.split("\0") if path and not path.startswith(IGNORED)]


def _status_paths(raw: str) -> list[str]:
    tokens, paths = iter(raw.split("\0")), []
    for token in tokens:
        if len(token) > 3:
            paths.append(token[3:])
            if "R" in token[:2] or "C" in token[:2]:
                next(tokens, None)
    return [path for path in paths if not path.startswith(IGNORED)]


def _main_clean(ctx: Context) -> list[Finding]:
    raw = _git(ctx, "status", "--porcelain=v1", "-z", "--untracked-files=no").stdout
    return [Finding("error", "main-dirty", f"the main checkout has an uncommitted change: {path}",
                    "commit, stash or revert it in the main checkout", path) for path in _status_paths(raw)]


def _worktrees(ctx: Context) -> list[Finding]:
    prefix, found = f"{ctx.run_id}-", []
    blocks = _git(ctx, "worktree", "list", "--porcelain").stdout.strip().split("\n\n")
    for block in blocks:
        fields = dict(line.partition(" ")[::2] for line in block.splitlines())
        path, branch = fields.get("worktree", ""), fields.get("branch", "").removeprefix("refs/heads/")
        if branch == _branch(ctx) or Path(path).name == ctx.run_id:
            found.append(Finding("warn", "worktree-left", f"run integration worktree still present: {path}",
                                 f"after landing, `git worktree remove {path}`", path))
            continue
        if not (branch.startswith(prefix) or Path(path).name.startswith(prefix)):
            continue
        fix = ("git worktree prune" if "prunable" in fields else
               f"bash {ctx.plugin_root}/scripts/worktree-gc.sh --apply --prefix {prefix} --base {_branch(ctx)}")
        found.append(Finding("error", "worktree-left", f"run worktree still present: {path} ({branch or 'detached'})",
                             fix, path))
    return found


def _branch(ctx: Context) -> str:
    return ctx.branch or f"graph/{ctx.run_id}"


def _default_ref(ctx: Context) -> str | None:
    head = _git(ctx, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    candidates = ([head.stdout.strip()] if head.returncode == 0 else []) + list(DEFAULTS)
    return next((ref for ref in candidates if _git(ctx, "rev-parse", "--verify", "--quiet", ref).returncode == 0),
                None)


def _waiting(branch: str, reason: str) -> list[Finding]:
    return [Finding("info", "waiting-merge", f"run branch {branch} is waiting for its merge: {reason}",
                    "merge it per the profile's integration, then re-run the run-end check")]


def _branch_merged(ctx: Context) -> list[Finding]:
    branch = _branch(ctx)
    if _git(ctx, "remote", "get-url", "origin").returncode != 0:
        return _waiting(branch, "no origin")
    default = _default_ref(ctx)
    if default is None:
        return _waiting(branch, "no origin default branch (origin/HEAD, origin/main or origin/master)")
    head = _git(ctx, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{branch}^{{commit}}")
    if head.returncode != 0:
        return _waiting(branch, f"branch {branch} not found")
    if _git(ctx, "merge-base", "--is-ancestor", head.stdout.strip(), default).returncode == 0:
        return []
    if ctx.integration == "push-main":
        return [Finding("error", "branch-unmerged", f"run branch {branch} is not an ancestor of {default}",
                        "land it per integration push-main: rebase on the default branch and push HEAD to it")]
    return _waiting(branch, f"not yet an ancestor of {default}")


def _stray_files(ctx: Context) -> list[Finding]:
    raw = _git(ctx, "ls-files", "--others", "--exclude-standard", "-z").stdout
    return [Finding("error", "stray-file", f"untracked file not covered by .gitignore: {path}",
                    "commit it, delete it or add it to .gitignore", path) for path in _paths(raw)]


CHECKS = (("mainClean", _main_clean), ("worktrees", _worktrees), ("branchMerged", _branch_merged),
          ("strayFiles", _stray_files))


def run(ctx: Context) -> list[Finding]:
    return [finding for key, check in CHECKS if getattr(ctx.config.runEnd, key) for finding in check(ctx)]
