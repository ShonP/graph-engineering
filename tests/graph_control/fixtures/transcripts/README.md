# Subagent transcript fixtures (SYNTHETIC)

Every row here is synthetic: invented ids, paths and text, shaped like the
witness in `../sessions/README.md` and the run's spike (an invoked skill is an
assistant `tool_use` named `Skill` with `input.skill`; a preloaded skill is a
`<command-name>` tag in user content). Each row carries only the keys the
reader uses plus one unrelated key, `isSidechain`, which the reader ignores.

`projects/` stands in for `<config>/projects/`; tests copy it under a temp
`CLAUDE_CONFIG_DIR`.

| File | Role in the tests |
| --- | --- |
| `agent-aobserved.jsonl` | Skill call for `graph-engineering:prior-art`; preload tags for `graph-engineering:definition-of-done` (string content) and `graph-engineering:impact-map` (text block); `graph-engineering:bruno` only in assistant text, so never observed |
| `agent-aedges.jsonl` | an errored Skill call (`graph-engineering:bruno`), a Read of a repo-local `SKILL.md`, a malformed line, then a mixed-case Skill call that succeeds |
| `agent-aempty.jsonl` | empty file |
