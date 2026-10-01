# research - a decision from evidence, no code

The playbook for a research question, a comparison or a decision, and its
product preset for "is this worth building"; the router in graph-ship step 1
picks it, and the engine reads this file only when the lane runs. A single
lookup stays in the `answer` lane. Nothing here writes code, so there is no
worktree, no plan, no qa and no merge. No `run.json` controls apply: the run
dir holds the ledger, the briefs, the leaf reports and the claims, all working
data. The deliverables (the report, the product concept, the spike report) go
to a durable repo path under the profile's `docsPath`, never only to `.graph/`,
which is git-ignored; the gate names them so the owner commits them. The engine
writes the brief and the report itself; only the leaves are dispatched.

## Presets

| Preset | Leaves | Use |
| --- | --- | --- |
| `quick` | 1 | one dimension, a narrow question |
| `standard` | 3 | a comparison or a decision over a few dimensions |
| `deep` | 6 | many independent dimensions, or a decision the owner gates on an irreversible choice; `verify` runs |
| `product` | 3, or 5 for a large appetite | "is this worth building"; see Product preset |

## Leaves

- **Fan-out.** Every leaf is dispatched at depth 1 in ONE message: the same
  agent type, only the brief varies (graph-ship step 3). No lead; leaves never
  have the Agent tool.
- **Budget.** Each leaf's dispatch states its tool budget of 10-20 calls (10
  for a narrow dimension, 20 for a broad one) and its `maxTurns` (the budget
  plus 5 for the report). A leaf that runs out reports `PARTIAL` with what
  remains; it is never extended.
- **Firewall.** Leaves get the brief only: `.graph/<run>/tasks/research-<k>.md`.
  No transcript, no owner context past the brief, no other leaf's output, so
  leaves do not anchor on each other and nothing private reaches a search query.
- **Claims to disk.** Each leaf appends to `.graph/<run>/research/claims.jsonl`
  one JSON line per claim, `{claim, source, pub_date, rung, confidence}` (`rung`
  on the `prior-art` ladder, `confidence` high, medium or low), every 5 items
  (sources read), with a shell `>>` append and never a rewrite: the leaves
  share the file, and a leaf that dies mid-way still leaves what it found.
- **Fetch blocklist.** Leaves never WebFetch login-walled domains (linkedin.com,
  x.com, twitter.com, facebook.com, instagram.com, tiktok.com): they return a
  login page, not the content. A claim that only such a page holds goes to the
  report's unverified list.

## Product preset

For the router's `product` lane. Slim by design: the owner kills weak ideas in
conversation, so there is no full product playbook. The two dispatches in step
3 and 4 run inside `report`, in order; on `--resume` each is skipped when its
artifact is already on disk.

1. **Intake** (in `brief`). The engine also writes `.graph/<run>/intake.md`:
   the idea in one paragraph, `intent: exploring|defined`, the appetite
   (`small|standard|large`), and a constraints probe: market, language,
   audience, budget, must-not, tools already used elsewhere. Each item comes
   from the ask, the profile, or `ownerAccess` when set; an unknown one becomes
   a reversible decision card with its default (graph-ship step 5), never a
   blocking question. `intent: defined` means the owner already chose what to
   build: the run closes and the ask goes straight to `feature`.
2. **Fan-out** (in `research`) at `standard`: tech with reuse first (existing
   skills, plugins, libraries and platform features before any build) plus a
   completeness checklist table with a status per row: design system, auth and
   session, DX/CI/runner, QA, observability, cost, skills per technology;
   competitor; ux when the idea has a user-facing surface. 5 leaves only when
   the appetite is large. The brief writes `deep: no - product preset: the
   spike tests the riskiest assumption`.
3. **Concept.** ONE `planner` dispatch writes the concept to
   `<docsPath>/research/<UTC date>-<slug>-concept.md` from the reports: the
   `product-spec` sections; 2-3 options, always including the smallest thing
   that could work and buy or do nothing; the riskiest
   assumption of each option; the checklist status; and one line
   `signal: already logged | instrumentation task`.
4. **Spike.** One `researcher-spike` on the recommended option's riskiest
   assumption, with the brief graph-ship step 1 gives the spike lane, its
   report at `<docsPath>/research/<UTC date>-spike-<slug>.md`; its verdict goes
   into the concept.
5. **Gate.** go / kill / clarify, with a 5-line summary: the idea, the
   recommended option, its riskiest assumption and the spike's verdict, the
   cost against the appetite, the signal line. kill closes the run with the
   reason in the ledger. clarify re-runs only the leaves the answer changes.
   go opens a feature run with the concept as its goal input: its
   `research-ux`, `research-tech` and `research-competitor` nodes are marked
   `skipped (product run <id>)` and point at this run's reports, while
   `research-impact` still runs, since this run never mapped the repo.

## node: brief
agent: engine
in: the owner's ask, the router's lane line, the profile
out: .graph/<run>/goal.md (the decision the research serves, the dimensions with one leaf each, the report's output format, the preset and its budget, the preferences probe - what the owner already uses, prefers or has ruled out, from the ask, the profile and `ownerAccess` when set, an unknown that would flip the decision becoming a reversible decision card - and the `deep: yes|no - <reason>` line that decides whether `verify` runs), one .graph/<run>/tasks/research-<k>.md per leaf (its dimension and mode, the output format, sources to prefer and avoid, the tool budget and `maxTurns`), .graph/<run>/intake.md in the product preset; no dispatch
gate: no
next: research

## node: research
agent: researcher
mode: per leaf, `tech`, `competitor` or `ux`, as its brief names
in: .graph/<run>/tasks/research-<k>.md only (the firewall)
out: .graph/<run>/research/<k>.md per leaf (the answer up top, evidence, open questions, then `ANSWERED`, `PARTIAL` or `BLOCKED`), appended lines in .graph/<run>/research/claims.jsonl
gate: no
next: verify

## node: verify
agent: researcher
when: deep
in: .graph/<run>/goal.md, .graph/<run>/research/claims.jsonl
out: .graph/<run>/research/verify.md (one refuter, cap 1: it tries to break the claims the decision rests on and marks each held, weakened or refuted, with its source)
gate: no
next: report

## node: report
agent: engine
in: .graph/<run>/goal.md, every .graph/<run>/research/*.md, .graph/<run>/research/claims.jsonl
out: <docsPath>/research/<UTC date>-<slug>.md (the profile's `docsPath`; the recommendation in one paragraph up top; the evidence per dimension with each source's rung; `## Evidence against`, never empty, naming what was searched when nothing turned up; `## Unverified`, each load-bearing claim no leaf reproduced with the spike that settles it, as a hypothesis and the smallest experiment), the ledger; in the product preset, <docsPath>/research/<UTC date>-<slug>-concept.md and the go / kill / clarify summary. The gate presents it and names each deliverable path, uncommitted, for the owner to commit: with nothing downstream, the owner's reply closes a research run
gate: yes
next: END
