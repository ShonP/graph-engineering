# Python and messaging skills sourcing: ruff, sqlalchemy, loguru, nats

**Mode:** tech (the GE spec 4.1 sourcing pass, one dedicated search per skill)
**For:** forge-platform plan 6, task 34 (branch `plan-6/python-skills`)
**Date:** 2026-09-22 (search), re-measured 2026-09-23 (the SHAs and counts below)

## Question

For each of the four competencies, is there a plugin-shaped upstream to depend on
(spec 4.2) or a licensed bare tree to vendor by SHA? If neither, the skill is
written from vendor docs plus what plan 6 measured, each claim carrying its source.

## Answer

None adopted. Two candidates were plugin-shaped or licensed and still rejected
with the lack named; the rest were missing, unlicensed or off-scope. All four
skills are written from pinned vendor sources plus the in-house ADRs
(`Equival-io/forge-platform` `docs/adr/`, a private repo). Each skill's header
lists its own pinned sources.

## Per skill

### ruff

| Candidate | Shape | Verdict |
| --- | --- | --- |
| [trailofbits/skills](https://github.com/trailofbits/skills) @ `32e34f817379`, `plugins/modern-python` 1.6.2 | plugin-shaped, so dependable under spec 4.2 | **Rejected.** `references/ruff-config.md` covers scaffolding and migration and recommends `select = ["ALL"]` against the house's narrow set, which ADR 0021 argues against. Nothing on banned-api symbols vs modules, `force-exclude`, or the per-file call the PostToolUse hook makes. Cited as prior art. |

### sqlalchemy

| Candidate | Shape | Verdict |
| --- | --- | --- |
| [manikosto/claude-code-python-stack](https://github.com/manikosto/claude-code-python-stack) @ `805c4d6a5783`, `skills/sqlalchemy-patterns/SKILL.md` (351 lines) | no `.claude-plugin/`, **no LICENSE file** | **Rejected.** It can be neither vendored (no licence, so no provenance) nor depended on (not plugin-shaped). The content is a generic 2.0 tutorial. Its `get_db_session` (lines 39-46) commits inside a FastAPI `yield` dependency, so the commit runs after the response has been sent, and it does not say so. **Correction:** the original pass said this dependency "rolls back without re-raising". Re-read at this SHA, it re-raises (line 46), so that reason is withdrawn. |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) @ `d9111a919d4f` | index | no SQLAlchemy entry |
| [anthropics/skills](https://github.com/anthropics/skills) @ `34040c9c5685` | skills repo | no database skill |

### loguru

GitHub repository search, 2026-09-23 (`api.github.com/search/repositories`):
`loguru skill` returned **0**, and `loguru agent skill` returned **0**.
VoltAgent/awesome-agent-skills and anthropics/skills (SHAs above) have no logging
entry. **Nothing found**, so the skill is written from vendor docs.

### nats

| Candidate | Shape | Verdict |
| --- | --- | --- |
| [kaustavdm/nats-skill](https://github.com/kaustavdm/nats-skill) @ `cbdda377b5a5` (last commit 2026-03-31) | MIT, no `.claude-plugin/` | **Rejected**, and the gap was measured (table below). A sound general NATS reference, but its generic advice to subscribe by subject alone (`js.PullSubscribe("orders.created", "order-worker")`, `skills/nats/SKILL.md:151`) is wrong under any real allow-list. With no stream named, the client looks the stream up through `$JS.API.STREAM.NAMES`. That is measured for nats-py; for nats.go it was read from `js.go` on `main` (`apiStreams = "STREAM.NAMES"`), not run. Nearly every rule here would contradict it, so a sibling house skill would repeat the whole file. Cited as prior art. |
| [lithqube/nats-jetstream-claude-skills](https://github.com/lithqube/nats-jetstream-claude-skills) @ `5001f06e38ff` (2026-09-16) | MIT, five skills, no `.claude-plugin/` | **Rejected.** It covers dedupe and inboxes. It has nothing on per-stream ack grants, the legacy vs modern consumer-create subjects, or `pull_subscribe_bind`, which are this cluster's authorization failures. |

**Gap measurement.** The table counts the lines in each repo's `*.md` files that
mention each fact this cluster's authorization model depends on. The original
pass wrote "six facts" but listed five counts. The five are the zero row for
kaustavdm below; `_INBOX` is the sixth fact, and it was never zero.

| fact | kaustavdm | lithqube |
| --- | --- | --- |
| `stream=` | 0 | 4 |
| `$JS.ACK` | 0 | 0 |
| `DURABLE.CREATE` | 0 | 0 |
| `duplicate_window` | 0 | 17 |
| `pull_subscribe_bind` | 0 | 0 |
| `_INBOX` | 4 | 16 |

Command: `grep -rE '<fact>' <clone> --include='*.md' | wc -l` on a `--depth 1`
clone at the SHA above.

## Prior-art note

```
Reuse candidates : trailofbits modern-python (plugin) -> reject, off-scope + select=ALL
                   manikosto sqlalchemy-patterns -> reject, unlicensed, not plugin-shaped
                   kaustavdm/nats-skill, lithqube nats skills -> reject, measured gap above
Looked at        : the five repos above (rung 3-4, SHAs pinned); vendor docs per skill header (rung 2)
Borrowed         : loguru's README InterceptHandler (0.7.3), SQLAlchemy's create_savepoint recipe
Rejected         : select = ["ALL"]; module-wide banned-api; subscribe-by-subject
Spiked           : text(":p::jsonb") binds nothing on 2.0.54 -> VALIDATED (_bindparams == [])
                   pull_subscribe_bind makes no API call -> VALIDATED (nats-py 2.16.0 client.py:625-689)
```
