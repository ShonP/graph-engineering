"""Load .claude/graph-checks.json version 1, the opt-in for the plugin hooks.

{"version": 1,
 "test":     {"argv": [...], "timeout_seconds": 1-600, default 600},
 "precheck": {"argv": [...], "timeout_seconds": 1-60,  default 10},
 "lint":     {"argv": [..., "{file}", ...], "extensions": [".py"],
              "timeout_seconds": 1-120, default 60}}

Every block is optional; unknown keys are rejected at every level so a typo
fails loudly instead of silently disabling a check. Stdlib only.
"""
from dataclasses import dataclass
import json
from pathlib import Path

FILE = '{file}'
# block -> (allowed keys, max timeout, default timeout)
BLOCKS = {
    'test': ({'argv', 'timeout_seconds'}, 600, 600),
    'precheck': ({'argv', 'timeout_seconds'}, 60, 10),
    'lint': ({'argv', 'extensions', 'timeout_seconds'}, 120, 60),
}


@dataclass(frozen=True)
class Check:
    argv: tuple[str, ...]
    timeout: int
    extensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    test: Check | None = None
    precheck: Check | None = None
    lint: Check | None = None


def _unknown(where: str, data: dict, allowed: set[str]) -> None:
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValueError(f'{where} has unknown key {extra[0]!r}')


def _argv(name: str, argv: object) -> tuple[str, ...]:
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or '\x00' in a for a in argv):
        raise ValueError(f'{name}.argv must be a nonempty array of nonempty strings without NUL')
    if name != 'lint' and any(FILE in a for a in argv):
        raise ValueError(f'{name}.argv must not contain {FILE}; only lint receives a file')
    if name == 'lint' and (argv.count(FILE) != 1 or any(FILE in a and a != FILE for a in argv)):
        raise ValueError(f'lint.argv must contain exactly one element equal to {FILE}')
    return tuple(argv)


def _extensions(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(
            not isinstance(e, str) or len(e) < 2 or not e.startswith('.') for e in value):
        raise ValueError('lint.extensions must be a nonempty array of suffixes starting with "." (for example ".py")')
    return tuple(value)


def _check(name: str, block: object) -> Check:
    allowed, most, default = BLOCKS[name]
    if not isinstance(block, dict):
        raise ValueError(f'{name} must be an object')
    _unknown(name, block, allowed)
    timeout = block.get('timeout_seconds', default)
    if type(timeout) is not int or not 1 <= timeout <= most:
        raise ValueError(f'{name}.timeout_seconds must be an integer from 1 to {most}')
    extensions = _extensions(block.get('extensions')) if name == 'lint' else ()
    return Check(_argv(name, block.get('argv')), timeout, extensions)


def load(path: Path) -> Config:
    """Parse and validate; raise ValueError with a one-line reason."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except ValueError as exc:
        raise ValueError(f'not valid JSON ({exc})') from None
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError('"version": 1 is required')
    _unknown('graph-checks.json', data, {'version', *BLOCKS})
    return Config(**{name: _check(name, data[name]) for name in BLOCKS if name in data})
