"""guard-agent: the PreToolUse(Agent|Task) policy hook body.

Reads the hook payload on stdin and the profile's `policy:` block, prints the
hook JSON (or nothing), and appends the override line to <root>/.graph/ledger.md.
Fail-open: an unreadable payload or profile gives no decision, so a broken
profile never blocks every dispatch in the repo.
"""

import json
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from . import Output

NAME = "guard-agent"
HELP = "PreToolUse(Agent|Task) policy check; prints hook JSON or nothing, fails open"


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--profile", required=True, type=Path, help="the repo's .claude/graph-profile.yaml")
    parser.add_argument("--root", required=True, type=Path, help="project root that holds .graph/ledger.md")


def run(args: Namespace) -> Output:
    from ..guard import decide
    from ..preflight import read_profile  # imports PyYAML

    try:
        payload = json.loads(sys.stdin.read())
        profile = read_profile(args.profile)
    except (ValueError, OSError):
        return Output("")
    decision = decide(payload, profile)
    if decision.ledger_line:
        ledger = args.root / ".graph" / "ledger.md"
        try:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a", encoding="utf-8") as handle:
                handle.write(decision.ledger_line + "\n")
        except OSError as error:
            print(f"guard-agent: override not logged to {ledger}: {error}", file=sys.stderr)
    return Output(json.dumps(decision.output) + "\n" if decision.output else "")
