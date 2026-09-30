"""Strict input primitives and artifact identity."""

import hashlib
import json
from pathlib import Path
from typing import Any


class Invalid(ValueError):
    """An artifact cannot prove its claimed capability."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def obj(value: Any, required: str, optional: str = "") -> dict[str, Any]:
    require(isinstance(value, dict), "expected an object")
    keys = set(required.split())
    require(not keys - value.keys(), f"missing fields: {sorted(keys - value.keys())}")
    extra = value.keys() - keys - set(optional.split())
    require(not extra, f"unknown fields: {sorted(extra)}")
    return value


def text(value: Any) -> str:
    require(isinstance(value, str) and bool(value.strip()), "expected nonempty text")
    return value


def strings(value: Any, *, empty: bool = True) -> tuple[str, ...]:
    require(isinstance(value, list), "expected an array")
    result = tuple(text(item) for item in value)
    require(len(result) == len(set(result)), "duplicate array values")
    require(empty or bool(result), "array must not be empty")
    return result


def array(value: Any) -> list[Any]:
    require(isinstance(value, list), "expected an array")
    return value


def integer(value: Any, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, f"expected integer >= {minimum}")
    return value


def boolean(value: Any) -> bool:
    require(type(value) is bool, "expected boolean")
    return value


def choice(value: Any, options: set[str]) -> str:
    require(isinstance(value, str) and value in options, f"expected one of {sorted(options)}")
    return value


def digest(value: Any) -> str:
    result = text(value)
    require(len(result) == 64 and all(c in "0123456789abcdef" for c in result),
            "expected lowercase SHA-256")
    return result


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(items: tuple[Any, ...], field: str = "id") -> dict[str, Any]:
    result = {getattr(item, field): item for item in items}
    require(len(result) == len(items), f"duplicate {field}")
    return result


def load(path: Path) -> Any:
    require(path.stat().st_size <= 8 * 1024 * 1024, "artifact exceeds 8 MiB")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_number(value: str) -> None:
        raise Invalid(f"invalid number {value}")

    return json.loads(path.read_text(), object_pairs_hook=no_duplicates, parse_constant=invalid_number)


def version(value: Any, allowed: frozenset[int] = frozenset({1})) -> int:
    require(type(value) is int and value in allowed,
            f"schema_version must be {' or '.join(str(item) for item in sorted(allowed))}")
    return value
