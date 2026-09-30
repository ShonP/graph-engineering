"""JSON-only CLI. Never starts runtimes or executes configured project commands."""

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

from .commands import Output, iter_commands
from .common import Invalid, fingerprint, load
from .identity import snapshot
from .plan import Plan
from .preflight import preflight
from .receipts import Receipt, verify
from .run import Run
from .state import event, record, store_items, validate_attempts


def parser(modules: Iterable[ModuleType] | None = None) -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("validate-plan", "validate-attempts", "fingerprint"):
        commands.add_parser(name).add_argument("artifact", type=Path)
    snap = commands.add_parser("snapshot")
    snap.add_argument("root", type=Path)
    snap.add_argument("--repo", required=True)
    pre = commands.add_parser("preflight")
    pre.add_argument("run", type=Path)
    pre.add_argument("--profile", required=True, type=Path)
    pre.add_argument("--graph", required=True, type=Path)
    pre.add_argument("--readiness-only", action="store_true", help="inspect setup before runtime evidence exists")
    for name in ("record-receipt", "verify"):
        command = commands.add_parser(name)
        command.add_argument("run", type=Path)
        if name == "record-receipt":
            command.add_argument("receipt", type=Path)
        command.add_argument("--store", required=True, type=Path)
    evt = commands.add_parser("event")
    evt.add_argument("artifact", type=Path)
    evt.add_argument("--state", required=True, type=Path)
    for module in iter_commands() if modules is None else modules:
        if module.NAME in commands.choices:
            raise ValueError(f"command module {module.NAME} collides with an existing subcommand")
        command = commands.add_parser(module.NAME, help=module.HELP)
        module.add_arguments(command)
        command.set_defaults(graph_command=module)
    return root


def main(argv: list[str] | None = None, modules: Iterable[ModuleType] | None = None) -> int:
    args = parser(modules).parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        plugin = getattr(args, "graph_command", None)
        if plugin is not None:
            result = plugin.run(args)
            if isinstance(result, Output):
                sys.stdout.write(result.text)
                return result.exit_code
        elif args.command == "validate-plan":
            plan = Plan.parse(load(args.artifact))
            result = {"tasks": len(plan.tasks), "cases": len(plan.cases)}
        elif args.command == "validate-attempts":
            result = validate_attempts(load(args.artifact))
        elif args.command == "fingerprint":
            result = {"sha256": fingerprint(load(args.artifact))}
        elif args.command == "snapshot":
            result = {"source": asdict(snapshot(args.root, args.repo))}
        elif args.command == "event":
            result = event(args.state, load(args.artifact))
        else:
            data = load(args.run)
            run = Run.parse(data)
            profile = args.profile if args.command == "preflight" else Path(run.profile)
            graph = args.graph if args.command == "preflight" else Path(run.graph)
            result = preflight(run, profile, graph, now, readiness_only=getattr(args, "readiness_only", False))
            if args.command == "record-receipt":
                receipt_data = load(args.receipt)
                receipt = Receipt.parse(receipt_data)
                receipt.validate(run, data, now, passing=receipt.status == "PASS")
                result = {"recorded": record(args.store, receipt_data)}
            elif args.command == "verify":
                result = verify(run, data, store_items(args.store), now)
        print(json.dumps({"status": "PASS", **result}, sort_keys=True))
        return 0
    except (Invalid, ValueError, OSError, TimeoutError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
