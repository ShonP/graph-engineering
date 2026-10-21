"""private-names: scope files that name a private consumer, reported by path and line only.

The list and the matcher are scripts/check-private-names.py's; an unconfigured list is a finding
at the hygiene.privateNames level.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

from . import Context, Finding, Row

ID = "private-names"
MODES = frozenset({"staged", "base", "tracked", "doctor"})
QUICK = True
HIT_FIX = "remove or rename it, or exempt the path with allow=<glob> on its entry in the private-names list"


def _check(plugin_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("ge_check_private_names",
                                                  plugin_root / "scripts" / "check-private-names.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unconfigured(check: ModuleType) -> tuple[str, str]:
    return ("no private-names list is configured, so no file is checked for private consumer names",
            f"set GRAPH_PRIVATE_NAMES or create {check.list_path()}, one name per line")


def run(ctx: Context) -> list[Finding]:
    level = ctx.config.privateNames
    if level == "off":
        return []
    check = _check(ctx.plugin_root)
    entries, _ = check.load()
    if not entries:
        return [Finding(level, "private-names-unconfigured", *_unconfigured(check))]
    found = []
    for rel, line in check.scan(ctx.root, [item.path for item in ctx.files], entries):
        where = rel if line is None else f"{rel}:{line}"
        found.append(Finding("error", "private-name", f"{where} names a private consumer", HIT_FIX, rel, line))
    return found


def doctor(ctx: Context) -> list[Row]:
    level = ctx.config.privateNames
    if level == "off":
        return []
    check = _check(ctx.plugin_root)
    entries, _ = check.load()
    return [] if entries else [(level, "private-names-unconfigured", *_unconfigured(check))]
