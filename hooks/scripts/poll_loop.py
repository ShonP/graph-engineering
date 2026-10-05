#!/usr/bin/env python3
"""Decide whether an implementer subagent's Bash call is a shell loop that sleeps.

Reads one PreToolUse payload on stdin and prints a deny decision or nothing.
Stdlib only; any parse problem means no decision (fail open).

The command is tokenized with shlex rather than matched by one regex, so quoted
prose ("while waiting, do not sleep") is a single word and never a loop. Loop
keywords, `do` and `done` count only in command position, as the shell reads
them. shlex is a single-pass state machine, so the cost is linear in the input.
Known limitation: a heredoc body is tokenized as commands, so writing a script
that holds a sleeping loop through `cat <<EOF` is denied; the reason points at
the Write tool.
"""

import json
import shlex
import sys

IMPLEMENTER_TYPES = frozenset({
    "graph-engineering:implementer",
    "graph-engineering:implementer-simple",
    "implementer",
    "implementer-simple",
})
LOOP_KEYWORDS = frozenset({"until", "while", "for"})
COMMAND_PREFIXES = frozenset({"do", "then", "else", "elif", "if", "while", "until", "!", "{", "}", "time"})
OPERATOR_CHARS = frozenset("();<>|&\n")
REASON = (
    "Shell loops that sleep are blocked for implementer subagents. To wait for a long "
    "command, run it through hooks/scripts/wait-run.sh --log <absolute path> -- <argv> "
    "and call it again without argv to attach while it reports exit 75. To create a "
    "script file that contains a loop, use the Write tool instead of a heredoc."
)


def tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace = " \t\r"
    lexer.commenters = ""
    return list(lexer)


def in_command_position(previous: str | None) -> bool:
    if previous is None or previous in COMMAND_PREFIXES:
        return True
    return all(char in OPERATOR_CHARS for char in previous)


def has_sleep_loop(command: str) -> bool:
    open_loops: list[list[bool]] = []  # per loop: [saw_do, saw_sleep]
    previous = None
    for word in tokens(command):
        at_command = in_command_position(previous)
        previous = word
        if at_command and word in LOOP_KEYWORDS:
            open_loops.append([False, False])
        elif not open_loops:
            continue
        elif at_command and word == "do":
            open_loops[-1][0] = True
        elif at_command and word == "done":
            saw_do, saw_sleep = open_loops.pop()
            if saw_do and saw_sleep:
                return True
        elif word.rsplit("/", 1)[-1] == "sleep":
            for loop in open_loops:
                loop[1] = True
    return any(saw_do and saw_sleep for saw_do, saw_sleep in open_loops)


def decide(payload: dict) -> dict | None:
    if payload.get("tool_name") != "Bash" or not payload.get("agent_id"):
        return None
    if payload.get("agent_type") not in IMPLEMENTER_TYPES:
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return None
    try:
        looping = has_sleep_loop(command)
    except ValueError:
        return None
    if not looping:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON,
    }}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        decision = decide(payload) if isinstance(payload, dict) else None
    except Exception:
        return 0
    if decision is not None:
        print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
