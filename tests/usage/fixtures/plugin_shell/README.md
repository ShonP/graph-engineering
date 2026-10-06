# plugin_shell fixture (SYNTHETIC)

Synthetic Claude Code transcripts for `tests/usage/test_plugin_shell_calls.py`. No row
comes from a real session. Shapes follow the real ones (checked 2026-10-06): each line
is a JSON object with `type` and `timestamp`; a Bash call is an assistant row's
`message.content[]` block `{"type": "tool_use", "id", "name": "Bash", "input":
{"command"}}`; a subagent transcript sits under `subagents/` beside a `.meta.json`
holding `agentType`. Every command carries `SENTINEL-CMD-ps<n>` so the test can assert
none of it reaches the output.

Window: `GRAPH_MEASURE_AT=2026-09-30T00:00:00Z`, `--days 14`, so `[09-16, 09-30)`.

| File, row | Role | Shape | Counted at 14 days |
| --- | --- | --- | --- |
| aps0001 row 1 | graph-engineering:implementer | `$P/...wait-run.sh` variable-command | yes (1) |
| aps0001 row 2 | same | streamed copy of row 1, same `toolu_` id | no, deduplicated |
| aps0001 row 3 | same | `wait-run.sh -- bash -c '...'` shell-c | yes (2) |
| aps0001 row 4 | same | `wait-run.sh -- bash /abs/check.sh` (allowed, D1) | no, clean |
| aps0001 row 5 | same | not JSON | no, malformed (1) |
| aps0001 row 6 | same | variable-command on 09-05 | no, out of window; yes at 30 days |
| aps0001 row 7 | same | `Read` tool_use with a command-shaped input | no, not Bash |
| aps0001 row 8 | same | `user` row | no, not assistant |
| aps0001 row 9 | same | numeric timestamp | no, malformed (2) |
| aps0001 row 10 | same | at exactly the window end | no, end is exclusive |
| aps0002 row 1 | graph-engineering:reviewer | text block then `${P}/...mutate-witness.sh` | yes (3) |
| aps0003 row 1 | other-plugin:x | variable-command | no, other plugin |
| aps0004 row 1 | unknown (no meta.json) | variable-command | no, role unknown |
| session-a.jsonl | main thread | variable-command | no, main thread |

Expected: `3` at 14 days, `4` at 30 days, stderr `skipped 2 malformed lines`.
