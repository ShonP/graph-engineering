"""Which files a hygiene run looks at, listed from git objects without reading their content."""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..common import Invalid

GITLINK = "160000"
HUNK = re.compile(r"^@@ -\S+ \+(\d+)")


@dataclass(frozen=True)
class ScopeFile:
    path: str
    status: str
    size: int
    binary: bool
    readable: bool = True


def git(root: Path, *args: str, stdin: str | None = None) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, input=stdin)
    if result.returncode:
        raise Invalid(f"git {args[0]} failed in {root}: {result.stderr.strip()}")
    return result.stdout


def commit(root: Path, rev: str) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", "--end-of-options",
                             f"{rev}^{{commit}}"], capture_output=True, text=True)
    if result.returncode:
        raise Invalid(f"unknown revision: {rev}")
    return result.stdout.strip()


def _empty_tree(root: Path) -> str:
    return git(root, "hash-object", "-t", "tree", "--stdin", stdin="").strip()


def _has_head(root: Path) -> bool:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD"],
                          capture_output=True).returncode == 0


def _listing(root: Path, *revs: str) -> list[ScopeFile]:
    options = ("-z", "--no-renames", "--no-ext-diff", "--no-textconv", "--diff-filter=AMT")
    raw = git(root, "diff", *options, "--raw", "--no-abbrev", *revs).split("\0")
    entries = {}
    for meta, path in zip(raw[0::2], raw[1::2]):
        _, mode, _, blob, status = meta.split(" ")
        if mode != GITLINK:
            entries[path] = (blob, "A" if status == "A" else "M")
    if not entries:
        return []
    numstat = git(root, "diff", *options, "--numstat", *revs).split("\0")
    binary = {line.split("\t", 2)[2] for line in numstat if line.startswith("-\t-\t")}
    blobs = sorted({blob for blob, _ in entries.values()})
    sizes = dict(line.split(" blob ") for line in git(root, "cat-file", "--batch-check", stdin="\n".join(blobs) + "\n")
                 .splitlines())
    return [ScopeFile(path, status, int(sizes[blob]), path in binary, os.access(root / path, os.R_OK))
            for path, (blob, status) in sorted(entries.items())]


def staged(root: Path) -> list[ScopeFile]:
    return _listing(root, "--cached", "HEAD" if _has_head(root) else _empty_tree(root))


def base(root: Path, rev: str) -> list[ScopeFile]:
    return _listing(root, f"{commit(root, rev)}...{commit(root, 'HEAD')}")


def tracked(root: Path) -> list[ScopeFile]:
    return _listing(root, "--cached", _empty_tree(root))


def added_lines(root: Path, path: str, base_rev: str | None) -> list[tuple[int, str]]:
    revs = (f"{base_rev}...HEAD",) if base_rev else ("--cached",)
    patch = git(root, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-textconv", *revs, "--",
                f":(literal){path}")
    lines, number = [], None
    for raw in patch.split("\n"):
        hunk = HUNK.match(raw)
        if hunk:
            number = int(hunk.group(1))
        elif number is not None and raw.startswith("+"):
            lines.append((number, raw[1:]))
            number += 1
    return lines


def read_text(root: Path, item: ScopeFile) -> str | None:
    if item.binary:
        return None
    try:
        return (root / item.path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
