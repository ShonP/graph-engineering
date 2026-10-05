"""Task contracts: dependency reachability, witnesses, ownership, cases and success signals."""

import re
from dataclasses import dataclass
from typing import Any

from .common import array, boolean, choice, obj, require, strings, text, unique, version
from .plan_budget import KEYS as BUDGET_KEYS, budget_fields, check_budget

NUMBER = r"-?[0-9]+(?:\.[0-9]+)?"
CONDITION = re.compile(rf"value (<=|>=|==|<|>) (?:({NUMBER})|baseline \* ({NUMBER})(?: \+ ({NUMBER}))?)")
SOURCES = {"prometheus", "sentry", "sql-readonly", "command"}
SIGNAL_KEYS = {"success_signals", "success_signals_reason"}
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def measure_key(goal: str) -> str:
    """The goal as scripts/measure_signals.py clean() keys it in measure.md, baseline.json and --due."""
    return " ".join(CONTROL.sub(" ", goal).replace("|", "/").split())


@dataclass(frozen=True)
class Signal:
    """A post-merge outcome the plan promises to watch. Stored as data; graph_control never runs it."""

    goal: str
    source: str
    command: tuple[str, ...]
    success_condition: str
    window_days: int

    @classmethod
    def parse(cls, value: Any) -> "Signal":
        row = obj(value, "goal source command success_condition window_days")
        command = tuple(text(item) for item in array(row["command"]))
        require(bool(command), "success signal command must be a nonempty argv")
        condition = row["success_condition"]
        require(isinstance(condition, str) and CONDITION.fullmatch(condition) is not None,
                f"success_condition must be 'value <op> <number>' or "
                f"'value <op> baseline * <number> [+ <number>]', got {condition!r}")
        days = row["window_days"]
        require(type(days) is int and 1 <= days <= 90, "window_days must be an integer 1-90")
        return cls(text(row["goal"]), choice(row["source"], SOURCES), command, condition, days)


@dataclass(frozen=True)
class Contract:
    id: str
    fields: tuple[str, ...]

    @classmethod
    def parse(cls, value: Any) -> "Contract":
        row = obj(value, "id fields")
        return cls(text(row["id"]), strings(row["fields"], empty=False))


@dataclass(frozen=True)
class Case:
    id: str
    given: str
    when: str
    then: str
    oracle: str
    runner: str
    requires_real: bool
    witness_kind: str
    witness_reference: str
    witness_claim: str
    transitions: tuple[str, ...]

    @classmethod
    def parse(cls, value: Any) -> "Case":
        row = obj(value, "id given when then oracle runner requires_real witness transitions")
        witness = obj(row["witness"], "kind reference claim")
        kind = choice(witness["kind"], {"real", "synthetic"})
        real = boolean(row["requires_real"])
        require(not real or kind == "real", f"case {row['id']}: real evidence required")
        return cls(*(text(row[key]) for key in ("id", "given", "when", "then", "oracle", "runner")),
                   real, kind, text(witness["reference"]), text(witness["claim"]),
                   strings(row["transitions"]))


@dataclass(frozen=True)
class Task:
    id: str
    depends_on: tuple[str, ...]
    produces: tuple[Contract, ...]
    consumes: tuple[Contract, ...]
    writable_paths: tuple[str, ...]
    case_ids: tuple[str, ...]
    stateful: bool
    estimate_min: int | None = None
    path_cap_reason: str | None = None
    proof: str | None = None

    @classmethod
    def parse(cls, value: Any, schema: int) -> "Task":
        row = obj(value, "id depends_on produces consumes writable_paths case_ids stateful", " ".join(BUDGET_KEYS))
        paths = strings(row["writable_paths"], empty=False)
        for path in paths:
            require(not path.startswith("/") and ".." not in path.split("/"),
                    "writable_paths must be relative, repo-qualified paths without '..'")
        task = cls(text(row["id"]), strings(row["depends_on"]),
                   tuple(Contract.parse(item) for item in array(row["produces"])),
                   tuple(Contract.parse(item) for item in array(row["consumes"])),
                   paths, strings(row["case_ids"], empty=False), boolean(row["stateful"]),
                   **budget_fields(row))
        check_budget(task, schema)
        return task


