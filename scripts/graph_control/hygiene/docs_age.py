"""docs-age: a tracked doc matching docs.ephemeral warns once its last commit (committer date) is more
than docs.ephemeralDays whole days old and errors past twice that. --base checks the same tracked set,
since the age is about the file, not the diff. Uncommitted files are skipped. History is not followed
across renames, so a renamed doc ages from its rename; a shallow clone ages from its oldest commit."""

import subprocess

from . import Context, Finding
from ..risk import matcher
from .scope import tracked

ID = "docs-age"
MODES = frozenset({"base", "tracked"})
QUICK = False
DAY = 86400
MARK = "\x01"
FIX = "delete it in the merge PR of the run that shipped it; git history keeps it"


def _last_commits(ctx: Context, paths: list[str]) -> dict[str, int]:
    result = subprocess.run(["git", "-C", str(ctx.root), "--literal-pathspecs", "log", "-z", f"--format={MARK}%ct",
                             "--name-only", "HEAD", "--", *paths], capture_output=True, text=True)
    stamps, stamp = {}, 0
    for token in result.stdout.split("\0"):
        if token.startswith(MARK):
            stamp = int(token[1:])
        elif path := token.removeprefix("\n"):
            stamps.setdefault(path, stamp)
    return stamps


def _finding(path: str, age: int, limit: int) -> Finding | None:
    if age <= limit:
        return None
    twice = age > 2 * limit
    bound = f"{'twice ' if twice else ''}hygiene.docs.ephemeralDays {limit}"
    return Finding("error" if twice else "warn", "doc-ephemeral",
                   f"ephemeral doc {path} was last committed {age} days ago, over {bound}", FIX, path)


def run(ctx: Context) -> list[Finding]:
    docs = ctx.config.docs
    if not docs.ephemeral:
        return []
    match = matcher(docs.ephemeral)
    files = ctx.files if ctx.mode == "tracked" else tracked(ctx.root)
    paths = [item.path for item in files if match.match(item.path)]
    if not paths:
        return []
    now = int(ctx.now.timestamp())
    findings = (_finding(path, (now - stamp) // DAY, docs.ephemeralDays)
                for path, stamp in sorted(_last_commits(ctx, paths).items()))
    return [finding for finding in findings if finding]
