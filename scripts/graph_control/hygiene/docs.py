"""docs: backticked repo paths and path:line cites in docs, or in one --text file, must resolve against git ls-files."""

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
EXTENSIONS = frozenset({"md", "mdx", "py", "sh", "ts", "tsx", "js", "jsx", "mjs", "cjs", "json", "yaml", "yml",
                        "toml", "txt", "swift", "kt", "kts", "go", "rs", "java", "rb", "sql", "html", "css", "xml",
                        "lock", "cfg", "ini", "plist", "gradle", "png", "jpg", "svg", "gif", "webp", "mp4"})


def _cites(text: str) -> list[tuple[int, str, str, int | None]]:
    cites, fenced = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(FENCE):
            fenced = not fenced
            continue
        for span in [] if fenced else SPAN.findall(line):
            match = TOKEN.fullmatch(span)
            if not match or span.startswith(("-", "/")) or "{{" in span:
                continue
            path = match["path"].removeprefix("./").rstrip("/")
            if "/" in match["path"] or PurePosixPath(path).suffix[1:] in EXTENSIONS:
                last = match["end"] or match["start"]
                cites.append((number, span, path, int(last) if last else None))
    return cites


class Tree:
    def __init__(self, root):
        self.root = root
        self.files = frozenset(git(root, "ls-files", "-z").split("\0")) - {""}
        self.dirs = frozenset(str(parent) for name in self.files for parent in PurePosixPath(name).parents)
        self.names = frozenset(PurePosixPath(name).name for name in self.files)
        self.counts: dict[str, int | None] = {}

    def candidates(self, path: str) -> list[str]:
        if "/" in path:
            return [path] if path in self.files else []
        return [name for name in self.files if PurePosixPath(name).name == path]

    def lines(self, name: str) -> int | None:
        if name not in self.counts:
            try:
                self.counts[name] = len((self.root / name).read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeDecodeError):
                self.counts[name] = None
        return self.counts[name]

    def check(self, path: str, line: int | None) -> tuple[str, str] | None:
        if GLOB.search(path):
            hit, names = matcher([path]).match, self.files if "/" in path else self.names
            return None if any(hit(name) for name in names) else ("doc-path", "matches no tracked file")
        found = self.candidates(path)
        if line is None:
            return None if found or path in self.dirs else ("doc-path", "does not exist in the tracked tree")
        if not found:
            return "doc-path", "is not a tracked file"
        counts = [count for count in map(self.lines, found) if count is not None]
        if not counts or line <= max(counts):
            return None
        return "doc-line", f"cites line {line}, but {found[0]} has {max(counts)} lines"


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
            problem = None if ignore(path) else tree.check(path, line)
            if problem:
                findings.append(Finding("error", problem[0], f"`{span}` {problem[1]}",
                                        f"correct the path in {doc}, or add {doc} to hygiene.docs.ignore",
                                        doc, number))
    return findings
