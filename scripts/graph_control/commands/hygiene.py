"""hygiene: run the repo hygiene rules over one git scope and print their findings as JSON.

Prints {"status": "PASS"|"FAIL", "findings": [...]} (plus "run_end" with --run-end) and exits 1
when any finding is an error. Starts only git; never a configured project command.
"""

import json
import subprocess
from argparse import ArgumentParser, Namespace
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import Output
from ..common import Invalid, require

NAME = "hygiene"
HELP = "repo hygiene findings over the staged, base, tracked, run-end, sweep or text scope, as JSON"
RULES = "graph_control.hygiene"
INTEGRATIONS = ("pr", "push-main")


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path, help="the git repository to check")
    parser.add_argument("--profile", type=Path, help="default <root>/.claude/graph-profile.yaml; missing = defaults")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--staged", action="store_true", help="files in the index that differ from HEAD")
    scope.add_argument("--base", metavar="REV", help="files added or changed on HEAD since its merge base with REV")
    scope.add_argument("--tracked", action="store_true", help="every tracked file")
    scope.add_argument("--run-end", metavar="RUN_ID", help="the end-of-run checks for this run id")
    scope.add_argument("--sweep", action="store_true", help="the report-only sweep over every tracked file")
    scope.add_argument("--text", type=Path, metavar="FILE", help="check one text file, such as a PR body")
    parser.add_argument("--branch", help="the run branch, with --run-end")
    parser.add_argument("--integration", choices=INTEGRATIONS, help="default: the profile's integration, else pr")
    parser.add_argument("--only", action="append", default=[], metavar="ID", help="run only this rule; repeatable")


def _profile(args: Namespace) -> dict:
    import yaml

    path = args.profile or args.root / ".claude" / "graph-profile.yaml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise Invalid(f"profile {path} cannot be read: {error}") from error
    return data if isinstance(data, dict) else {}


def _toplevel(root: Path) -> Path:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    require(root.is_dir() and result.returncode == 0, f"not a git repository: {root}")
    return Path(result.stdout.strip())


def _mode(args: Namespace) -> str:
    for flag in ("staged", "base", "tracked", "run_end", "sweep", "text"):
        if getattr(args, flag) not in (None, False):
            return flag.replace("_", "-")
    raise Invalid("no scope flag given")


def run(args: Namespace, package: str = RULES, now: datetime | None = None) -> Output:
    from ..hygiene import Context, iter_rules
    from ..hygiene.config import parse
    from ..hygiene.scope import base, commit, staged, tracked

    profile = _profile(args)
    config = parse(profile)
    root = _toplevel(args.root)
    rules = list(iter_rules(package))
    known = [rule.ID for rule in rules]
    unknown = [ident for ident in args.only if ident not in known]
    require(not unknown, f"unknown rule id {', '.join(unknown)}; known: {', '.join(known) or 'none'}")
    require(args.text is None or args.text.is_file(), f"--text file not found: {args.text}")
    mode = _mode(args)
    listing = {"staged": lambda: staged(root), "base": lambda: base(root, args.base),
               "tracked": lambda: tracked(root), "sweep": lambda: tracked(root)}
    files = tuple(listing[mode]()) if mode in listing else ()
    integration = args.integration or profile.get("integration")
    ctx = Context(root=root, config=config, mode=mode, now=now or datetime.now(timezone.utc), files=files,
                  base=commit(root, args.base) if args.base else None, run_id=args.run_end, branch=args.branch,
                  integration=integration if integration in INTEGRATIONS else "pr", text=args.text)
    findings = [finding for rule in rules if mode in rule.MODES and (not args.only or rule.ID in args.only)
                for finding in rule.run(ctx)]
    errors = sum(finding.level == "error" for finding in findings)
    result = {"status": "FAIL" if errors else "PASS", "findings": [asdict(finding) for finding in findings]}
    if mode == "run-end":
        result["run_end"] = f"DIRTY ({errors})" if errors else "CLEAN"
    return Output(json.dumps(result, sort_keys=True) + "\n", 1 if errors else 0)
