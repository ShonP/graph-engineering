# Deterministic run controls

Use `uv run scripts/graph-control.py …` from the plugin checkout. The PEP 723 entry point requires Python ≥3.11 and pins PyYAML 6.0.2. The controls inspect files, executable availability and Git state. They **never execute configured project commands, start a runtime, call a model or make network requests**. `uv` may install its pinned runtime/dependency when first invoked; provision it before offline use.

Successful commands return JSON `{"status":"PASS",…}` and exit 0. Invalid, missing, stale or incomplete evidence returns `{"status":"BLOCKED","reason":"…"}` and exit 1. Parser errors use argparse's exit 2. There is no N/A/skip route for required checks. Every check declared in the run is required; keep optional diagnostics outside this gate manifest.

```
uv run scripts/graph-control.py validate-plan /absolute/run/plan.json
uv run scripts/graph-control.py snapshot /absolute/candidate --repo backend
uv run scripts/graph-control.py fingerprint /absolute/run/run.json
uv run scripts/graph-control.py preflight /absolute/run/run.json --profile /absolute/profile.yaml --graph /absolute/run/graph.md
uv run scripts/graph-control.py record-receipt /absolute/run/run.json /absolute/run/receipt.json --store /absolute/run/receipts.json
uv run scripts/graph-control.py verify /absolute/run/run.json --store /absolute/run/receipts.json
uv run scripts/graph-control.py validate-attempts /absolute/run/attempts.json
uv run scripts/graph-control.py event /absolute/run/event.json --state /absolute/run/events.json
```

`preflight --readiness-only` is for the stage before implementation/runtime startup: it checks configuration, plan, tools, models and baseline source, but does not require the runtime observation file yet. Its `phase: readiness` result cannot authorize completion. Use a planned runtime artifact path and placeholder fingerprint until the runner reports actual identity, then refresh the candidate manifest. Recording and verification never accept readiness-only mode.

`fingerprint` hashes canonical JSON (sorted keys, compact separators). File hash fields instead use SHA-256 of the exact file bytes. `snapshot` prints `source` suitable for a candidate. Put mutable run artifacts outside candidate source roots, or in a deliberately ignored run directory; otherwise adding a receipt correctly changes the dirty source fingerprint. Record source identity **after** implementation and before checks. After changing source, update the manifest and rerun affected checks; do not relabel old receipts. `record-receipt` and `verify` rerun read-only preflight from the manifest's bound profile/playbook paths. A changed plan, profile or graph invalidates the candidate contract.

## Plan schema (version 1)

All listed fields are required. Unknown/duplicate keys and duplicate IDs are rejected. Arrays below may be empty unless the example/comment says otherwise.

```json
{
  "schema_version": 1,
  "external_contracts": [{"id": "RunDetail", "fields": ["fan_out_planned"]}],
  "cases": [{
    "id": "AC-FANOUT", "given": "two known downstream candidates",
    "when": "the first starts", "then": "header shows Product 1 of 2",
    "oracle": "visible total equals the supplied candidate count", "runner": "playwright",
    "requires_real": false,
    "witness": {"kind": "synthetic", "reference": "tests/fixtures/fanout.json", "claim": "two candidates"},
    "transitions": ["not_started", "running"]
  }],
  "tasks": [{
    "id": "FE3", "depends_on": [], "produces": [{"id": "stage-renderer", "fields": ["deriveStageStatus"]}],
    "consumes": [{"id": "RunDetail", "fields": ["fan_out_planned"]}],
    "writable_paths": ["frontend/src/stages/**"], "case_ids": ["AC-FANOUT"], "stateful": true
  }, {
    "id": "FE4", "depends_on": ["FE3"], "produces": [],
    "consumes": [{"id": "stage-renderer", "fields": ["deriveStageStatus"]}],
    "writable_paths": ["frontend/src/downstream/**"], "case_ids": ["AC-FANOUT"], "stateful": true
  }]
}
```

Every case has an owning task. Every task has at least one case and writable path. Stateful tasks need a case with at least two named transition events/states. Real-world claims set `requires_real: true`; synthetic witnesses cannot satisfy them. Witness kinds are exactly `real` or `synthetic`. A reviewer must verify the witness's **truth and relevance**: the parser cannot discover that a supposedly real Solr fixture was invented, or that a range belongs to another product.

