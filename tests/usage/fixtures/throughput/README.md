# Throughput fixtures (SYNTHETIC)

Everything under this folder is synthetic: invented ids, roles, times and
text. No row was copied from a real transcript. The only prompt and response
text is the sentinels `SENTINEL-PROMPT-thr7` and `SENTINEL-RESPONSE-thr9`,
which the tests assert never reach stdout or stderr.

The layout mirrors `tests/graph_control/fixtures/sessions/` (see its README
for the witnessed host layout): `project/` stands in for
`~/.claude/projects/<cwd slug>/`, subagents live at
`<session>/subagents/agent-<id>.jsonl` with an `agent-<id>.meta.json`, and
workflow agents one level down at `subagents/workflows/wf_<id>/`.

Measured with `GRAPH_MEASURE_AT=2026-09-30T00:00:00Z` and the default
`--days 14`, so the window is `[2026-09-16T00:00Z, 2026-09-30T00:00Z)`. An
agent is in the window when its last timestamp is. Git does not keep mtimes,
so every checked-out file is newer than the window start and passes the mtime
pre-filter; the test for that filter sets an old mtime itself.

| agent | where | agentType | description | timestamps (UTC) | active | wall interval |
| --- | --- | --- | --- | --- | --- | --- |
| `athr0001` | `synthetic-session` | `graph-engineering:implementer` | `0192f3ab:implement` | 09-29 10:00, 10:05, 10:10, 10:25, 10:30 | 15 min (the 15-min gap is idle) | 10:00-10:30 |
| `athr0002` | `synthetic-session` | `graph-engineering:implementer` | `0192f3ab:implement` | 09-29 10:00 then every 10 min to 11:30, then 11:35 | 95 min (10-min gaps count: 600 s is active) | 10:00-11:35 |
| `athr0003` | `synthetic-session` | `graph-engineering:implementer-simple` | `0192f3ac:implement` | 09-29 12:00 then every 10 min to 14:00 | 120 min | 12:00-14:00 |
| `athr0004` | `workflows/wf_thr01` | `graph-engineering:implementer` | `w1:T1` | 09-29 13:00, 13:10, 13:20, 13:30, 13:40 | 40 min | 13:00-13:40 |
| `athr0005` | `workflows/wf_thr01` | `graph-engineering:reviewer` | `w1:T1 review` | 09-29 13:10, 13:20, 13:30, 13:40 | 30 min | 13:10-13:40 |
| `athr0006` | `older-session` | `graph-engineering:implementer` | `0192f3ab:implement` | 09-01 10:00 then every 10 min to 11:40 | 100 min, OUT of window | 10:00-11:40 |

`athr0001` also carries one malformed line and one row without a timestamp;
both are skipped.

## Expected values (hand-computed, the oracle for AC-TP-1)

Populations use the role after the last `:` of `agentType`.

- `implementer-p90-active`: implementers in the window are 15, 95 and 40
  minutes. Nearest-rank p90 of n values is the value at rank `ceil(0.9 * n)`
  in ascending order: sorted `[15, 40, 95]`, rank `ceil(2.7) = 3`, so
  **`95.00`**. (Including the out-of-window `athr0006` would give 100;
  including the implementer-simple would give 120.)
- `implementer-over-90`: implementer or implementer-simple with active
  strictly over 90 minutes: `athr0002` (95) and `athr0003` (120), so **`2`**.
  (Including `athr0006` would give 3.)
- `workflow-concurrency`: per group, the time-weighted mean number of running
  agents over the time at least one runs, then the mean across groups with 2
  or more agents.
  - `wf_thr01`: `athr0004` 13:00-13:40 and `athr0005` 13:10-13:40. Agent
    minutes 40 + 30 = 70 over 40 busy minutes: 1.75.
  - graph run `0192f3ab` (outside a workflow): `athr0001` 10:00-10:30 and
    `athr0002` 10:00-11:35. Agent minutes 30 + 95 = 125 over 95 busy
    minutes: 1.315789...
  - graph run `0192f3ac`: one agent, skipped.
  - Mean: (1.75 + 1.315789) / 2 = 1.532894..., so **`1.53`**.

Empty window (`GRAPH_MEASURE_AT=2026-01-01T00:00:00Z`): p90 and concurrency
exit 1 with empty stdout; over-90 prints **`0`**.
