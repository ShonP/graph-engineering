#!/usr/bin/env bash
#
# SessionStart hook: put the top of the project's handoff note, and the
# graph-engineering reply contract, in front of Claude at the start of a main
# session. Exits 0 always.
#
# Contract, from the doc fetched 2026-09-10 and rechecked 2026-09-30:
#   Hooks reference, "Hooks reference - Claude Code Docs"
#     https://code.claude.com/docs/en/hooks
#     - "SessionStart decision control": "Claude Code adds stdout it treats as
#       plain text to Claude's context", and "a hook that only loads context can
#       print to stdout directly without building JSON". The header line below
#       also keeps the output from starting with `{`, which is what would make
#       Claude Code parse it as JSON instead ("Exit code 0").
#     - "Exit code 2 behavior per event": SessionStart cannot block.
#     - "SessionStart input": `source` is startup, resume, clear, compact or
#       fork; `agent_type` is present when the session runs `claude --agent`.
#       hooks.json registers this hook for startup|clear|compact only; the
#       resume/fork check below is defence in depth beside that matcher.
#
# Prints, in order: the first 40 lines of docs/HANDOFF.md; a size warning when
# that file is over 150 lines; the three-line reply contract when the repo has
# .claude/graph-profile.yaml. No commands are run and nothing is written.

set -eu

# Drain stdin, on every path, so Claude Code's writer never sees EPIPE.
INPUT="$(cat)" || INPUT=""

# A resumed or forked session already has this text; an --agent session is not
# the owner's main session. Plain bash regex: no JSON parser is spawned.
SOURCE_RE='"source"[[:space:]]*:[[:space:]]*"(resume|fork)"'
AGENT_RE='"agent_type"[[:space:]]*:'
[[ $INPUT =~ $SOURCE_RE ]] && exit 0
[[ $INPUT =~ $AGENT_RE ]] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -n "$PROJECT_DIR" ] || exit 0
[ -d "$PROJECT_DIR" ] || exit 0

HANDOFF="$PROJECT_DIR/docs/HANDOFF.md"
if [ -f "$HANDOFF" ]; then
  printf 'docs/HANDOFF.md, first 40 lines (graph-engineering SessionStart hook):\n\n'
  head -n 40 -- "$HANDOFF" || exit 0
  # grep -c '' counts a last line with no trailing newline; it exits 1 on an
  # empty file, which is not an error here.
  LINES="$(grep -c '' -- "$HANDOFF" 2>/dev/null)" || LINES=0
  if [ "$LINES" -gt 150 ]; then
    printf '\ndocs/HANDOFF.md is %s lines; keep this index under 150 lines and move detail into linked files.\n' "$LINES"
  fi
fi

if [ -f "$PROJECT_DIR/.claude/graph-profile.yaml" ]; then
  [ -f "$HANDOFF" ] && printf '\n'
  printf '%s\n' \
    "graph-engineering reply contract: status and decision replies in at most 5 lines, plain words, echoing the owner's choices." \
    "Give one recommended action, say what you did and what you need, and no internal codes or SHAs unless asked." \
    "Deliverables go to a durable repo path, never only to chat or a scratchpad."
fi

exit 0
