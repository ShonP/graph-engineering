"""home-paths: text lines that name a user's home directory, reported by path and line only."""

import re

from . import Context, Finding
from ..risk import matcher
from .scope import read_text

ID = "home-paths"
MODES = frozenset({"staged", "base", "tracked"})
QUICK = True
PATTERN = re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/")
SKIP = ("**/fixtures/**", "**/test_*", "**/*_test.*", "**/*.test.*", "**/tests/**", "CHANGELOG*")
FIX = "write `~`, `$HOME` or a repo-relative path instead"


def run(ctx: Context) -> list[Finding]:
    level = ctx.config.paths.home
    if level == "off":
        return []
    skip = matcher(SKIP)
    found = []
    for item in ctx.files:
        text = None if skip.match(item.path) else read_text(ctx.root, item)
        for number, line in enumerate((text or "").split("\n"), 1):
            if PATTERN.search(line):
                found.append(Finding(level, "home-path", f"{item.path}:{number} names a home directory", FIX,
                                     item.path, number))
    return found
