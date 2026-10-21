#!/usr/bin/env bash

set -u

input="$(</dev/stdin)"
case "$input" in *git*) ;; *) exit 0 ;; esac
case "$input" in *commit*) ;; *) exit 0 ;; esac

[ -n "${CLAUDE_PROJECT_DIR:-}" ] || exit 0
[ -f "$CLAUDE_PROJECT_DIR/.claude/graph-profile.yaml" ] || exit 0
command -v uv >/dev/null 2>&1 || exit 0

src="${BASH_SOURCE[0]}"
case "$src" in
  */*) here="${src%/*}" ;;
  *) here=. ;;
esac
here="$(cd "$here" && pwd -P)" || exit 0

. "$here/python-runtime.sh" || exit 0
ge_python_runtime 2>/dev/null || exit 0

GE_HOOK_INPUT="$input" GE_PLUGIN_ROOT="${here%/hooks/scripts}" "$GE_PYTHON" - <<'PY'
import json
import os
import re
import shlex
import subprocess
import sys

PUNCT = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&"}
VALUED = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
PREFIX = "graph-engineering commit guard: "
REDIRECT_ENV = ("GIT_DIR=", "GIT_WORK_TREE=")
REDIRECT_OPTIONS = ("--git-dir", "--work-tree")


def segments(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    current = []
    for token in lexer:
        if token in PUNCT:
            yield current
            current = []
        else:
            current.append(token)
    yield current


def commit_dir(command, cwd):
    inner = [a or b for a, b in re.findall(r"`([^`]*)`|\$\(([^()]*)\)", command)]
    for part in [command] + inner:
        found = git_commit(part, cwd)
        if found:
            return found
    return None


def redirects_option(word):
    return word in REDIRECT_OPTIONS or word.startswith(tuple(f"{o}=" for o in REDIRECT_OPTIONS))


def git_commit(command, cwd):
    exported = False
    for words in segments(command):
        redirected = exported
        while words and "=" in words[0] and not words[0].startswith(("-", "=")):
            redirected = redirected or words[0].startswith(REDIRECT_ENV)
            words = words[1:]
        if words and words[0] == "export":
            exported = exported or any(w.startswith(REDIRECT_ENV) for w in words[1:])
            continue
        if len(words) > 1 and words[0] == "cd":
            cwd = os.path.join(cwd, os.path.expanduser(words[1]))
            continue
        if not words or os.path.basename(words[0]) != "git":
            continue
        target, rest = cwd, words[1:]
        while rest and rest[0].startswith("-"):
            redirected = redirected or redirects_option(rest[0])
            if rest[0] == "-C" and len(rest) > 1:
                target = os.path.join(target, os.path.expanduser(rest[1]))
            rest = rest[2:] if rest[0] in VALUED else rest[1:]
        if rest and rest[0] == "commit" and not redirected:
            return target
    return None


def run(argv, timeout):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def reason(findings):
    errors = [f for f in findings if f.get("level") == "error"]
    lines = []
    for f in errors[:3]:
        message, path = f.get("message", ""), f.get("path")
        head = message if not path or message.startswith(path) else f"{path}: {message}"
        lines.append(f"{head} - {f.get('fix', '')}")
    more = f"; {len(errors) - 3} more, see `graph-control hygiene --staged`" if len(errors) > 3 else ""
    return PREFIX + "; ".join(lines) + more


def main():
    try:
        payload = json.loads(os.environ["GE_HOOK_INPUT"])
        directory = commit_dir(payload["tool_input"]["command"], payload.get("cwd") or os.getcwd())
    except (ValueError, KeyError, TypeError, AttributeError):
        return
    if directory is None:
        return
    try:
        top = run(["git", "-C", directory, "rev-parse", "--show-toplevel"], 5)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"{PREFIX}hygiene did not run (error ({type(error).__name__})); commit allowed", file=sys.stderr)
        return
    root = top.stdout.strip()
    if top.returncode != 0 or not os.path.isfile(os.path.join(root, ".claude", "graph-profile.yaml")):
        return
    script = os.path.join(os.environ["GE_PLUGIN_ROOT"], "scripts", "graph-control.py")
    try:
        result = run(["uv", "run", "--quiet", "--script", script, "hygiene", "--root", root, "--staged"], 12)
        verdict = json.loads(result.stdout)
        status, findings = verdict["status"], verdict.get("findings", [])
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as error:
        status, findings = f"error ({type(error).__name__})", []
    if status == "FAIL":
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                    "permissionDecisionReason": reason(findings)}
        print(json.dumps({"hookSpecificOutput": decision}))
    elif status != "PASS":
        print(f"{PREFIX}hygiene did not run ({status}); commit allowed", file=sys.stderr)


main()
PY
exit 0
