"""Throwaway git repos for hygiene tests. Rule tasks import these; keep the signatures stable."""

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env)
    return result.stdout.strip()


def make_repo(tmp: Path, origin: bool = False) -> Path:
    root = Path(tmp).resolve() / "repo"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    for key, value in (("user.email", "example-user@api.example.test"), ("user.name", "example-user"),
                       ("commit.gpgsign", "false"), ("core.hooksPath", os.devnull)):
        git(root, "config", key, value)
    if origin:
        remote = root.parent / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True)
        git(root, "remote", "add", "origin", str(remote))
    return root


def write_profile(root: Path, text: str) -> Path:
    path = Path(root) / ".claude" / "graph-profile.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def stage(root: Path, rel: str, data: str | bytes) -> Path:
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    git(root, "add", "--", rel)
    return path


def commit_at(root: Path, msg: str, days_ago: float, now: datetime) -> str:
    stamp = (now - timedelta(days=days_ago)).isoformat()
    env = {**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    git(root, "commit", "-q", "--allow-empty", "-m", msg, env=env)
    return git(root, "rev-parse", "HEAD")
