"""docs: backticked paths and path:line cites under a tracked top-level entry must resolve against git ls-files.

A cite resolves from the repo root or from the citing doc's directory. The docs are the tracked files
matching docs.roots minus docs.ignore, or the one --text file, where a path HEAD's history deleted resolves too.
"""

import posixpath
import re
from pathlib import Path, PurePosixPath

from ..common import Invalid
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


def _parents(names: frozenset[str]) -> frozenset[str]:
    return frozenset(str(parent) for name in names for parent in PurePosixPath(name).parents)


def _deleted(root) -> frozenset[str]:
    try:
        names = git(root, "log", "--format=", "--name-only", "--diff-filter=D", "-z", "HEAD", "--")
    except Invalid:
        return frozenset()
    gone = frozenset(name.strip("\n") for name in names.split("\0")) - {""}
    return gone | _parents(gone)


class Tree:
    def __init__(self, root, history: bool = False):
        self.root = root
        self.files = frozenset(git(root, "ls-files", "-z").split("\0")) - {""}
        self.dirs = _parents(self.files)
        self.tops = frozenset(name.split("/")[0] for name in self.files)
        self.gone = _deleted(root) if history else frozenset()
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
        if path in self.gone and path not in self.files:
            return None
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


def _folder(ctx: Context, doc: str) -> str | None:
    if ctx.mode != "text":
        return PurePosixPath(doc).parent.as_posix()
    try:
        return Path(doc).resolve().parent.relative_to(Path(ctx.root).resolve()).as_posix()
    except ValueError:
        return None


def _problem(tree: Tree, folder: str | None, path: str, line: int | None) -> tuple[str, str] | None:
    candidates = [path]
    if folder not in (None, "."):
        joined = posixpath.normpath(posixpath.join(folder, path))
        if not joined.startswith("../"):
            candidates.append(joined)
    problems = [tree.check(candidate, line) for candidate in candidates]
    if None in problems:
        return None
    return next((item for item in problems if item[0] == "doc-line"), problems[0])


def _fix(ctx: Context, doc: str) -> str:
    if ctx.mode == "text":
        return f"correct the path in {doc}, or add the cited token to hygiene.docs.ignore"
    return f"correct the path in {doc}, or add {doc} to hygiene.docs.ignore"


def run(ctx: Context) -> list[Finding]:
    docs = _docs(ctx)
    if not docs:
        return []
    tree, ignore = Tree(ctx.root, history=ctx.mode == "text"), matcher(ctx.config.docs.ignore).match
    findings = []
    for doc, text in docs:
        folder = _folder(ctx, doc)
        for number, span, path, line in _cites(text):
            problem = _problem(tree, folder, path, line) if tree.claims(path) and not ignore(path) else None
            if problem:
                findings.append(Finding("error", problem[0], f"`{span}` {problem[1]}", _fix(ctx, doc), doc, number))
    return findings
