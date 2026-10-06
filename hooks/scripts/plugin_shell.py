#!/usr/bin/env python3
"""Decide whether a Bash call runs a plugin script in a shape Claude Code cannot check.

Reads one PreToolUse payload on stdin and prints a deny decision or nothing, for
every caller (bypass-mode runs stop on Claude Code's inline-shell safety prompt).
Stdlib only; any parse problem means no decision (fail open). Plugin scripts only
(PLUGIN_SCRIPTS, by basename), two shapes:
- variable-command: the command word, after assignments and env/time/nohup/
  command/exec, starts with a variable (`$P/hooks/scripts/wait-run.sh`).
- shell-c: the command runs a plugin script (directly or via bash/sh) and its argv
  holds a shell word, then an option word with `c` in it (`-lc`, `-eo x -c`).
Words come from poll_loop.tokens (shlex, linear), reused over bashlex
(unmaintained) and tree-sitter (native wheel per call); shlex splits `$P/x` and
`${P}/x`, so they are rejoined here. Claude Code's rm-word and brace rules are not
repeated (still moving upstream, claude-code#99630). Known gap, shared with the
poll guard (followups F10): `$(...)`, backticks and heredoc bodies are not read.
"""

import json
import sys
from pathlib import Path

from poll_loop import COMMAND_PREFIXES, OPERATOR_CHARS, in_command_position, tokens

PLUGIN_SCRIPTS = frozenset({"wait-run.sh", "mutate-witness.sh", "lane-run.sh", "worktree-gc.sh"})
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
SCRIPT_RUNNERS = frozenset({"bash", "sh"})
WRAPPERS = frozenset({"env", "time", "nohup", "command", "exec"})
PLUGIN_ROOT = Path(__file__).resolve().parents[2]
REASON = (
    f"Call plugin scripts by their literal absolute path under {PLUGIN_ROOT}, never through "
    "a shell variable, and pass argv straight through instead of wrapping it in bash -c or "
    "sh -c; for a pipeline, set -o pipefail or an && chain, Write a script file under "
    ".graph/<run>/ and pass its path. Claude Code cannot check a $VAR command or a shell -c "
    "script, so it stops even bypass-mode runs on a safety prompt. "
    "To switch this guard off, set GRAPH_SHELL_GUARD=off."
)


def basename(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def is_operator(word: str) -> bool:
    return bool(word) and all(char in OPERATOR_CHARS for char in word)


def is_assignment(word: str) -> bool:
    name, equals, _ = word.partition("=")
    return bool(equals) and name.isidentifier()


def words(raw: list[str]):
    """Rejoin `$` expansions, collapse `$(...)` to one word, skip heredoc bodies."""
    i, heredoc, pending = 0, None, None
    while i < len(raw):
        word, nxt = raw[i], raw[i + 1] if i + 1 < len(raw) else None
        i += 1
        if heredoc is not None:
            if word == heredoc and raw[i - 2] == "\n":
                heredoc = None
            continue
        if word == "$" and nxt == "(":
            depth = 0
            while i < len(raw):
                if is_operator(raw[i]):
                    depth += raw[i].count("(") - raw[i].count(")")
                i += 1
                if depth <= 0:
                    break
            yield "$()"
        elif word == "$" and nxt == "{" and "}" in raw[i:i + 3]:
            close = raw.index("}", i)
            joined = "$" + "".join(raw[i:close + 1])
            i = close + 1
            if i < len(raw) and raw[i].startswith("/"):
                joined, i = joined + raw[i], i + 1
            yield joined
        elif word == "$" and nxt is not None and not is_operator(nxt):
            i += 1
            yield word + nxt
        else:
            if word == "\n" and pending is not None:
                heredoc, pending = pending, None
            elif word in ("<<", "<<-") and nxt is not None:
                delimiter = raw[i + 1] if nxt == "-" and i + 1 < len(raw) else nxt
                pending = delimiter.lstrip("-")
            yield word


def wraps_shell_c(argv: list[str]) -> bool:
    if basename(argv[0]) in SCRIPT_RUNNERS:
        script = next((word for word in argv[1:] if not word.startswith("-")), "")
        if basename(script) not in PLUGIN_SCRIPTS:
            return False
    elif basename(argv[0]) not in PLUGIN_SCRIPTS:
        return False
    for start, word in enumerate(argv[1:], 1):
        if basename(word) in SHELLS and runs_c(argv[start + 1:]):
            return True
    return False


def runs_c(options: list[str]) -> bool:
    takes_value = False
    for word in options:
        if takes_value:
            takes_value = False
        elif word[:1] in "-+" and len(word) > 1 and not word.startswith("--"):
            if "c" in word[1:]:
                return True
            takes_value = word.endswith("o")
        elif not word.startswith("--"):
            return False
    return False


def find_violation(command: str) -> str | None:
    try:
        stream = list(words(tokens(command)))
    except ValueError:
        return None
    argv: list[str] = []
    previous, wrapped, redirect = None, False, False
    for word in stream + [";"]:
        if redirect:
            redirect = False
        elif is_operator(word) and ("<" in word or ">" in word):
            redirect = True
        elif is_operator(word):
            if argv and wraps_shell_c(argv):
                return "shell-c"
            argv, previous, wrapped = [], word, False
        elif argv:
            argv.append(word)
        elif in_command_position(previous) or wrapped:
            previous = word
            wrapped = is_assignment(word) or word in WRAPPERS
            if wrapped or word in COMMAND_PREFIXES:
                continue
            if word.startswith("$") and basename(word) in PLUGIN_SCRIPTS:
                return "variable-command"
            argv = [word]
    return None


def decide(payload: dict) -> dict | None:
    if payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or find_violation(command) is None:
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
    except Exception:  # noqa: BLE001 - a hook fails open on any error
        return 0
    if decision is not None:
        print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
