"""findings.json v1: the review and qa verdict file the engine counts and routes.

Reviewers write findings.json (PASS or CHANGES-REQUESTED); qa writes
qa-findings.json in the same shape (PASS or FAIL). The prose contract lives in
skills/process/review-protocol/SKILL.md, whose JSON example a test parses here.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import Invalid, array, boolean, choice, integer, load, obj, require, text, unique, version

SEVERITIES = ("blocking", "important", "nit")
ROUTES = {"patch", "bad_plan", "intent_gap", "defer"}
STATUSES = {"open", "fixed", "refuted"}
VERDICTS = {"PASS", "CHANGES-REQUESTED", "FAIL"}
MIN_CONFIDENCE = 0.8
FINDING_ID = re.compile(r"F[1-9][0-9]*")
GIT_SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
FIELDS = "id severity file line scenario rule confidence route needs_author_context status"


def sha(value: Any) -> str:
    result = text(value)
    require(GIT_SHA.fullmatch(result) is not None, "expected a full lowercase git sha")
    return result


def confidence(value: Any) -> float:
    require(type(value) in (int, float) and 0 <= value <= 1, "confidence must be a number from 0.0 to 1.0")
    return float(value)


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    file: str
    line: int
    scenario: str
    rule: str
    confidence: float
    route: str
    needs_author_context: bool
    status: str

    @classmethod
    def parse(cls, value: Any) -> "Finding":
        row = obj(value, FIELDS)
        require(isinstance(row["id"], str) and FINDING_ID.fullmatch(row["id"]) is not None, "id must be F<n>")
        result = cls(row["id"], choice(row["severity"], set(SEVERITIES)), text(row["file"]),
                     integer(row["line"]), text(row["scenario"]), text(row["rule"]),
                     confidence(row["confidence"]), choice(row["route"], ROUTES),
                     boolean(row["needs_author_context"]), choice(row["status"], STATUSES))
        require(result.severity == "nit" or result.confidence >= MIN_CONFIDENCE,
                f"{result.severity} needs confidence >= {MIN_CONFIDENCE}")
        require(result.severity != "nit" or result.route == "defer", "nits never enter a fix loop; route them defer")
        return result


@dataclass(frozen=True)
class Findings:
    verdict: str
    base: str
    head: str
    findings: tuple[Finding, ...]

    @classmethod
    def parse(cls, value: Any) -> "Findings":
        row = obj(value, "schema_version verdict reviewed findings")
        version(row["schema_version"])
        reviewed = obj(row["reviewed"], "base head")
        items = []
        for index, item in enumerate(array(row["findings"])):
            try:
                items.append(Finding.parse(item))
            except Invalid as error:
                raise Invalid(f"findings[{index}]: {error}") from None
        result = cls(choice(row["verdict"], VERDICTS), sha(reviewed["base"]), sha(reviewed["head"]), tuple(items))
        unique(result.findings)
        blockers = [item.id for item in result.open() if item.severity != "nit"]
        require(result.verdict != "PASS" or not blockers, f"PASS with open blocking or important findings {blockers}")
        return result

    def open(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.status == "open")

    def counts(self) -> dict[str, int]:
        return {severity: sum(item.severity == severity for item in self.open()) for severity in SEVERITIES}

    def routes(self) -> dict[str, list[str]]:
        """Open finding ids by route; routes with no open finding are left out."""
        result: dict[str, list[str]] = {}
        for item in self.open():
            result.setdefault(item.route, []).append(item.id)
        return result


def read(path: Path) -> Findings:
    """Parse one file. Absent is an error: a review that wrote nothing did not find nothing."""
    require(path.is_file(), f"absent findings file is not zero findings: {path}")
    try:
        return Findings.parse(load(path))
    except ValueError as error:
        raise Invalid(f"{path}: {error}") from None


def read_all(paths: Iterable[Path]) -> list[tuple[Path, Findings]]:
    paths = list(paths)
    require(bool(paths), "no findings files named")
    require(len({path.resolve() for path in paths}) == len(paths), "a findings file is named twice")
    return [(path, read(path)) for path in paths]


def counts(paths: Iterable[Path]) -> dict[str, int]:
    """Open findings by severity, summed across files; fixed and refuted ones do not count."""
    total = dict.fromkeys(SEVERITIES, 0)
    for _, findings in read_all(paths):
        for severity, number in findings.counts().items():
            total[severity] += number
    return total
