---
name: review-protocol
description: The severity scale, refutation rules and findings.json schema every reviewer and qa agent uses. Use whenever reporting review or qa findings, writing findings.json or qa-findings.json, or re-reviewing a fix round, so that severity and routing mean the same thing across reviewers and runs.
---

# Review protocol

## Severity

**Blocking.** Wrong behavior, data loss, a security or privacy hole, or a
violation of a stated house rule. Merging this ships a defect.

**Important.** Real, but survivable for one release: a missing test on new
logic, an error path that cannot report, a pattern that will be copied.

**Nit.** Style and preference. Nits never block and never enter a fix loop.

If you cannot say what breaks, it is a nit. "I would have written this
differently" is not a finding.

## Refute before surfacing

Drop any finding that:

- does not reproduce when you actually try it
- is pre-existing rather than introduced by this diff
- hits a documented skip-rule or intentional-duplication allowlist
- sits below confidence 0.8

Deduplicate what two lenses both raised.

Run things. A finding you reproduced outranks three you inferred from reading,
and inferred findings are where reviewer credibility goes to die.

## Test hygiene

A passing test is not evidence. Ask what the test would do if the code it names
were deleted. If the answer is "still pass", the test is decoration and the
coverage is imaginary.

Watch for a witness that a *different* guard also catches. It proves nothing
about the guard it is named for.

**Mutation receipts.** For each new guard or validation the implementer runs
`scripts/mutate-witness.sh` beside this skill and lists each receipt path. A
receipt is JSON (`file`, `lines`, `find`, `replace`, `killed`, `test_exit`,
`head`, `observed_at`, `test`): check that `lines` sit on the guard, `test` is
that guard's own test and `head` is on the reviewed branch. A surviving mutant
(`killed: false`) is Important, and so is a new guard or validation with no
receipt. Re-run a doubtful one from its fields: the script mutates only a
disposable worktree, never the shared one.

**Receipt coverage check (advisory).** Before `DONE` the implementer runs
`scripts/guard-receipts-check.py` from the plugin root (base SHA, receipts
directory, `--repo`): it lists added guard lines that no killed receipt covers.
It is a line heuristic that over-reports, so a listed line is a hint and never
a finding by itself, and you need not re-run it. Importance comes only from the
rule above: a real new guard or validation with no receipt.

## Always-on lenses

Security and privacy load as their own skills. Two more lenses apply with no
skill load, on every diff they touch:

- **Accessibility** (any UI diff): interactive elements have roles/labels and a
  keyboard path; focus is managed on navigation and dialogs; loading/empty/error
  states exist; reduced-motion is respected; contrast holds. A UI control a
  screen reader cannot name is Blocking, not a nit.
- **Implementer non-negotiables**: unvalidated boundary input, missing authz on
  a new endpoint, PII in logs/analytics/fixtures, secrets in code. These are
  stated implementation duties, so finding one is Blocking by definition.
- **Prior art** (every diff): the plan or PR carries a prior-art note per
  `prior-art` - reuse candidates weighed, sources with rungs, spikes with
  verdicts - or a written skip reason that fits the skip rule. Missing is
  Important. New code that re-implements an available, adequate library,
  skill or platform feature is Important, and the finding names the candidate.
- **UX evidence** (any UI diff): before/after screenshots or recordings exist
  under the profile's `uxEvidence.path` (or `.graph/<run>/assets/`) and the PR
  body embeds them, per `ux-evidence`. Missing on a diff a user can see is
  Blocking - it is a stated house rule. Evidence that contradicts the
  experience spec or the acceptance criteria is Important - including placement: an element on a different screen, region or hierarchy level than the spec decided, or a state the spec's table lists that the diff does not build, with no reason in the implementer's report. Look at the images;
  a folder that exists is not evidence that it shows the change.
- **Definition of done** (every diff): each `definition-of-done` cell the task's acceptance criteria name has its artifact in the diff or a one-line reason. Missing with no reason is Important (Blocking where the cell is itself a house rule, like `api-contract` or `ux-evidence`). A diff that fixes adjacent code no plan task covers is Important scope creep - implementers record those in `.graph/<run>/followups.md` instead (`impact-map`); name it as a follow-up.
- **API contract** (any API-surface diff): the collection under the profile's
  `api.collection` changes with the endpoint, and the PR body carries the
  `## API contract` section with the `bru run` command and pass line, per
  `api-contract`. Missing with no stated reason is Blocking - a stated house
  rule. A touched endpoint whose requests assert only status, or skip the auth
  case, is Important.

## Findings file

Write `findings.json` with the Write tool at the path your dispatch names; qa
writes `qa-findings.json` in the same shape. The engine counts and routes from
the file, never from prose. Check it from the repo with
`uv run <plugin root>/scripts/graph-control.py findings <path>` (the plugin root
is three directories above this skill; type it as a literal absolute path, never
through a shell variable) and rewrite the file until the command
exits 0; that means the file is valid, whatever its verdict.

```json
{
  "schema_version": 1,
  "verdict": "CHANGES-REQUESTED",
  "reviewed": {"base": "<base sha>", "head": "<head sha>"},
  "findings": [
    {
      "id": "F1",
      "severity": "blocking",
      "file": "src/orders/total.py",
      "line": 42,
      "scenario": "with qty 0 the total divides by zero and the endpoint returns 500",
      "rule": "review-protocol: Blocking, wrong behavior",
      "confidence": 0.9,
      "route": "patch",
      "needs_author_context": false,
      "status": "open"
    }
  ]
}
```

