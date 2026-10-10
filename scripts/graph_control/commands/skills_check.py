"""skills-check: a dispatch's REQUIRED skills against the child's `skills_loaded:` line.

Stdlib only. Exit 0 with PASS when every required skill is proven loaded; exit 1
with {"status": "SKILLS_MISSING", "missing": [...]} otherwise; exit 2 with
{"status": "BLOCKED", "reason": ...} when either list or the agent id is
malformed, so the engine can tell a skipped skill from a receipt it could not read.

Without `--agent-id` it reads nothing: the engine passes both lists. With it, it
reads that subagent's transcript, and a required name is proven only when it is
both claimed and observed there; SKILLS_MISSING then adds `unobserved`, the
claimed names the transcript does not show, and PASS adds `"observed":
"transcript"`. No transcript found falls back to the claim alone with
`"observed": "unavailable"`, so a harness that moves transcripts blocks nothing.
"""

import json
from argparse import ArgumentParser, Namespace
from typing import Any

from . import Output

NAME = "skills-check"
HELP = ("compare a dispatch's REQUIRED skills with the child's skills_loaded line; "
        "exit 1 naming the missing, 2 on a malformed line")


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--required", required=True, help="comma-separated REQUIRED skills the dispatch named")
    parser.add_argument("--loaded", required=True,
                        help="the child's skills_loaded value, comma-separated; empty when the line is absent")
    parser.add_argument("--agent-id", help="the child's agent id; checks the claim against its transcript")


def _print(status: str, exit_code: int, **fields: Any) -> Output:
    return Output(json.dumps({"status": status, **fields}, sort_keys=True) + "\n", exit_code)


def run(args: Namespace) -> dict[str, Any] | Output:
    from ..common import Invalid
    from ..skills import missing, names, unobserved
    from ..transcript import observed_skills, subagent_transcript

    try:
        required, loaded = names(args.required), names(args.loaded)
        transcript = None if args.agent_id is None else subagent_transcript(args.agent_id)
    except Invalid as error:
        return _print("BLOCKED", 2, reason=str(error))
    source = None if args.agent_id is None else "unavailable" if transcript is None else "transcript"
    proven, hidden = loaded, []
    if transcript is not None:
        observed = observed_skills(transcript)
        hidden = unobserved(tuple(name for name in required if name in loaded), observed)
        proven = tuple(name for name in loaded if name in observed)
    gone = missing(required, proven)
    if gone:
        detail = {"unobserved": hidden} if source == "transcript" else {"observed": source} if source else {}
        return _print("SKILLS_MISSING", 1, missing=gone, **detail)
    return {"required": len(required), "missing": [], **({"observed": source} if source else {})}
