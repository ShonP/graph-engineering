# graph-engineering

A public Claude Code plugin. Every change serves the goals below; weigh them together and say which one a trade-off gives up.

## Goals

1. **Quality.** The goal is reached correctly: tested, reviewed, verified on the running surface. Never traded away for the others.
2. **Token cost.** Every line of an agent, skill, graph or command is paid on every dispatch that loads it. Fewer, sharper words; load on demand over preload; one home per rule.
3. **Wall time.** Parallel over serial, short critical paths, no idle polling, one full suite per task or round.
4. **Owner attention.** Gates only where a decision is real; decisions as cards with a default; at most 5-line status replies.
5. **Low friction.** A new consumer repo installs and runs in minutes; failures say what to do next.
6. **Generality.** Public repo: name stacks and tools, never a consumer product, person, private repo, account or internal metric (README "Genericity", `scripts/check-private-names.py`).
7. **Maintainability.** Small files, no dead code, reuse before build, delete before add.

## Rules that follow

- No code comments. Names and structure explain the code; `definition-of-done` holds the rule and `scripts/check-no-new-comments.py` enforces it.
- Prompts are code: a prompt change states its token delta (bytes before/after of each loaded file) and, when it changes behaviour, runs an eval before/after: the standing suite is `evals/` (`claude plugin eval . --ablation none --no-publish --allow-tools Agent Bash Write Edit Read`, on the base and the branch; each run is a metered session, so ask the owner first).
- Prefer an executable check (test, lint, `graph-control` subcommand, hook) over a prose rule.
- Measure, do not guess: `scripts/session_usage.py` for tokens per role, `scripts/throughput.py` for run time.
- Every change ships its tests; `bash scripts/run-all-tests.sh` is green before a PR.
- Changelog entries go under `[Unreleased]`; the owner bumps the version.
