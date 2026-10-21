import importlib.util
from pathlib import Path
from types import ModuleType

from . import Context, Finding, Row

ID = "checks-expiry"
MODES = frozenset({"doctor"})
QUICK = True
WARN_DAYS = 7
CONFIG = Path(".claude") / "graph-checks.json"


def _checks_config(plugin_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("ge_checks_config", plugin_root / "hooks" / "scripts" / "checks_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(ctx: Context) -> list[Finding]:
    return []


def doctor(ctx: Context) -> list[Row]:
    path = ctx.root / CONFIG
    if not path.is_file():
        return []
    try:
        checks = _checks_config(ctx.plugin_root).load(path).checks
    except (ValueError, OSError):
        return []
    today, rows = ctx.now.date(), []
    for check in checks:
        if check.mode != "advisory":
            continue
        left = (check.expires - today).days
        if left <= 0:
            rows.append(("error", "check-expired",
                         f"advisory check {check.id} in {CONFIG} expired on {check.expires}, so it now blocks the gate",
                         f"make {check.id} pass, then set its mode to blocking and drop expires"))
        elif left <= WARN_DAYS:
            rows.append(("warn", "check-expiring",
                         f"advisory check {check.id} starts blocking on {check.expires} "
                         f"(in {left} day{'' if left == 1 else 's'})",
                         f"make {check.id} pass before then, or move expires with the reason in the commit"))
    return rows