- `verdict`: `PASS` or `CHANGES-REQUESTED` (qa: `PASS` or `FAIL`). `PASS`
  exactly when no blocking or important finding is `open`.
- `reviewed`: the full shas (`git rev-parse`) of the base and head you read.
- `id`: `F1`, `F2`, ... unique in the file.
- `file`, `line`: repo-relative path and 1-based line; `0` when the finding is
  about the file as a whole (a missing test, a missing artifact).
- `scenario`: concrete inputs leading to a wrong result. Not "could be unsafe"
  but "with `next: []` this returns valid and the run never terminates".
- `rule`: the house rule, skill section or acceptance criterion it breaks.
- `confidence`: 0.0 to 1.0. Blocking and important need at least 0.8.
- `route`: see Routes. Nits always take `defer`.
- `needs_author_context`: `true` only when the fix needs knowledge the original
  author holds and the file and diff cannot carry.
- `status`: `open` when raised; only a re-review sets `fixed` or `refuted`.

Order findings blocking, important, nit. The human summary is one line, the
return line `PASS|CHANGES-REQUESTED blocking=<n> important=<m> findings=<path>`;
the file holds the detail. A missing file is `BLOCKED`: an absent findings file
is not zero findings.

## Routes

| `route` | Use when | Goes to |
| --- | --- | --- |
| `patch` | the code is wrong and the plan is right | the fix loop |
| `bad_plan` | the code does what the plan says and the plan is wrong | back to the plan node; the owner sees the plan diff before re-approving |
| `intent_gap` | the goal and criteria do not decide the behavior | a decision card for the owner |
| `defer` | real but outside this task, and every nit | `.graph/<run>/followups.md` |

## Re-review

A re-review reads the previous round's open blocking and important findings
plus `git diff <last reviewed head>..HEAD` (the fix commits), not the whole
branch, and applies every loaded lens to that diff. Its file sets
`reviewed.base` to the last reviewed head, carries each of those findings
forward under its id as `fixed`, `refuted` (the fixer's evidence shows it was
wrong, and you agree) or still `open`, and numbers new findings after the
highest prior id.

Each fix round is a fresh dispatch of the tier that built the task, reading
this file; only findings with `needs_author_context: true` go back to the
original author. Round 3 escalates one tier: a small task moves from
`implementer-simple` to `implementer` (opus), and a standard task gets a fresh
diagnosis on opus (`implementer` with `superpowers:systematic-debugging`
REQUIRED, a new hypothesis before any edit). At most 3 rounds; what survives
goes to the owner.

## Review depth

The profile's `instructionPaths` globs name the files that steer agents:
prompts, skills, agent definitions, rule packs, `CLAUDE.md`. They join the
built-in `agent-control` risk row (`.claude/**`, `CLAUDE.md`, `AGENTS.md`,
`.mcp.json`, `.github/**`), so a diff to one of them changes agent behavior,
gets a full review and always waits for the owner at merge. Any other
prose-only diff (docs, changelogs, READMEs) gets the `lint` depth: scripted
checks only, no LLM review. The engine runs `graph-control depth` before each
review leg; at `lint` no reviewer is dispatched: the engine runs the repo's
`lint.argv` from `.claude/graph-checks.json` on each changed file it lists,
writes `findings.json` itself and records the review receipt as its own actor.
A diff with code in it is never `lint`. Prose is decided by file type
(Markdown, reStructuredText, AsciiDoc, and named files such as README or
LICENSE), never by directory: a `conf.py` under `docs/`, a `requirements.txt`
or an MDX page is code.

## Panel

Depth `panel` (a risk row, a `review.seams` seam, or more than
`review.panel_lines` changed lines, per `graph-control depth`) is sized by the
diff:

- **Over ~2,000 changed lines or ~120k diff tokens** (`changed_lines` from
  `graph-control depth`; tokens estimated as `git diff <base> | wc -c` over
  4): the engine dispatches `reviewer-lead`. It slices the diff by plan task
  or package into at most 4 slices and runs one `reviewer` leaf per slice, all
  in one message, each on opus and each applying every REQUIRED lens in one
  read. Leaves write `.graph/<run>/review/<slice>.json`; the lead merges them
  into `findings.json`.
- **Below that**: one `reviewer` whose dispatch carries an explicit lens list.
  It reproduces every blocking finding before surfacing it.

The lead merges the leaf files with two rules:

- **Dedupe.** Two findings are one when they name the same `file`, their
  `line`s are within 3, and they cite the same `rule`. Keep the higher
  severity, then the higher confidence.
- **Refute.** The lead reproduces every blocking finding itself with the
  smallest targeted run and appends the command and its result to the
  `scenario`; a missing artifact reproduces as the check that shows it absent.
  A blocker that does not reproduce is dropped; one that shows less harm takes
  that severity. The leaf files stay as the record of what was dropped.

No per-lens leaves and no verifier leaves: each reads the same diff again. A
re-review is sized by its fix-commit diff, so it is usually one reviewer.

## Do not

Praise. Soften. Pad with observations to look thorough. Fix anything - you
report, someone else decides.
