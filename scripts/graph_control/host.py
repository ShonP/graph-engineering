"""Host inspection before a wave: free disk, load, a bare repo, base freshness, docker.

This is host inspection, not project execution; graph_control never runs a
configured project command. The only processes started are:

- read-only git queries on local refs (`config --get`, `symbolic-ref`,
  `show-ref`, `rev-parse`, `rev-list --count`), with GIT_DIR and friends
  scrubbed. Never fetch, pull or anything else that touches a remote, so
  "behind" means behind the last fetch.
- `docker info` with a 5 s timeout, and only when the profile's runtime.up or
  runtime.command names docker or compose. It asks whichever daemon the
  environment points at (DOCKER_HOST, or the local socket) whether it
  answers. A profile without them is never probed.

Free disk below the minimum is the one blocking finding (`disk-low`).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .doctor import LEVELS, Finding

GB = 10**9
BLOCKING = "disk-low"
DOCKER_TIMEOUT = 5
GIT_TIMEOUT = 10
CONTAINERS = re.compile(r"docker|compose", re.IGNORECASE)
GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def inspect(root: Path, min_free_gb: int, profile: dict[str, Any] | None) -> list[Finding]:
    """Every host finding for `root`, errors first."""
    findings = [*_disk(root, min_free_gb), *_load(), *_bare(root), *_behind(root), *_docker(profile)]
    return sorted(findings, key=lambda finding: LEVELS.index(finding.level))


def blocking(findings: list[Finding]) -> Finding | None:
    return next((finding for finding in findings if finding.id == BLOCKING), None)


def _disk(root: Path, min_free_gb: int) -> list[Finding]:
    free = shutil.disk_usage(root).free / GB
    if free >= min_free_gb:
        return []
    return [Finding("error", BLOCKING, f"{free:.1f} GB free on the volume holding {root}, below the {min_free_gb} GB minimum",
                    "free space on that volume (the plugin's scripts/worktree-gc.sh lists merged worktrees; the engine "
                    "removes a run's own from its run worktree with --apply --base <run branch> --prefix <run8>-), "
                    "or lower --min-free-gb")]


def _load() -> list[Finding]:
    try:
        load = os.getloadavg()[0]
    except (AttributeError, OSError):  # not every platform reports a load average
        return []
    cores = os.cpu_count() or 1
    if load < cores:
        return []
    return [Finding("warn", "load-high", f"1-minute load average {load:.2f} is at or above the {cores} cores",
                    "let running builds or agents finish before dispatching more, or narrow the wave")]


def _git(root: Path, *args: str) -> str | None:
    environment = {key: value for key, value in os.environ.items() if key not in GIT_VARS}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                                timeout=GIT_TIMEOUT, env=environment, stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _bare(root: Path) -> list[Finding]:
    if _git(root, "config", "--type=bool", "--get", "core.bare") != "true":
        return []
    return [Finding("error", "bare-repo", f"core.bare is true for the repository at {root}, so checkouts and worktrees fail",
                    "if this repository is meant to have a working tree: git config core.bare false")]


def _default_branch(root: Path) -> str | None:
    remote_head = _git(root, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
    if remote_head:
        return remote_head.split("/", 1)[-1]
    for name in (_git(root, "config", "--get", "init.defaultBranch"), "main", "master"):
        if name and _git(root, "show-ref", "-q", "--verify", f"refs/heads/{name}") is not None:
            return name
    return None


def _behind(root: Path) -> list[Finding]:
    branch = _default_branch(root)
    upstream = branch and _git(root, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")
    count = upstream and _git(root, "rev-list", "--count", f"{branch}..{branch}@{{upstream}}")
    if not count or not count.isdigit() or int(count) == 0:
        return []
    plural = "" if count == "1" else "s"
    return [Finding("info", "base-behind",
                    f"{branch} is {count} commit{plural} behind {upstream} (local refs; nothing was fetched)",
                    f"fast-forward {branch} to {upstream} before cutting worktrees from it")]


def _docker(profile: dict[str, Any] | None) -> list[Finding]:
    runtime = profile.get("runtime") if isinstance(profile, dict) else None
    if not isinstance(runtime, dict) or not any(CONTAINERS.search(str(runtime.get(key) or "")) for key in ("up", "command")):
        return []
    try:
        answered = subprocess.run(["docker", "info"], capture_output=True, timeout=DOCKER_TIMEOUT,
                                  stdin=subprocess.DEVNULL, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        answered = False
    if answered:
        return []
    return [Finding("warn", "docker-unreachable",
                    f"the profile's runtime uses docker or compose, but `docker info` did not succeed within {DOCKER_TIMEOUT} s",
                    "start the container engine before the runtime is brought up")]
