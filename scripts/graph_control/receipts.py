"""Exact-candidate receipts, with independent actors and complete case coverage."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import array, choice, digest, file_hash, fingerprint, integer, obj, require, text, unique
from .identity import fresh, timestamp
from .run import Candidate, Run


@dataclass(frozen=True)
class CaseResult:
    id: str
    status: str

    @classmethod
    def parse(cls, value: Any) -> "CaseResult":
        row = obj(value, "id status")
        return cls(text(row["id"]), choice(row["status"], {"PASS", "FAIL", "SKIPPED", "BLOCKED"}))


@dataclass(frozen=True)
class Receipt:
    check_id: str
    actor: str
    model: str
    run_sha256: str
    candidate: Candidate
    argv: tuple[str, ...]
    cwd: str
    status: str
    exit_code: int
    executed: int
    skipped: int
    cases: tuple[CaseResult, ...]
    observed_at: str
    log_path: str
    log_sha256: str
    blocking: int
    important: int

    @classmethod
    def parse(cls, value: Any) -> "Receipt":
        row = obj(value, "check_id actor model run_sha256 candidate argv cwd status exit_code executed "
                  "skipped cases observed_at log_path log_sha256 findings")
        findings = obj(row["findings"], "blocking important")
        result = cls(text(row["check_id"]), text(row["actor"]), text(row["model"]),
                     digest(row["run_sha256"]), Candidate.parse(row["candidate"]),
                     tuple(text(x) for x in array(row["argv"])), text(row["cwd"]),
                     choice(row["status"], {"PASS", "FAIL", "BLOCKED"}), integer(row["exit_code"]),
                     integer(row["executed"]), integer(row["skipped"]),
                     tuple(CaseResult.parse(x) for x in array(row["cases"])),
                     text(row["observed_at"]), text(row["log_path"]), digest(row["log_sha256"]),
                     integer(findings["blocking"]), integer(findings["important"]))
        unique(result.cases)
        return result

    def validate(self, run: Run, run_data: Any, now: datetime, *, passing: bool) -> None:
        checks, actors = unique(run.checks), unique(run.actors)
        require(self.check_id in checks, "receipt references unknown check")
        require(self.actor in actors, "receipt references unknown actor")
        check, actor = checks[self.check_id], actors[self.actor]
        require(self.run_sha256 == fingerprint(run_data), "receipt belongs to a different run contract")
        require(self.candidate == run.candidate, "receipt candidate/source/runtime identity mismatch")
        require(self.argv == check.argv and self.cwd == check.cwd, "receipt command/cwd differs from required check")
        require(actor.role == check.capability, "receipt actor role differs from check capability")
        require(self.model == actor.resolved_model, "receipt response model differs from resolved dispatch")
        require({case.id for case in self.cases} == set(check.case_ids), "receipt case selection differs from required check")
        require(file_hash(Path(self.log_path)) == self.log_sha256, "receipt log missing or modified")
        fresh(self.observed_at, check.max_age_seconds, now)
        if passing:
            require(self.status == "PASS" and self.exit_code == 0, f"{check.id}: check did not pass")
            require(self.executed > 0 and self.skipped == 0, f"{check.id}: zero executed or skipped required checks")
            require(self.executed >= len(self.cases), f"{check.id}: executed count below required cases")
            require(all(case.status == "PASS" for case in self.cases), f"{check.id}: required case did not pass")
            require(self.blocking == 0 and self.important == 0, f"{check.id}: unresolved blocking/important findings")


def verify(run: Run, run_data: Any, items: list[Any], now: datetime) -> dict[str, Any]:
    latest: dict[str, Receipt] = {}
    for item in items:
        receipt = Receipt.parse(item)
        require(receipt.check_id in {check.id for check in run.checks}, "store contains unknown check")
        previous = latest.get(receipt.check_id)
        require(previous is None or timestamp(receipt.observed_at) > timestamp(previous.observed_at),
                "check receipt observations must increase; old evidence cannot overwrite a later result")
        latest[receipt.check_id] = receipt
    require(set(latest) == {check.id for check in run.checks}, "missing required check receipts")
    for receipt in latest.values():
        receipt.validate(run, run_data, now, passing=True)
    actors = {actor.id: actor for actor in run.actors}
    implementing = {actor.id for actor in run.actors if actor.role == "implement"}
    reviewers = {item.actor for item in latest.values() if actors[item.actor].role == "review"}
    qa = {item.actor for item in latest.values() if actors[item.actor].role == "qa"}
    require(not (reviewers & implementing or qa & implementing or reviewers & qa),
            "review and QA must be independent of implementation and each other")
    return {"checks": len(latest), "cases": sorted({case.id for item in latest.values() for case in item.cases}),
            "candidate": fingerprint(run_data["candidate"])}
