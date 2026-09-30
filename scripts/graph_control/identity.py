"""Read-only Git identity and fresh runtime attestations; no project execution."""

import hashlib
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .common import digest, file_hash, fingerprint, load, obj, require, text
from .run import Run, Source


def git(root: Path, *args: str) -> bytes:
    environment = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        environment.pop(key, None)
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
                            capture_output=True, timeout=30, env=environment, check=False)
    require(result.returncode == 0, f"cannot inspect Git candidate at {root}")
    return result.stdout


def snapshot(root: Path, repo: str) -> Source:
    root = root.resolve(strict=True)
    actual_root = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    require(root == actual_root, "candidate root must be the Git worktree root")
    revision = git(root, "rev-parse", "HEAD").decode().strip()
    dirty = hashlib.sha256()
    dirty.update(b"index\0" + git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", "--cached", "HEAD", "--"))
    dirty.update(b"worktree\0" + git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", "--"))
    paths = sorted(path for path in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if path)
    for raw in paths:
        path = root / os.fsdecode(raw)
        dirty.update(b"\0untracked\0" + raw + b"\0")
        if path.is_symlink():
            dirty.update(b"symlink\0" + os.fsencode(os.readlink(path)))
        else:
            require(path.is_file(), f"unsupported untracked entry: {path}")
            dirty.update(str(path.stat().st_mode & 0o777).encode() + b"\0")
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    dirty.update(block)
    return Source(repo, str(root), revision, dirty.hexdigest())


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(text(value).replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def fresh(value: str, max_age: int, now: datetime) -> None:
    age = (now - timestamp(value)).total_seconds()
    require(0 <= age <= max_age, "evidence expired or timestamp is in the future")


def validate_identity(run: Run, now: datetime, *, readiness_only: bool = False) -> None:
    for expected in run.candidate.sources:
        require(snapshot(Path(expected.root), expected.repo) == expected,
                f"candidate changed or wrong checkout: {expected.repo}")
    require(file_hash(Path(run.plan)) == run.plan_sha256, "plan changed since run manifest")
    require(file_hash(Path(run.profile)) == run.profile_sha256, "profile changed since run manifest")
    require(file_hash(Path(run.graph)) == run.graph_sha256, "graph changed since run manifest")
    if run.runtime_identity and not readiness_only:
        row = obj(load(Path(run.runtime_identity)), "fingerprint observed_at worker_revision images_sha256 "
                  "corpus_sha256 sources_sha256 run_id instance_id")
        require(digest(row["fingerprint"]) == run.candidate.runtime, "runtime fingerprint mismatch")
        require(digest(row["sources_sha256"]) == fingerprint([asdict(source) for source in run.candidate.sources]),
                "runtime source identity differs from complete candidate sources")
        require(text(row["run_id"]) == run.id, "runtime belongs to another run")
        text(row["instance_id"])
        require(text(row["worker_revision"]) in {source.revision for source in run.candidate.sources},
                "runtime worker does not serve a candidate source revision")
        digest(row["images_sha256"])
        digest(row["corpus_sha256"])
        expected = fingerprint({key: row[key] for key in (
            "worker_revision", "images_sha256", "corpus_sha256", "sources_sha256", "run_id", "instance_id")})
        require(expected == row["fingerprint"], "runtime identity contents do not match fingerprint")
        fresh(row["observed_at"], run.runtime_max_age_seconds, now)
