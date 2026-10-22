"""Validate a repo's access matrix; with --live, run each row's check.

Usage: access-doctor.py [--live] [matrix]    (default: docs/ops/access.yaml)
Exit 0 when every row is valid (and, with --live, every check passes), 1 otherwise.
"""

import argparse
import shlex
import subprocess
import sys

import yaml

FIELDS = ("id", "what", "holds", "role", "who", "owner_only", "check", "request", "pipeline", "status")
STATUSES = ("active", "requested", "blocked")
CHECK_TIMEOUT_SECONDS = 30


def validate(rows):
    problems = []
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"row {index}: not a mapping")
            continue
        name = row.get("id") or f"row {index}"
        for field in FIELDS:
            if field not in row:
                problems.append(f"{name}: missing {field}")
        if row.get("id") in seen:
            problems.append(f"{name}: duplicate id")
        seen.add(row.get("id"))
        if not isinstance(row.get("owner_only"), bool):
            problems.append(f"{name}: owner_only must be true or false")
        if "paid" in row and not isinstance(row["paid"], bool):
            problems.append(f"{name}: paid must be true or false")
        elif row.get("paid") and not row.get("spend_cap"):
            problems.append(f"{name}: paid row needs spend_cap")
        if row.get("status") not in STATUSES:
            problems.append(f"{name}: status must be one of {', '.join(STATUSES)}")
        if not row.get("owner_only"):
            for field in ("check", "request", "who"):
                if not row.get(field):
                    problems.append(f"{name}: {field} is empty and the row is not owner_only")
    return problems


def probe(row):
    command = row.get("check")
    if not command or row.get("status") != "active":
        return None
    try:
        done = subprocess.run(
            shlex.split(command), capture_output=True, stdin=subprocess.DEVNULL, timeout=CHECK_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"{row['id']}: check did not run ({type(error).__name__})"
    if done.returncode != 0:
        return f"{row['id']}: check exited {done.returncode}; request: {row.get('request')}"
    return None


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix", nargs="?", default="docs/ops/access.yaml")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.matrix, encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as error:
        print(f"{args.matrix}: cannot read matrix ({type(error).__name__})", file=sys.stderr)
        return 1
    rows = document.get("rows") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        print(f"{args.matrix}: no rows list", file=sys.stderr)
        return 1
    problems = validate(rows)
    if args.live and not problems:
        problems = [failure for failure in map(probe, rows) if failure]
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"access-doctor: {len(rows)} rows, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
