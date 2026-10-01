"""Skill receipt: every REQUIRED skill a dispatch named appears in the child's `skills_loaded:` line.

A required qualified name `ns:skill` is proven only by the identical qualified
name: a loaded name in another namespace never counts, and a loaded bare name
proves only a required bare name. So a bare REQUIRED name that a host built-in
shares (bare `security-review` resolved to the host's own in 7 of 7 measured
reviews) is the routing's problem, which check-routing-resolves and doctor's
`routing-bare` flag. There is no host snapshot to go stale. Pure: no I/O.
"""

import re

from .common import require

NAME = re.compile(r"[a-z0-9][a-z0-9_-]*(?::[a-z0-9][a-z0-9_-]*)?")
NOTE = re.compile(r"\([^()]*\)")  # an annotation such as `(preloaded)`
PREFIX = "skills_loaded:"
FORMAT = "write the line as `skills_loaded: <plugin>:<skill>, ...`"


def names(value: str) -> tuple[str, ...]:
    """Comma-separated names, lowercased, deduplicated in order; Invalid on a name the pattern rejects.

    Tolerant of how a model writes the line: the `skills_loaded:` prefix,
    backticks, surrounding whitespace and parenthetical annotations are dropped."""
    value = NOTE.sub(" ", value.replace("`", "")).strip()
    value = value[len(PREFIX):] if value.lower().startswith(PREFIX) else value
    result: list[str] = []
    for item in (part.strip().lower() for part in value.split(",")):
        if not item:
            continue
        require(NAME.fullmatch(item) is not None, f"not a skill name: {item!r}; {FORMAT}")
        if item not in result:
            result.append(item)
    return tuple(result)


def missing(required: tuple[str, ...], loaded: tuple[str, ...]) -> list[str]:
    """The required names, in order, that no identical loaded name proves."""
    proven = set(loaded)
    return [name for name in required if name not in proven]
