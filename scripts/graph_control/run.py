"""Run and candidate schema shared by preflight and receipt validation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import array, boolean, choice, digest, integer, obj, require, strings, text, unique, version

CAPABILITIES = {"plan", "implement", "review", "qa", "verify"}
CHECK_KINDS = {"implement": "test", "review": "analysis", "qa": "public", "verify": "final"}


@dataclass(frozen=True)
class Source:
    repo: str
    root: str
    revision: str
    dirty_sha256: str

    @classmethod
    def parse(cls, value: Any) -> "Source":
        row = obj(value, "repo root revision dirty_sha256")
        revision = text(row["revision"])
        require(len(revision) in {40, 64} and all(c in "0123456789abcdef" for c in revision),
                "source revision must be a full Git object ID")
        root = text(row["root"])
        require(Path(root).is_absolute(), "source root must be absolute")
        return cls(text(row["repo"]), root, revision, digest(row["dirty_sha256"]))


@dataclass(frozen=True)
class Candidate:
    sources: tuple[Source, ...]
    runtime: str | None
    fixture_sha256: str
    schema_sha256: str

    @classmethod
    def parse(cls, value: Any) -> "Candidate":
        row = obj(value, "sources runtime fixture_sha256 schema_sha256")
        sources = tuple(Source.parse(x) for x in array(row["sources"]))
        require(bool(sources), "candidate needs at least one source")
        unique(sources, "repo")
        require(len({source.root for source in sources}) == len(sources), "duplicate source root")
        return cls(sources, None if row["runtime"] is None else digest(row["runtime"]),
                   digest(row["fixture_sha256"]), digest(row["schema_sha256"]))


@dataclass(frozen=True)
class Check:
    id: str
    capability: str
    kind: str
    argv: tuple[str, ...]
    cwd: str
    case_ids: tuple[str, ...]
    max_age_seconds: int

    @classmethod
    def parse(cls, value: Any) -> "Check":
        row = obj(value, "id capability kind argv cwd case_ids max_age_seconds")
        capability = choice(row["capability"], set(CHECK_KINDS))
        kind = text(row["kind"])
        require(kind == CHECK_KINDS[capability], "check kind does not match capability")
        argv = tuple(text(x) for x in array(row["argv"]))
        require(bool(argv), "check argv must not be empty")
        cases = strings(row["case_ids"], empty=capability not in {"qa", "verify"})
        if capability in {"qa", "verify"}:
            static = {"ruff", "mypy", "eslint", "prettier", "pyright", "tsc"}
            require(Path(argv[0]).name not in static, "static checks cannot satisfy public acceptance")
            require(not any(arg in {"lint", "format", "format:check", "typecheck"} for arg in argv[1:]),
                    "lint/typecheck cannot be remapped to QA or final verification")
        return cls(text(row["id"]), capability, kind, argv, text(row["cwd"]), cases,
                   integer(row["max_age_seconds"], 1))


@dataclass(frozen=True)
class Actor:
    id: str
    role: str
    requested_model: str
    resolved_model: str
    resolution_source: str
    skills: tuple[str, ...]

    @classmethod
    def parse(cls, value: Any) -> "Actor":
        row = obj(value, "id role requested_model resolved_model resolution_source skills")
        return cls(text(row["id"]), choice(row["role"], CAPABILITIES),
                   text(row["requested_model"]), text(row["resolved_model"]),
                   text(row["resolution_source"]), strings(row["skills"]))


@dataclass(frozen=True)
class Run:
    id: str
    plugin_version: str
    plan: str
    plan_sha256: str
    profile: str
    profile_sha256: str
    graph: str
    graph_sha256: str
    candidate: Candidate
    capability_nodes: dict[str, str]
    checks: tuple[Check, ...]
    actors: tuple[Actor, ...]
    available_models: tuple[str, ...]
    tools: tuple[str, ...]
    runtime_identity: str | None
    runtime_max_age_seconds: int
    requires_api: bool
    requires_design: bool

    @classmethod
    def parse(cls, value: Any) -> "Run":
        row = obj(value, "schema_version id plugin_version plan plan_sha256 profile profile_sha256 graph graph_sha256 "
                  "candidate capability_nodes checks actors "
                  "available_models tools runtime_identity runtime_max_age_seconds requires_api requires_design")
        version(row["schema_version"])
        nodes = obj(row["capability_nodes"], " ".join(CAPABILITIES))
        result = cls(text(row["id"]), text(row["plugin_version"]), text(row["plan"]), digest(row["plan_sha256"]),
                     text(row["profile"]), digest(row["profile_sha256"]),
                     text(row["graph"]), digest(row["graph_sha256"]),
                     Candidate.parse(row["candidate"]), {key: text(val) for key, val in nodes.items()},
                     tuple(Check.parse(x) for x in array(row["checks"])),
                     tuple(Actor.parse(x) for x in array(row["actors"])),
                     strings(row["available_models"], empty=False), strings(row["tools"]),
                     None if row["runtime_identity"] is None else text(row["runtime_identity"]),
                     integer(row["runtime_max_age_seconds"], 1),
                     boolean(row["requires_api"]), boolean(row["requires_design"]))
        result.validate()
        return result

    def validate(self) -> None:
        unique(self.checks)
        unique(self.actors)
        require({check.capability for check in self.checks} == set(CHECK_KINDS),
                "checks must cover implement, independent review, QA and final verify")
        require({actor.role for actor in self.actors} == CAPABILITIES,
                "actors must cover the full lifecycle")
        for actor in self.actors:
            require(actor.resolved_model in self.available_models,
                    f"{actor.id}: resolved model unavailable")
        for check in self.checks:
            roots = [Path(source.root) for source in self.candidate.sources]
            require(Path(check.cwd) in roots, f"{check.id}: cwd must be an exact candidate source root")
        require((self.candidate.runtime is None) == (self.runtime_identity is None),
                "runtime candidate fingerprint and runtime_identity must both be present or null")
