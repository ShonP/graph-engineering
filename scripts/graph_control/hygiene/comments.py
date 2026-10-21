"""comments: with comments.mode none, a comment-only line the diff adds is an error at path:line.

Only whole-line comments are read, by the marker the file extension uses; a `*` line counts only inside
a `/*` block opened by a comment-only line, and a line-1 shebang never counts; a trailing comment after
code is never checked, so a marker inside a string literal on a code line cannot fire. A line
matching a comments.allow regex passes, and while comments.cite is true so does a comment citing a
URL (an issue, a spec): the one exception the no-comments rule keeps.
"""

import functools
import re
from collections.abc import Callable
from pathlib import PurePosixPath

from . import Context, Finding
from ..common import Invalid
from .scope import added_lines, git

ID = "comments"
MODES = frozenset({"staged", "base"})
QUICK = False
SLASH = ("//", "/*")
STAR = "*"
SHEBANG = "#!"
MARKERS = {**dict.fromkeys(("ts", "tsx", "js", "jsx", "swift", "kt", "kts", "java", "go", "rs", "c", "h", "cpp",
                            "cs", "css"), SLASH),
           **dict.fromkeys(("py", "sh", "bash", "rb", "yaml", "yml", "toml"), ("#",)),
           **dict.fromkeys(("sql", "lua"), ("--",))}
CITE = re.compile(r"https?://\S")
FIX = ("delete the comment and let names carry the meaning; trailing comments after code are not checked; "
       "a needed line goes in hygiene.comments.allow (a regex), or set hygiene.comments.mode: any")


def _blocks(ctx: Context, path: str) -> set[int]:
    rev = ":" if ctx.mode == "staged" else "HEAD:"
    inside, opened = set(), False
    for number, line in enumerate(git(ctx.root, "show", f"{rev}{path}").split("\n"), 1):
        text = line.strip()
        if opened:
            inside.add(number)
            opened = "*/" not in text
        elif text.startswith("/*"):
            opened = "*/" not in text[2:]
    return inside


def _comment(text: str, number: int, markers: tuple[str, ...], block: Callable[[], set[int]]) -> bool:
    if number == 1 and text.startswith(SHEBANG):
        return False
    if text.startswith(markers):
        return True
    return markers is SLASH and text.startswith(STAR) and number in block()


def _compiled(patterns: tuple[str, ...]) -> list[re.Pattern[str]]:
    try:
        return [re.compile(pattern) for pattern in patterns]
    except re.error as error:
        raise Invalid(f"profile key hygiene.comments.allow holds an invalid regex {error.pattern!r}") from error


def run(ctx: Context) -> list[Finding]:
    settings = ctx.config.comments
    if settings.mode == "any":
        return []
    allow = _compiled(settings.allow)
    found = []
    for item in ctx.files:
        markers = MARKERS.get(PurePosixPath(item.path).suffix[1:].lower())
        if not markers:
            continue
        block = functools.cache(functools.partial(_blocks, ctx, item.path))
        for number, line in added_lines(ctx.root, item.path, None if ctx.mode == "staged" else ctx.base):
            text = line.strip()
            if not _comment(text, number, markers, block) or any(pattern.search(text) for pattern in allow):
                continue
            if settings.cite and CITE.search(text):
                continue
            found.append(Finding("error", "comment-added", f"{item.path}:{number} adds a comment-only line", FIX,
                                 item.path, number))
    return found
