"""comments: with comments.mode none, a comment-only line the diff adds is an error at path:line.

Only whole-line comments are read, by the marker the file extension uses; a trailing comment after
code is never checked, so a marker inside a string literal on a code line cannot fire. A line
matching a comments.allow regex passes, and while comments.cite is true so does a comment citing a
URL (an issue, a spec): the one exception the no-comments rule keeps.
"""

import re
from pathlib import PurePosixPath

from . import Context, Finding
from ..common import Invalid
from .scope import git

ID = "comments"
MODES = frozenset({"staged", "base"})
QUICK = False
SLASH = ("//", "/*", "*")
MARKERS = {**dict.fromkeys(("ts", "tsx", "js", "jsx", "swift", "kt", "kts", "java", "go", "rs", "c", "h", "cpp",
                            "cs", "css"), SLASH),
           **dict.fromkeys(("py", "sh", "bash", "rb", "yaml", "yml", "toml"), ("#",)),
           **dict.fromkeys(("sql", "lua"), ("--",))}
CITE = re.compile(r"https?://\S")
HUNK = re.compile(r"^@@ -\S+ \+(\d+)")
FIX = ("delete the comment and let names carry the meaning; trailing comments after code are not checked; "
       "a needed line goes in hygiene.comments.allow (a regex), or set hygiene.comments.mode: any")


def _added(ctx: Context, path: str) -> list[tuple[int, str]]:
    revs = ("--cached",) if ctx.mode == "staged" else (f"{ctx.base}...HEAD",)
    patch = git(ctx.root, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-textconv", *revs, "--",
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
        for number, line in _added(ctx, item.path):
            text = line.strip()
            if not text.startswith(markers) or any(pattern.search(text) for pattern in allow):
                continue
            if settings.cite and CITE.search(text):
                continue
            found.append(Finding("error", "comment-added", f"{item.path}:{number} adds a comment-only line", FIX,
                                 item.path, number))
    return found
