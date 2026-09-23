"""Vet a Bruno collection's `smoke` requests before they run on a shared environment.

Usage: python3 vet_smoke.py <collection dir> [--test-tenant <value>]

Prints "RUN <file>" for a smoke request that is safe to run against a shared,
deployed environment, and "REFUSE <file> <reason>" for one that is not. Exit 1
when anything is refused.

Safe means: a GET, HEAD or OPTIONS request; or a write whose request URL PATH
has `{{testTenant}}` as a whole segment AND a non-empty --test-tenant was given.
A mention anywhere else - docs, body, query string, headers - does not count,
because it does not decide which tenant's rows the write touches. A file with
more than one method block is refused (Bruno sends the last one; an indented
block counts), and so is a path with `.` or `..` segments.

A request's file is not all Bruno sends: scripts run arbitrary JavaScript
(with axios and fetch available), so they can rewrite the request or send any
other. No denylist of calls can be complete, so this is an allowlist: a smoke
request is refused when its own file, or a `folder.bru` / `collection.bru`
between it and the collection root, has any non-empty `script:*` or `tests`
block, or a `vars` block that defines `testTenant` (request and runtime
variables beat `--env-var`, so a rebound tenant is a real tenant). Declarative
`assert` blocks are fine. Auth belongs in an `auth:*` block reading a variable
passed with `--env-var`, not in a script.

Exit 0: every smoke request is RUN. Exit 1: at least one REFUSE. Exit 2: the
collection directory is missing or has no smoke-tagged request - nothing was
vetted, which is BLOCKED, never a pass. Runs on Python 3.9+ (the macOS default).
"""

from __future__ import annotations

import pathlib
import re
import sys

READ_METHODS = {"get", "head", "options"}
METHOD_BLOCK = re.compile(
    r"^[ \t]*(get|head|options|post|put|patch|delete|graphql)\s*\{(.*?)^[ \t]*\}",
    re.S | re.M,
)
SCRIPT_HEADER = re.compile(r"^[ \t]*(script:[\w-]+|tests)\s*\{", re.M)
SCRIPT_BLOCK = re.compile(r"^[ \t]*(script:[\w-]+|tests)\s*\{(.*?)^\}", re.S | re.M)
VARS_BLOCK = re.compile(r"^[ \t]*vars(?::[\w-]+)?\s*\{(.*?)^[ \t]*\}", re.S | re.M)
TENANT_KEY = re.compile(r"^\s*~?testTenant\s*:", re.M)


def smoke_tagged(text: str) -> bool:
    meta = re.search(r"^meta\s*\{(.*?)^\}", text, re.S | re.M)
    if not meta:
        return False
    tags = re.search(r"tags:\s*\[(.*?)\]", meta.group(1), re.S)
    return bool(tags) and "smoke" in re.split(r"[\s,]+", tags.group(1))


def url_path(block: str) -> str:
    url = re.search(r"^\s*url:\s*(\S+)", block, re.M)
    if not url:
        return ""
    return url.group(1).split("?", 1)[0].split("#", 1)[0]


def script_risk(text: str) -> str | None:
    closed = {m.start(): m.group(2) for m in SCRIPT_BLOCK.finditer(text)}
    for header in SCRIPT_HEADER.finditer(text):
        body = closed.get(header.start())
        # An unclosed or oddly closed block is refused too: better a false
        # refusal than a script nobody read.
        if body is None or body.strip():
            return f"non-empty {header.group(1)} block"
    if any(TENANT_KEY.search(body) for body in VARS_BLOCK.findall(text)):
        return "a vars block rebinds testTenant"
    return None


def inherited_risk(f: pathlib.Path, root: pathlib.Path) -> str | None:
    d = f.parent
    while True:
        for name in ("folder.bru", "collection.bru"):
            p = d / name
            if p.is_file():
                reason = script_risk(p.read_text())
                if reason:
                    return f"{p.relative_to(root)}: {reason}"
        if d == root or root not in d.parents:
            return None
        d = d.parent


def verdict(text: str, tenant: str) -> str | None:
    risk = script_risk(text)
    if risk:
        return risk
    blocks = METHOD_BLOCK.findall(text)
    if not blocks:
        return "no method block"
    if len(blocks) > 1:
        # Bruno merges repeated method blocks and the LAST one wins, so the
        # first one is not what gets sent. Refuse rather than guess.
        return f"{len(blocks)} method blocks ({', '.join(b[0] for b in blocks)})"
    method, block = blocks[0]
    if method in READ_METHODS:
        return None
    segments = url_path(block).split("/")
    if ".." in segments or "." in segments:
        return f"{method} URL path has a relative segment"
    if "{{testTenant}}" not in segments:
        return f"{method} not scoped to {{{{testTenant}}}} in the URL path"
    if not tenant:
        return f"{method} scoped to {{{{testTenant}}}} but deploy.testTenant is empty"
    return None


def main() -> int:
    args = sys.argv[1:]
    tenant = ""
    if "--test-tenant" in args:
        i = args.index("--test-tenant")
        tenant = args[i + 1] if i + 1 < len(args) else ""
        del args[i : i + 2]
    if not args:
        print("usage: vet_smoke.py <collection dir> [--test-tenant <value>]", file=sys.stderr)
        return 2
    root = pathlib.Path(args[0]).resolve()
    if not root.is_dir():
        print(f"collection not found: {root}", file=sys.stderr)
        return 2
    refused = vetted = 0
    for f in sorted(root.rglob("*.bru")):
        if f.name in ("folder.bru", "collection.bru"):
            continue
        text = f.read_text()
        if not smoke_tagged(text):
            continue
        vetted += 1
        reason = verdict(text, tenant) or inherited_risk(f, root)
        if reason is None:
            print(f"RUN {f}")
        else:
            print(f"REFUSE {f} {reason}")
            refused += 1
    if not vetted:
        print(f"no smoke-tagged request under {root}", file=sys.stderr)
        return 2
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
