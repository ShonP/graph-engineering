# Session fixtures (SYNTHETIC)

Everything under this folder is synthetic: invented ids, token counts, times
and text, shaped like the witness below. No row was copied from a real
transcript. The prompt and response text is the sentinels
`SENTINEL-PROMPT-7f3a` and `SENTINEL-RESPONSE-9c1e`, which the privacy tests
assert never reach any output or cache.

- `project/` stands in for `<config>/projects/<cwd slug>/`. Tests copy it
  under a temp `CLAUDE_CONFIG_DIR`, named by the slug of a temp repo.
- `ages.json` gives each transcript's last-activity age in minutes; tests
  apply it with `os.utime`, since git does not keep mtimes.
- `repo/graph/` is copied to `<repo>/.graph/` (the repo ignores `.graph/`).

| File | Role in the tests |
| --- | --- |
| `synthetic-session.jsonl` | current session (newest top-level jsonl): main thread, a streamed message split over 2 rows, one `<synthetic>` error row |
| `agent-asyn0001` | implementer, `0192f3ab:implement`, live 2 min, model from the transcript |
| `agent-asyn0002` | reviewer, `0192f3ab:review`, live but idle 12 min (`!`) |
| `agent-asyn0003` | qa, `0192f3ab:qa`, live 0 min, no assistant row yet: model from `meta.model` |
| `agent-asyn0004` | researcher, finished (`end_turn`), not live |
| `workflows/wf_synthetic/agent-asyn0005` | workflow agent, finished (`StructuredOutput`), not live, no run prefix |
| `agent-asyn0006` | implementer, 40 min without a final result: stale, not live, still costed |
| `older-session*` | decoy session with a fresh agent; must never show |

## Witness (read-only, 2026-09-30, Claude Code 2.1.286, macOS)

Read with scripts that print key names, types and counts only, never prompt or
response text, over `~/.claude/projects/-Users-<owner>/<session>/` (58 agent
transcripts, workflow-launched) plus a scan of 366 Agent-tool `agent-*.meta.json`
files from the last 10 days across all projects.

Layout
- Project dir slug: every character of the cwd outside `[A-Za-z0-9]` becomes
  `-` (seen: `/x/graph-engineering/.worktrees/ge-next` gives
  `-x-graph-engineering--worktrees-ge-next`; `/private/var/.../T/tmp.93o9` gives
  `...-T-tmp-93o9`). Not witnessed: the host's handling of very long paths.
- Main thread: `<slug>/<session>.jsonl`. Subagents:
  `<slug>/<session>/subagents/agent-<id>.jsonl` and `agent-<id>.meta.json`;
  workflow agents one level down at `subagents/workflows/<wf>/agent-<id>.*`.

`agent-<id>.meta.json` keys
- Always: `agentType` (for example `graph-engineering:implementer`),
  `description`, `requestShape` (`foreground` or `background`),
  `requestNonInteractive`, `spawnDepth`; `toolUseId` for Agent-tool agents.
- Sometimes: `model` (the requested alias such as `opus`, present only when
  the dispatch named one: 6 of 366 Agent-tool metas), `parentAgentId`, `stoppedByUser`,
  `workflowPhase`, `spawnedWithWorktree`, `worktreeBranch`, `worktreePath`.
- `description` carries the engine's `<run8>:<node>` prefix
  (`docs/engine/run.md` step 4, dispatch shape). None of the witnessed Agent-tool
  descriptions had it yet; workflow ones use `<wave>:<task>`.

Transcript rows (`*.jsonl`, one JSON object per line)
- Top-level keys used: `type` (`user`, `assistant`, `attachment`, `system`
  and other bookkeeping types), `timestamp` (ISO 8601 with `Z`), `message`.
  Also present, unused: `agentId`, `sessionId`, `isSidechain`, `uuid`,
  `parentUuid`, `requestId`, `cwd`, `gitBranch`, `version`.
- `message` on assistant rows: `id`, `model` (for example
  `claude-opus-5-5`, or `<synthetic>` for host-made error rows), `stop_reason`,
  `content` (blocks with `type`; tool calls carry `name`), `usage`.
- `usage`: `input_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`, `output_tokens`, `cache_creation`
  (`ephemeral_5m_input_tokens`, `ephemeral_1h_input_tokens`).
- Streaming: one API message spans consecutive assistant rows with the same
  `message.id` and the same `usage` (main thread: 189 rows, 91 ids, 0 with
  differing usage, 0 non-consecutive repeats). Count a message once.

Final result (what "no final result" means)
- Agent-tool agents end on an assistant row with `stop_reason: end_turn`.
- Workflow agents end on an assistant `tool_use` named `StructuredOutput`,
  followed by its `user` tool_result row.
- Everything else is still working: in the witness, the 8 transcripts written
  in the last 15 minutes ended on a `Bash` tool_use, a tool_result or an
  `attachment` row. Last activity is the transcript's mtime.
