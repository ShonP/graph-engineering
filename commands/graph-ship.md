---
description: Run a named playbook end to end - execute its nodes, honor its gates, dispatch each agent with the skills its task requires, and keep a resumable ledger.
argument-hint: "<goal> [--lane answer|direct|quick|full|investigate|research|product] [--graph feature|bug|infra|quick|research] [--auto-merge] [--resume <run-id>]"
---

# /graph-ship - the engine

Execute a playbook. **The engine is playbook-agnostic:** it reads `graphs/<name>.md` and runs whatever nodes it finds. It does not know what a feature is. That is what lets the same engine run `feature`, `bug` and `infra` without a branch per workflow here.

## Steps

1. **Load context, then route.** Read the candidate repository's `.claude/graph-profile.yaml` first; in a multi-repo workspace, its repo-relative runtime and API settings take precedence over workspace routing defaults. If absent, tell the owner to run `/graph-init` and stop. The router below runs inline in this turn: no skill load, no dispatch.

   **Where the rest lives.** This file holds only the router, so the lanes that open no run dir pay for nothing more. `<plugin-root>` is the installed plugin directory (its `installPath` in `~/.claude/plugins/installed_plugins.json`, or three directories above any of its skills' base directory). A lane that opens a run dir (`quick`, `full`, `research`, `product`) Reads `<plugin-root>/docs/engine/run.md` (steps 2-8 and 10) once per run, before step 2, and `<plugin-root>/docs/engine/land.md` (step 9) at its merge gate. `direct` and `investigate` Read their rules in `<plugin-root>/docs/engine/lanes.md`. Detail that only one playbook needs lives in that playbook's graph file, read only when it runs.

   **Due measures.** Before routing, when `.graph/` holds a merged run, run `python3 <plugin-root>/scripts/measure_signals.py --due .` from the repo root, then `python3 <plugin-root>/scripts/measure_signals.py .graph/<run>` for each run its line names: it measures only the long-window signals now due (step 9), deterministically, with no model turn; no line means nothing is due.

   **`--resume <run-id>`: no routing.** Read the playbook copy in `.graph/<run-id>/` and the ledger's `playbook:` line; the run finishes on the lane and graph it started with.

   **Split, then match risk.** An ask with several independent goals splits into parallel runs, one per goal, each routed on its own. Nothing is deferred silently: a goal not started now is named back to the owner with the reason. Then read the profile's `risk:` rows (`id`, `paths` globs, `keywords`). A row matches when one of its keywords appears in the goal text, or one of its path globs matches a file the goal names. One row is built in and always applies: `agent-control`, the agent's own control plane (`.claude/**`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json`, `.github/**` and the profile's `instructionPaths`). Any match forces at least `quick`. A profile with no `risk:` block matches only `agent-control`, and the ledger line says so.

   **Lanes.** Pick the lane by size and risk first; the ask type only picks the graph, except that an ask which starts with no code change (a question, a spike, research, a product idea, a signal) takes its own lane below. `--lane` and `--graph` are the owner's explicit choice and win over the pick; `--graph` still forces a playbook (its lane is `quick` for `graphs/quick.md`, `research` for `graphs/research.md`, `full` otherwise).
   - **answer** - a pure question or a current-state fact; no run dir. A current-state fact (a version, a price, a model, live data) needs a lookup, one WebFetch or one `researcher` dispatch, never memory. Name the source in the reply.
   - **direct** - a one-sentence diff, at most 2 files, no risk row: exactly one `implementer-simple`, no run dir, a run-it verification, and `ESCALATE` to `quick` when it outgrows that. Its rules are in `lanes.md`.
   - **quick** - a defined intent, at most 5 files, or any risk row on a small ask. Runs `graphs/quick.md` through steps 2 to 10 like any playbook.
   - **full** - anything larger: `graphs/feature.md`, `bug.md` or `infra.md`, picked by the triage below.
   - **spike** - a "can X do Y" question with a falsifiable answer: the researcher's `spike` mode, dispatched as one `graph-engineering:researcher-spike`, no run dir, its report at `<docsPath>/research/<UTC date>-spike-<slug>.md` (the profile's `docsPath`: a durable repo path). That agent runs without CLAUDE.md, so its brief carries the profile path, the REQUIRED skills, the rule packs and the project invariants (stack, paths, commands, what must not be touched).
   - **research** - a comparison, a decision, or a question that needs more than one source: `graphs/research.md` at its `quick`, `standard` or `deep` preset (1, 3 or 6 `researcher` leaves at depth 1), the report at `<docsPath>/research/<UTC date>-<slug>.md`. A single lookup stays in `answer`. It opens a run dir and ledger (step 2) for its briefs and claims but, like `answer`, `direct`, `spike` and the investigate pulse, is exempt from `run.json` controls.
   - **product** - "is this worth building": `graphs/research.md` with its product preset, which ends at a go / kill / clarify owner gate and, on go, hands off to the `feature` playbook with its research already done. An ask whose intent is already settled (`intent: defined` in the preset's intake) goes straight to `feature`.
   - **investigate** - a signal-driven ask ("look at the errors and fix what matters"); a lane, not a graph: a `researcher` in `signals` mode digests the profile's `pulse.command`, and each item the owner picks routes on its own. Its rules are in `lanes.md`.

   **Triage (`full` lane, no `--graph`).** Classify the goal and pick one playbook:
   - **bug** - the goal describes existing behaviour that is wrong: an error, crash, regression, wrong result, a failing check, a stack trace, an issue labelled bug.
   - **infra** - the goal's target is deployment configuration only: Helm charts or values, kustomize overlays, Argo CD applications, Kubernetes manifests, gateway or policy resources, secrets wiring, cluster add-ons - and no application code.
   - **feature** - everything else, including chores and refactors (the planner scales the plan down) and changes that touch both app code and infra (the impact map classifies the infra tasks).

   When two fit, prefer the narrower one only if the goal says so outright; otherwise `feature`. Carry the lane, the matched risk rows, the playbook and a one-line reason into step 2, which writes them as the first line of `ledger.md` (`playbook: bug - lane full, risk: none - "checkout returns 500 when the cart is empty" describes wrong behaviour`). Never ask before running: a question costs the owner's attention on every run. In `full` the triage line heads the plan gate's exhibit, so a wrong playbook is caught before any code and the owner reruns with `--graph`. In `direct` and `quick` the run-it verification is the catch: tests, the after-capture and the Bruno request run the change, and `ESCALATE` moves work up a lane. Every playbook gates before its first code-writing node (`quick`, feature, bug and infra all gate at `plan`; `research` writes no code and gates at `report`); a playbook added later must too, or the router must ask the owner before running it.