Contract producers are unique. A consumed contract's producer must be an ancestor dependency; all consumed fields must exist. External contracts must already exist and have evidence in the case/research artifacts. Dependencies reject cycles/unknown tasks. Unordered tasks cannot claim overlapping writable paths. Glob overlap uses a conservative static-prefix check: ambiguous ownership must be narrowed or serialized. Paths are repo-qualified relative paths, without `..`.

## Run schema (version 1)

```json
{
  "schema_version": 1, "id": "run-id", "plugin_version": "<executing plugin version>",
  "plan": "/absolute/run/plan.json", "plan_sha256": "<file SHA256>",
  "profile": "/absolute/project/.claude/graph-profile.yaml", "profile_sha256": "<file SHA256>",
  "graph": "/absolute/run/graph.md", "graph_sha256": "<file SHA256>",
  "candidate": {
    "sources": [{"repo": "backend", "root": "/absolute/candidate", "revision": "<full Git object ID>", "dirty_sha256": "<snapshot value>"}],
    "runtime": null, "fixture_sha256": "<fixture-set SHA256>", "schema_sha256": "<schema SHA256>"
  },
  "capability_nodes": {"plan": "plan", "implement": "implement", "review": "review", "qa": "qa", "verify": "qa"},
  "checks": [{"id": "unit", "capability": "implement", "kind": "test", "argv": ["uv", "run", "pytest"],
              "cwd": "/absolute/candidate", "case_ids": ["AC-FANOUT"], "max_age_seconds": 3600}],
  "actors": [{"id": "worker-session-id", "role": "implement", "requested_model": "sonnet",
              "resolved_model": "<concrete available host model>", "resolution_source": "<host capability evidence>", "skills": []}],
  "available_models": ["<concrete available host model>"], "tools": ["git", "uv"],
  "runtime_identity": null, "runtime_max_age_seconds": 120,
  "requires_api": false, "requires_design": false
}
```

This abbreviated example intentionally shows only one check/actor; a valid run needs checks covering **implement, review, QA, verify** and actors covering **plan, implement, review, QA, verify**. Use distinct session IDs for actors; each actor has one role. A reviewer and QA actor must differ from implementers and from each other. Required check kinds are fixed: implement=`test`, review=`analysis`, qa=`public`, verify=`final`. QA and final checks together must each cover every plan case. Known lint/typecheck-only commands cannot masquerade as public/final checks. Arbitrary command semantics remain the reviewer's responsibility.

Checks use argv arrays, never eval/shell interpretation by this helper. `cwd` must exactly match a canonical candidate source root (use `snapshot` output; `/var` versus `/private/var` aliases are not interchangeable in the manifest). `argv[0]` and declared tools must be discoverable executables. Skills must be existing files. `available_models` and `resolution_source` are **host-supplied observations**, not proof obtained by this tool. Include concrete model IDs from actual host capability discovery; unavailable resolution blocks. Receipt response-model metadata is compared with the resolved dispatch. Do not substitute an agent saying “I am model X” for provider metadata.

The actual saved graph is parsed: capability node existence, agent role, cycles and unknown edges are checked. The full feature graph's QA node can map both `qa` and `verify`, but these still require **separate check receipts**; final verify is not inferred from the QA label. A reduced graph missing QA is blocked. When design is required, the design node must exist; `design: owner` cannot silently become `plan: auto` without a design gate.

The profile must declare either an explicit `runtime.none` reason for a CLI/library public surface, or a live runtime. Missing setup cannot be replaced by `none` for API work. A live runtime accepts either:

- `runtime.command`: a bounded project-owned setup→checks→cleanup harness, or
- nonempty `runtime.up`, `seed`, `down`, `baseUrl`, and `health.command` or `health.url`+`expect`.

API work also requires `api.collection` and `api.schema`; the repo-relative collection must contain bruno.json inside a candidate source. The helper checks declarations, not endpoint health; the runner owns actual startup, isolation, identity observations and cleanup. Static candidates use `runtime: null` and `runtime_identity: null`. Live candidates require both values and a fresh identity artifact:

```json
{
  "worker_revision": "<one candidate source revision>",
  "sources_sha256": "<canonical fingerprint of the full candidate.sources array>",
  "run_id": "<run.id>", "instance_id": "<unique runtime instance ID>",
  "images_sha256": "<pinned image-set SHA256>",
  "corpus_sha256": "<pinned corpus SHA256>",
  "fingerprint": "<canonical SHA256 of preceding six identity fields>",
  "observed_at": "2026-09-29T12:00:00+00:00"
}
```

The runtime fingerprint must match `candidate.runtime`; worker revision must be among candidate sources, the full source fingerprint includes dirty trees, and run/instance identity distinguishes parallel stacks. The timestamp must not be future or older than `runtime_max_age_seconds`. A runner must regenerate this artifact from its observed worker/images/corpus, not copy the expected values. Fixture/schema hashes likewise come from observed runner inputs; use canonical JSON `[]` hash only for an honestly empty fixture/schema set. No running service is queried by this tool.

## Receipt schema

```json
{
  "check_id": "public-api", "actor": "qa-session-id", "model": "<actual provider response model>",
  "run_sha256": "<fingerprint run.json>",
  "candidate": {"sources": [], "runtime": null, "fixture_sha256": "<hash>", "schema_sha256": "<hash>"},
  "argv": ["make", "test-api-acceptance"], "cwd": "/absolute/candidate", "status": "PASS",
  "exit_code": 0, "executed": 1, "skipped": 0,
  "cases": [{"id": "AC-FANOUT", "status": "PASS"}],
  "observed_at": "2026-09-29T12:00:00+00:00",
  "log_path": "/absolute/run/evidence/api.log", "log_sha256": "<file SHA256>",
  "findings": {"blocking": 0, "important": 0}
}
```

Copy the **complete actual** candidate object; `sources: []` is only an illustration and is invalid. Case results are exactly PASS/FAIL/SKIPPED/BLOCKED. Receipt status is PASS/FAIL/BLOCKED. For analysis, `executed` counts inspected acceptance assertions, not claimed test executions; for test/public/final checks it is actual selected cases/checks executed. Preserve the original process exit status before any log-filtering pipeline. Zero executions, skipped required cases, missing cases, wrong actor/role/model, nonzero exit, important/blocking findings, changed logs, wrong candidate and expired evidence cannot prove PASS.

A store is `{"schema_version":1,"receipts":[…]}`. Recording uses a local POSIX file lock and atomic replacement. Receipt observation times must strictly increase per check; an old pass cannot overwrite a newer failure. The latest appended receipt per check wins; a later failure cannot be hidden by an older pass. Old source-state receipts remain in the store for history but do not prove the new candidate. The files are audit artifacts, **not tamper-proof signed attestations**; independent reviewers/QA must observe their own evidence.

## Attempts and events

```json
{"schema_version":1,"max_fix_rounds":3,"task_ids":["T1"],"attempts":[
  {"task_id":"T1","round":1,"decision":"fix","candidate":"<revision>","reason":"range assertion failed","hypothesis":"per-product ranges","outcome":"failed"}
]}
```

Run this validator before every fix dispatch. Rounds are consecutive per task and never reset. Outcomes are pending/passed/failed. After two failures for the same task/hypothesis, another fix on that hypothesis is rejected; a new diagnosis must name its changed hypothesis and evidence in reason. Beyond the limit the decision must be `replan` or `blocked`; either closes that task's repair series. A new approved plan is required to start another series. The tool validates an artifact; it cannot observe unrecorded dispatches or enforce host calls made outside the engine.

An event is `{"task_id":"T1","sequence":1,"kind":"progress","summary":"tests running"}`. Kinds are progress/yielded/completed/failed/decision. Per-task sequence strictly increases. State retains only the latest event per task; only completed/failed/decision returns `wake:true`. The engine/host must honor this signal; the helper does not intercept native notifications.

## Regression suite

```
uv run --python 3.12 --with PyYAML==6.0.2 python -m unittest discover -s tests/graph_control -v
```

Fixtures cover the audited FE3→FE4 missing edge, unavailable planned count, synthetic-as-real evidence, composed workflow transitions, missing QA graph/runtime, missing models/skills, lint-only false gates, exact source/dirty/runtime freshness, log drift, zero/skipped cases, later failures, repair limits, event coalescing, and a public CLI record→verify→wrong-candidate failure sequence. Semantic witness truth and meaningful oracle quality remain model-review/evaluation cases rather than parser claims.