@dataclass(frozen=True)
class Plan:
    cases: tuple[Case, ...]
    tasks: tuple[Task, ...]
    external_contracts: tuple[Contract, ...]
    success_signals: tuple[Signal, ...] = ()
    success_signals_reason: str | None = None

    @classmethod
    def parse(cls, value: Any) -> "Plan":
        row = obj(value, "schema_version cases tasks external_contracts", " ".join(sorted(SIGNAL_KEYS)))
        schema = version(row["schema_version"], frozenset({1, 2}))
        require(schema == 2 or not row.keys() & SIGNAL_KEYS,
                "success_signals and success_signals_reason need schema_version 2")
        signals = tuple(Signal.parse(x) for x in array(row.get("success_signals", [])))
        empty = "success_signals" in row and not signals
        reason = text(row["success_signals_reason"]) if "success_signals_reason" in row else None
        require(not empty or reason is not None, "an empty success_signals list needs a success_signals_reason")
        require(reason is None or empty, "success_signals_reason only explains an empty success_signals list")
        keys = [measure_key(signal.goal) for signal in signals]
        for key in keys:
            require(keys.count(key) == 1, f"duplicate success signal goal {key!r}: each is measured by its goal")
        result = cls(tuple(Case.parse(x) for x in array(row["cases"])),
                     tuple(Task.parse(x, schema) for x in array(row["tasks"])),
                     tuple(Contract.parse(x) for x in array(row["external_contracts"])),
                     signals, reason)
        result.validate()
        return result

    def levels(self) -> list[list[str]]:
        """Topological levels from depends_on; tasks keep plan order within a level."""
        pending = unique(self.tasks)
        placed: set[str] = set()
        result: list[list[str]] = []
        while pending:
            ready = [key for key, task in pending.items() if set(task.depends_on) <= placed]
            require(bool(ready), "cyclic or unknown task dependency")
            result.append(ready)
            placed.update(ready)
            for key in ready:
                del pending[key]
        return result

    def validate(self) -> None:
        cases, tasks = unique(self.cases), unique(self.tasks)
        require(bool(cases) and bool(tasks), "plan needs cases and tasks")
        parents: dict[str, set[str]] = {}
        for level in self.levels():
            for key in level:
                parents[key] = set(tasks[key].depends_on)
                for dependency in tasks[key].depends_on:
                    parents[key].update(parents[dependency])
        providers = {key: (None, contract) for key, contract in unique(self.external_contracts).items()}
        for task in self.tasks:
            for contract in task.produces:
                require(contract.id not in providers, f"multiple producers for {contract.id}")
                providers[contract.id] = (task.id, contract)
        covered: set[str] = set()
        for task in self.tasks:
            require(set(task.case_ids) <= cases.keys(), f"{task.id}: unknown acceptance case")
            covered.update(task.case_ids)
            require(not task.stateful or any(len(cases[key].transitions) >= 2 for key in task.case_ids),
                    f"{task.id}: stateful task needs a composed transition case")
            unique(task.consumes)
            for consumed in task.consumes:
                require(consumed.id in providers, f"{task.id}: missing producer {consumed.id}")
                owner, produced = providers[consumed.id]
                require(owner is None or owner in parents[task.id],
                        f"{task.id}: missing dependency on producer {owner} of {consumed.id}")
                require(set(consumed.fields) <= set(produced.fields),
                        f"{task.id}: missing fields in {consumed.id}")
        require(covered == cases.keys(), "acceptance cases without an owning task")
        for index, task in enumerate(self.tasks):
            for other in self.tasks[index + 1:]:
                if other.id in parents[task.id] or task.id in parents[other.id]:
                    continue
                for left in task.writable_paths:
                    for right in other.writable_paths:
                        require(not overlaps(left, right),
                                f"unordered writable paths overlap: {task.id}:{left}, {other.id}:{right}")


def overlaps(left: str, right: str) -> bool:
    """Conservative static-prefix check; ambiguous globs need ordered ownership."""
    def prefix(path: str) -> str:
        return re.split(r"[*?\[{]", path, maxsplit=1)[0].rstrip("/")

    a, b = prefix(left), prefix(right)
    return (not a or not b or a == b or a.startswith(b + "/") or b.startswith(a + "/")
            or (bool(re.search(r"[*?\[{]", left)) and b.startswith(a))
            or (bool(re.search(r"[*?\[{]", right)) and a.startswith(b)))
