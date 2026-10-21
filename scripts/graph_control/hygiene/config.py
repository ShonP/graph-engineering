"""The optional `hygiene:` profile block, parsed strictly into frozen dataclasses with defaults."""

from collections.abc import Callable
from dataclasses import MISSING, dataclass, field, fields
from typing import Any

from ..common import Invalid
from ..evidence_store import DEFAULT_PATH

LEVELS = ("warn", "error", "off")
Check = Callable[[Any, str], Any]


def _fail(key: str, why: str) -> None:
    raise Invalid(f"profile key {key} {why}")


def _boolean(value: Any, key: str) -> bool:
    if type(value) is not bool:
        _fail(key, "must be true or false")
    return value


def _count(minimum: int, maximum: int | None = None) -> Check:
    def check(value: Any, key: str) -> int:
        if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
            _fail(key, f"must be an integer from {minimum}" + (f" to {maximum}" if maximum else " up"))
        return value
    return check


def _choice(*options: str) -> Check:
    def check(value: Any, key: str) -> str:
        if value is False and "off" in options:
            return "off"
        if not isinstance(value, str) or value not in options:
            _fail(key, f"must be one of {', '.join(options)}")
        return value
    return check


def _text(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(key, "must be a nonempty string")
    return value


def _strings(value: Any, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail(key, "must be a list of strings")
    return tuple(_text(item, key) for item in value)


def _globs(value: Any, key: str) -> tuple[str, ...]:
    result = _strings(value, key)
    for glob in result:
        if glob.startswith(("/", "~")) or ".." in glob.split("/"):
            _fail(key, f"must hold repo-relative globs, not {glob!r}")
    return result


def _rows(cls: type) -> Check:
    def check(value: Any, key: str) -> tuple[Any, ...]:
        if not isinstance(value, list):
            _fail(key, "must be a list of mappings")
        return tuple(build(cls, item, f"{key}[{index}]") for index, item in enumerate(value))
    return check


def _section(cls: type) -> Check:
    return lambda value, key: build(cls, value, key)


def spec(check: Check, default: Any = MISSING) -> Any:
    if isinstance(default, type):
        return field(default_factory=default, metadata={"check": check})
    return field(default=default, metadata={"check": check})


def build(cls: type, value: Any, key: str) -> Any:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        _fail(key, "must be a mapping")
    known = {item.name: item for item in fields(cls)}
    for name in value:
        if name not in known:
            raise Invalid(f"unknown profile key {key}.{name}")
    missing = [name for name, item in known.items()
               if name not in value and item.default is MISSING and item.default_factory is MISSING]
    if missing:
        _fail(f"{key}.{missing[0]}", "is required")
    return cls(**{name: known[name].metadata["check"](raw, f"{key}.{name}") for name, raw in value.items()})


@dataclass(frozen=True)
class Media:
    enabled: bool = spec(_boolean, True)
    max_kb: int = spec(_count(1), 500)
    deny: tuple[str, ...] = spec(_globs, ())
    allow: tuple[str, ...] = spec(_globs, ())


@dataclass(frozen=True)
class Paths:
    home: str = spec(_choice(*LEVELS), "warn")


@dataclass(frozen=True)
class Literal:
    id: str = spec(_text)
    pattern: str = spec(_text)
    owner: tuple[str, ...] = spec(_globs)
    allow: tuple[str, ...] = spec(_globs, ())


@dataclass(frozen=True)
class Docs:
    roots: tuple[str, ...] = spec(_globs, ())
    ignore: tuple[str, ...] = spec(_globs, ())
    ephemeral: tuple[str, ...] = spec(_globs, ())
    ephemeralDays: int = spec(_count(1), 14)


@dataclass(frozen=True)
class Budget:
    id: str = spec(_text)
    globs: tuple[str, ...] = spec(_globs)
    max_bytes: int = spec(_count(1))


@dataclass(frozen=True)
class Context:
    budgets: tuple[Budget, ...] = spec(_rows(Budget), ())
    warn_pct: int = spec(_count(1, 100), 80)
    builtin: bool = spec(_boolean, True)


@dataclass(frozen=True)
class Comments:
    mode: str = spec(_choice("any", "none"), "any")
    allow: tuple[str, ...] = spec(_strings, ())


@dataclass(frozen=True)
class Surfaces:
    roots: tuple[str, ...] = spec(_globs, ())
    idleDays: int = spec(_count(1), 30)
    minCallers: int = spec(_count(1), 1)


@dataclass(frozen=True)
class RunEnd:
    mainClean: bool = spec(_boolean, True)
    worktrees: bool = spec(_boolean, True)
    branchMerged: bool = spec(_boolean, True)
    strayFiles: bool = spec(_boolean, True)


@dataclass(frozen=True)
class Measure:
    paths: tuple[str, ...] = spec(_globs, ())


@dataclass(frozen=True)
class Hygiene:
    media: Media = spec(_section(Media), Media)
    paths: Paths = spec(_section(Paths), Paths)
    privateNames: str = spec(_choice(*LEVELS), "warn")
    literals: tuple[Literal, ...] = spec(_rows(Literal), ())
    docs: Docs = spec(_section(Docs), Docs)
    context: Context = spec(_section(Context), Context)
    comments: Comments = spec(_section(Comments), Comments)
    surfaces: Surfaces = spec(_section(Surfaces), Surfaces)
    runEnd: RunEnd = spec(_section(RunEnd), RunEnd)
    measure: Measure = spec(_section(Measure), Measure)


@dataclass(frozen=True)
class UxEvidence:
    path: str
    store: bool


@dataclass(frozen=True)
class Config(Hygiene):
    docs_path: str | None = None
    ux_evidence: UxEvidence = field(default_factory=lambda: UxEvidence(DEFAULT_PATH, False))


def parse(profile: Any) -> Config:
    profile = profile if isinstance(profile, dict) else {}
    hygiene = build(Hygiene, profile.get("hygiene"), "hygiene")
    docs_path = profile.get("docsPath") if isinstance(profile.get("docsPath"), str) else None
    evidence = profile.get("uxEvidence") if isinstance(profile.get("uxEvidence"), dict) else {}
    path = evidence.get("path") if isinstance(evidence.get("path"), str) and evidence["path"].strip() else DEFAULT_PATH
    store = evidence.get("store")
    stored = isinstance(store, dict) and any(isinstance(value, str) and value.strip() for value in store.values())
    values = {item.name: getattr(hygiene, item.name) for item in fields(Hygiene)}
    return Config(**values, docs_path=docs_path, ux_evidence=UxEvidence(path, stored))
