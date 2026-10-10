#!/usr/bin/env python3
"""Fail when a tracked file or path names a private consumer (product, person, repo).

The plugin is public, so the banned names never live in it. They come from,
in order:
  1. env GRAPH_PRIVATE_NAMES: entries separated by `;` or newlines
  2. ${XDG_CONFIG_HOME:-~/.config}/graph-engineering/private-names.txt

One entry per line (or per `;` in the env), `#` starts a comment:
  <name> [allow=<glob>[,<glob>...]]
`allow=` exempts tracked paths matching a glob (fnmatch, repo-relative), for
the rare place a name belongs, such as a publisher field in a manifest.

Matching is case-insensitive over every `git ls-files` path and the text of
every tracked file (binary files skipped). A name counts at a word edge or an
identifier seam: before it, nothing, a non-letter or a lowercase-to-Name camel
join (`myName`); after it, nothing, a non-letter (`_`, a digit, `-`, `.`) or a
name-to-Upper camel join (`NameKit`). A longer lowercase word that merely
starts or ends with the name (`equivalent` for `equiv`) does not count.
A hit prints the path (and line), never the name.
With no list configured (public CI) it prints a `SKIP` line and exits 0, which
run-all-tests reports as partial rather than passed.
  python3 scripts/check-private-names.py [repo]
Exit 1 on any hit, 0 otherwise.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

TAG = "check-private-names"


def list_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "graph-engineering" / "private-names.txt"


def parse(lines):
    entries = []
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, _, rest = line.partition(" allow=")
        globs = [g.strip() for g in rest.split(",") if g.strip()]
        entries.append((name.strip(), globs))
    return entries


def load():
    env = os.environ.get("GRAPH_PRIVATE_NAMES", "").strip()
    if env:
        return parse(re.split(r"[;\n]", env)), "GRAPH_PRIVATE_NAMES"
    path = list_path()
    if path.is_file():
        return parse(path.read_text(encoding="utf-8").splitlines()), str(path)
    return [], str(path)


def seam(left: str, right: str) -> bool:
    """A camel-case join between two letters: lowercase then uppercase."""
    return left.islower() and right.isupper()


def names(text: str, pattern: re.Pattern) -> bool:
    for m in pattern.finditer(text):
        start, end = m.start(), m.end()
        before = text[start - 1] if start else ""
        after = text[end] if end < len(text) else ""
        if before.isalpha() and not seam(before, text[start]):
            continue
        if after.isalpha() and not seam(text[end - 1], after):
            continue
        return True
    return False


def main(argv):
    repo = Path(argv[1] if len(argv) > 1 else ".").resolve()
    entries, source = load()
    if not entries:
        print(f"SKIP {TAG}: no list configured (set GRAPH_PRIVATE_NAMES or create {source})")
        return 0
    files = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"], check=True, capture_output=True
    ).stdout.decode().split("\0")
    files = [f for f in files if f]
    patterns = [(re.compile(re.escape(name), re.I), globs) for name, globs in entries]
    hits = 0
    for rel in files:
        active = [p for p, globs in patterns if not any(fnmatch.fnmatch(rel, g) for g in globs)]
        if not active:
            continue
        if any(names(rel, p) for p in active):
            print(f"FAIL {rel}: path names a private consumer")
            hits += 1
        path = repo / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            if any(names(line, p) for p in active):
                print(f"FAIL {rel}:{number}: names a private consumer")
                hits += 1
    if hits:
        print(f"{TAG}: {hits} hit(s) name a private consumer (list: {source})")
        return 1
    print(f"ok {TAG}: {len(entries)} name(s), {len(files)} tracked file(s), list: {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
