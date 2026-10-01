"""Plug-in graph-control subcommands: one module per command, discovered at startup.

A command module defines NAME (str), HELP (str), add_arguments(parser) and
run(args) -> dict | Output. Modules whose name starts with `_` are private
helpers and are skipped. Import heavy dependencies inside `run`, so discovery
stays cheap for every other subcommand.
"""

import importlib
import pkgutil
from collections.abc import Iterator
from dataclasses import dataclass
from types import ModuleType

CONTRACT = {"NAME": str, "HELP": str, "add_arguments": callable, "run": callable}


@dataclass(frozen=True)
class Output:
    """Printed verbatim with its exit code, instead of the PASS JSON a dict result gets."""

    text: str
    exit_code: int = 0


def _satisfies(value: object, check: object) -> bool:
    return check(value) if check is callable else isinstance(value, check)


def iter_commands(package: str = __name__) -> Iterator[ModuleType]:
    """Yield every command module in `package`; a module breaking the contract raises TypeError."""
    root = importlib.import_module(package)
    for info in sorted(pkgutil.iter_modules(root.__path__), key=lambda item: item.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        missing = [name for name, check in CONTRACT.items()
                   if not _satisfies(getattr(module, name, None), check)]
        if missing:
            raise TypeError(f"command module {module.__name__} is missing or mistypes {missing}")
        yield module
