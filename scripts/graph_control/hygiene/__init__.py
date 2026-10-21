"""Hygiene rules: one module per rule in this package, discovered like graph-control commands.

A rule module defines ID (str), MODES (frozenset of MODE_NAMES), QUICK (bool: starts no process)
and run(ctx) -> list[Finding]. It defines doctor(ctx) -> list[(level, id, message, fix)] exactly
when MODES holds "doctor". run is called only for a mode in MODES; ctx is a Context. Levels are
error, warn and info; any error makes the run FAIL. Modules named `_*`, config and scope are not
rules. Read file text through scope.read_text, which returns None for binary or unreadable files.
A breach of this contract raises TypeError naming the module.
"""

import importlib
import pkgutil
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

from ..common import Invalid
from .config import Config, parse
from .scope import ScopeFile

MODE_NAMES = frozenset({"staged", "base", "tracked", "run-end", "sweep", "text", "doctor"})
NOT_RULES = frozenset({"config", "scope"})
PLUGIN_ROOT = Path(__file__).resolve().parents[3]
Row = tuple[str, str, str, str]


@dataclass(frozen=True)
class Finding:
    level: str
    id: str
    message: str
    fix: str
    path: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class Context:
    root: Path
    config: Config
    mode: str
    now: datetime
    files: tuple[ScopeFile, ...] = ()
    base: str | None = None
    run_id: str | None = None
    branch: str | None = None
    integration: str = "pr"
    text: Path | None = None
    plugin_root: Path = PLUGIN_ROOT


def _breaches(module: ModuleType) -> list[str]:
    modes = getattr(module, "MODES", None)
    checks = {"ID": isinstance(getattr(module, "ID", None), str),
              "MODES": isinstance(modes, frozenset) and modes <= MODE_NAMES,
              "QUICK": type(getattr(module, "QUICK", None)) is bool,
              "run": callable(getattr(module, "run", None)),
              "doctor": callable(getattr(module, "doctor", None)) == ("doctor" in (modes or ()))}
    return [name for name, ok in checks.items() if not ok]


def iter_rules(package: str = __name__) -> Iterator[ModuleType]:
    root = importlib.import_module(package)
    for info in sorted(pkgutil.iter_modules(root.__path__), key=lambda item: item.name):
        if info.name.startswith("_") or info.name in NOT_RULES:
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        breaches = _breaches(module)
        if breaches:
            raise TypeError(f"hygiene rule module {module.__name__} is missing or mistypes {breaches}")
        yield module


def doctor_rows(profile: Any, root: Path, quick: bool, package: str = __name__) -> list[Row]:
    try:
        config = parse(profile)
    except Invalid as error:
        return [("error", "hygiene-invalid", f"the hygiene profile block is invalid: {error}",
                 "correct or remove the named key under `hygiene:` in .claude/graph-profile.yaml")]
    ctx = Context(root=root, config=config, mode="doctor", now=datetime.now(timezone.utc))
    return [row for rule in iter_rules(package) if "doctor" in rule.MODES and (rule.QUICK or not quick)
            for row in rule.doctor(ctx)]
