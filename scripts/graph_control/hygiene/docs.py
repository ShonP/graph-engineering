"""docs: backticked paths and path:line cites under a tracked top-level entry must resolve against git ls-files.

The docs are the tracked files matching docs.roots minus docs.ignore, or the one --text file.
"""

import re
from pathlib import PurePosixPath

from ..risk import matcher
from . import Context, Finding
from .scope import git, read_text

ID = "docs"
MODES = frozenset({"base", "tracked", "text"})
QUICK = False
SPAN = re.compile(r"`([^`\n]+)`")
TOKEN = re.compile(r"(?P<path>[\w./@*?{},\[\]+-]+)(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?")
GLOB = re.compile(r"[*?\[{]")
FENCE = "```"


def _cites(text: str) -> list[tuple[int, str, str, int | None]]:
    cites, fenced = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(FENCE):
            fenced = not fenced
            continue
        for span in [] if fenced else SPAN.findall(line):
            match = TOKEN.fullmatch(span)
            if not match or "{{" in span:
                continue
            last = match["end"] or match["start"]
            cites.append((number, span, match["path"].removeprefix("./").rstrip("/"), int(last) if last else None))
    return cites


class Tree:
    def __init__(self, root):
        self.root = root
        self.files = frozenset(git(root, "ls-files", "-z").split("\0")) - {""}
        self.dirs = frozenset(str(parent) for name in self.files for parent in PurePosixPath(name).parents)
        self.tops = frozenset(name.split("/")[0] for name in self.files)
        self.counts: dict[str, int | None] = {}

    def claims(self, path: str) -> bool:
        return path.split("/")[0] in self.tops

    def lines(self, name: str) -> int | None:
        if name not in self.counts:
            try:
                self.counts[name] = len((self.root / name).read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeDecodeError):
                self.counts[name] = None
        return self.counts[name]

    def check(self, path: str, line: int | None) -> tuple[str, str] | None:
        if GLOB.search(path):
            hit = matcher([path]).match
            return None if any(hit(name) for name in self.files) else ("doc-path", "matches no tracked file")
        if line is None:
            missing = path not in self.files and path not in self.dirs
            return ("doc-path", "does not exist in the tracked tree") if missing else None
        if path not in self.files:
            return "doc-path", "is not a tracked file"
        count = self.lines(path)
        if count is None or line <= count:
            return None
        return "doc-line", f"cites line {line}, but {path} has {count} lines"


def _docs(ctx: Context) -> list[tuple[str, str]]:
    if ctx.mode == "text":
        return [(str(ctx.text), ctx.text.read_text(encoding="utf-8", errors="replace"))]
    roots, ignore = matcher(ctx.config.docs.roots).match, matcher(ctx.config.docs.ignore).match
    docs = [item for item in ctx.files if roots(item.path) and not ignore(item.path)]
    return [(item.path, text) for item in docs if (text := read_text(ctx.root, item)) is not None]


def run(ctx: Context) -> list[Finding]:
    docs = _docs(ctx)
    if not docs:
        return []
    tree, ignore = Tree(ctx.root), matcher(ctx.config.docs.ignore).match
    findings = []
    for doc, text in docs:
        for number, span, path, line in _cites(text):
            problem = tree.check(path, line) if tree.claims(path) and not ignore(path) else None
            if problem:
                findings.append(Finding("error", problem[0], f"`{span}` {problem[1]}",
                                        f"correct the path in {doc}, or add {doc} to hygiene.docs.ignore",
                                        doc, number))
    return findings
