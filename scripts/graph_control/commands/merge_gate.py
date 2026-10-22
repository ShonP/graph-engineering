from argparse import ArgumentParser, Namespace
from pathlib import Path, PurePosixPath
from typing import Any

NAME = "merge-gate"
HELP = "whether a green run merges without the owner, with the profile read at --base, never the branch"
PROFILE_PATH = ".claude/graph-profile.yaml"
VERDICTS = ("PASS", "FAIL", "INCOMPLETE")
PROFILE_LIMIT = 1024 * 1024


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("run", type=Path, help="the run directory, .graph/<run>")
    parser.add_argument("--root", required=True, type=Path, help="the run worktree")
    parser.add_argument("--base", required=True, help="the run base revision; the profile is read from it")
    parser.add_argument("--auto-merge", action="store_true", help="the run was started with --auto-merge")
    parser.add_argument("--profile-path", default=PROFILE_PATH, help="repo-relative profile path at the base")


def _profile_path(value: str) -> str:
    from ..common import require

    path = PurePosixPath(value)
    require(bool(value) and not value.startswith("-") and not path.is_absolute() and ".." not in path.parts,
            f"--profile-path must be a repo-relative path inside the tree, not {value!r}")
    return str(path)


def base_profile(root: Path, commit: str, path: str) -> dict[str, Any]:
    import yaml

    from ..common import Invalid, require
    from ..identity import git
    from ..preflight import UniqueLoader

    entry = git(root, "ls-tree", "-z", "--full-tree", commit, "--", path).decode().rstrip("\0")
    if not entry:
        return {}
    kind, sha = entry.split("\t", 1)[0].split(" ")[1:3]
    require(kind == "blob", f"{commit}:{path} is a {kind}, not a profile file")
    raw = git(root, "cat-file", "blob", sha)
    require(len(raw) <= PROFILE_LIMIT, "profile exceeds 1 MiB")
    try:
        value = yaml.load(raw.decode(), Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise Invalid(f"invalid profile YAML at {commit}:{path}: {error}") from error
    require(isinstance(value, dict), "profile must be a YAML mapping")
    return value


def qa_verdict(path: Path) -> str:
    if not path.is_file():
        return ""
    import re

    pattern = re.compile(rf"({'|'.join(VERDICTS)})\b")
    matches = [pattern.match(line.strip()) for line in path.read_text().splitlines()]
    return next((match.group(1) for match in reversed(matches) if match), "")


def verified(run_dir: Path) -> tuple[bool, str]:
    from datetime import datetime, timezone

    from ..common import Invalid, load
    from ..receipts import verify
    from ..run import Run
    from ..state import store_items

    run_path, store = run_dir / "run.json", run_dir / "receipts.json"
    missing = [str(path) for path in (run_path, store) if not path.is_file()]
    if missing:
        return False, f"missing {', '.join(missing)}"
    try:
        data = load(run_path)
        verify(Run.parse(data), data, store_items(store), datetime.now(timezone.utc))
    except Invalid as error:
        return False, str(error)
    return True, ""


def run(args: Namespace) -> dict[str, Any]:
    from ..common import load, require
    from ..depth import DIFF, _commit, _numstat
    from ..depth import decide as depth
    from ..findings import counts
    from ..identity import git
    from ..merge_rule import Inputs, decide
    from ..review_files import review_files

    path = _profile_path(args.profile_path)
    commit = _commit(args.root, args.base)
    profile = base_profile(args.root, commit, path)
    plan = load(args.run / "plan.json")
    risk_rows = depth(args.root, commit, profile, plan)["risk_rows"]
    changed = _numstat(git(args.root, *DIFF, "--numstat", "-z", commit, "--"))[2]
    files = [Path(item) for item in review_files(args.run, profile, plan)["latest"]] + [args.run / "qa-findings.json"]
    for item in files:
        require(item.is_file(), f"missing findings file: {item}")
    severity = counts(files)
    ok, why = verified(args.run)
    decision = decide(profile, Inputs(tuple(risk_rows), tuple(changed), severity["blocking"], severity["important"],
                                      qa_verdict(args.run / "qa.md"), ok, args.auto_merge))
    reasons = [f"{reason}: {why}" if why and reason.startswith("failed: verify") else reason
               for reason in decision.reasons]
    return {"open": decision.open, "mode": decision.mode, "reasons": reasons, "risk_rows": list(risk_rows),
            "profile_source": f"{commit}:{path}"}
