"""media: added files over the size limit, denied paths, design media and stored UX evidence in git."""

import math
from pathlib import PurePosixPath

from . import Context, Finding
from ..evidence_store import MEDIA
from ..risk import matcher
from .scope import ScopeFile, git

ID = "media"
MODES = frozenset({"staged", "base", "tracked"})
QUICK = False
DEFAULT_DOCS = "docs"
Hit = tuple[str, str, str]


def _media(path: str) -> bool:
    return PurePosixPath(path).suffix.lower().lstrip(".") in MEDIA


def _under(path: str, folder: str) -> bool:
    return path.startswith(folder.strip("/") + "/")


def _hit(ctx: Context, item: ScopeFile, deny) -> Hit | None:
    path, remove = item.path, f"`git rm --cached -- {item.path}`"
    design = f"{(ctx.config.docs_path or DEFAULT_DOCS).strip('/')}/ux"
    evidence = ctx.config.ux_evidence
    if _media(path) and _under(path, design):
        return "media-design", f"{path} is design media under {design}/", \
            f"{remove}; design media stays in .graph/<run>/design/"
    if _media(path) and evidence.store and _under(path, evidence.path):
        return "media-evidence", f"{path} is UX evidence media under {evidence.path}", \
            f"push it with the `uxEvidence.store` push command, then {remove}"
    if deny.match(path):
        return "media-deny", f"{path} matches hygiene.media.deny", f"{remove}, or add it to `hygiene.media.allow`"
    limit, kb = ctx.config.media.max_kb, math.ceil(item.size / 1024)
    if item.status == "A" and kb > limit:
        return "media-size", f"{path}: {kb} KB > {limit} KB", \
            f"add it to `hygiene.media.allow` if it belongs in git, else {remove} or track it with git LFS"
    return None


def _lfs(ctx: Context, paths: list[str]) -> set[str]:
    if not paths:
        return set()
    out = git(ctx.root, "check-attr", "filter", "-z", "--stdin", stdin="\0".join(paths) + "\0").split("\0")
    return {path for path, value in zip(out[0::3], out[2::3]) if value == "lfs"}


def run(ctx: Context) -> list[Finding]:
    config = ctx.config.media
    if not config.enabled:
        return []
    allow, deny = matcher(config.allow), matcher(config.deny)
    hits = {item.path: hit for item in ctx.files if not allow.match(item.path) and (hit := _hit(ctx, item, deny))}
    exempt = _lfs(ctx, list(hits))
    return [Finding("error", ident, message, fix, path)
            for path, (ident, message, fix) in hits.items() if path not in exempt]
