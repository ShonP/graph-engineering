"""The merge gate as a pure function: whether a green change merges without the owner.

The caller reads the profile from the run base, never the branch, and gathers
the inputs; this module does no I/O. Every condition is evaluated and reported
in a fixed order (floor, classes, findings, qa, verify), each line starting
`held:` or `failed:`; the gate opens only when all hold.

FLOOR and ALWAYS_OWNER are hard-coded, not profile rows, because a profile row
is exactly what a diff could edit or an owner could drop by mistake.
"""

from dataclasses import dataclass
from typing import Any

from .risk import CONTROL, matcher

FLOOR: tuple[str, ...] = ("**/.claude/graph-profile.yaml", "**/.claude/graph-checks.json",
                          "scripts/graph_control/**", "scripts/graph-control.py")
ALWAYS_OWNER: tuple[str, ...] = ("destructive", "credentials-and-access", "spend")
OFF, WHEN_GREEN, AUTO_MERGE = "off", "when-green", "auto-merge"


@dataclass(frozen=True)
class Inputs:
    risk_rows: tuple[str, ...]
    changed_paths: tuple[str, ...]
    blocking: int
    important: int
    qa_verdict: str
    verify_ok: bool
    auto_merge: bool = False


@dataclass(frozen=True)
class Decision:
    open: bool
    mode: str
    reasons: tuple[str, ...]


def _gates(profile: dict[str, Any]) -> dict[str, Any]:
    gates = profile.get("gates") if isinstance(profile, dict) else None
    return gates if isinstance(gates, dict) else {}


def _names(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def mode(profile: dict[str, Any], auto_merge: bool) -> str:
    if auto_merge is True:
        return AUTO_MERGE
    return WHEN_GREEN if _gates(profile).get("merge_auto") == WHEN_GREEN else OFF


def _floor(paths: tuple[str, ...]) -> str:
    match = matcher(FLOOR).match
    hit = next((path for path in paths if match(path)), None)
    if hit is not None:
        return f"failed: gate-floor {hit} changes the gate itself"
    return "held: gate-floor no changed path touches the gate"


def _classes(gates: dict[str, Any], current: str, rows: tuple[str, ...]) -> str:
    owner = {*_names(gates.get("owner_classes")), *ALWAYS_OWNER}
    waiting = [row for row in rows if row in owner]
    if current == OFF:
        auto = set(_names(gates.get("auto_classes"))) - {CONTROL}
        waiting += [row for row in rows if row not in auto and row not in waiting]
    if waiting:
        return f"failed: classes {', '.join(waiting)} wait for the owner in mode {current}"
    return f"held: classes {', '.join(rows)} may merge in mode {current}"


def _findings(blocking: int, important: int) -> str:
    state = "held" if blocking == 0 and important == 0 else "failed"
    return f"{state}: findings {blocking} blocking, {important} important"


def _qa(verdict: str) -> str:
    stripped = verdict.strip() if isinstance(verdict, str) else ""
    if stripped == "PASS":
        return "held: qa PASS"
    return f"failed: qa verdict {stripped or '(none)'!r} is not PASS"


def _verify(ok: bool) -> str:
    return "held: verify green" if ok is True else "failed: verify not green"


def decide(profile: dict[str, Any], inputs: Inputs) -> Decision:
    current = mode(profile, inputs.auto_merge)
    rows = tuple(inputs.risk_rows) or ("none",)
    reasons = (_floor(tuple(inputs.changed_paths)), _classes(_gates(profile), current, rows),
               _findings(inputs.blocking, inputs.important), _qa(inputs.qa_verdict), _verify(inputs.verify_ok))
    return Decision(all(reason.startswith("held:") for reason in reasons), current, reasons)
