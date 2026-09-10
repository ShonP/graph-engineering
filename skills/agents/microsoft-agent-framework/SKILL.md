---
name: microsoft-agent-framework
description: Use when building or reviewing anything agentic - an agent, a tool, a multi-step workflow, checkpoints, human-in-the-loop, or agent observability. Microsoft Agent Framework is the house default framework; covers agent construction, Pydantic structured outputs, typed function tools, workflows, checkpointing and OpenTelemetry.
license: MIT
---

# Microsoft Agent Framework

Sources (fetched 2026-09-10 with curl, all HTTP 200). Four of the plan's URLs
now redirect; the effective URL is what the rules cite and the planned URL is
named beside it:

- https://learn.microsoft.com/en-us/agent-framework/overview/ - "Microsoft Agent Framework Overview | Microsoft Learn" (from `/overview/agent-framework-overview`)
- https://learn.microsoft.com/en-us/agent-framework/concepts/agents/running-agents - "Running Agents | Microsoft Learn" (from `/tutorials/agents/run-agent`)
- https://learn.microsoft.com/en-us/agent-framework/concepts/agents/custom-agents - "Custom Agents | Microsoft Learn" (from `/user-guide/agents/agent-types/chat-client-agent`)
- https://learn.microsoft.com/en-us/agent-framework/agents/structured-outputs - "Producing Structured Outputs with agents | Microsoft Learn"
- https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools - "Using function tools with an agent | Microsoft Learn"
- https://learn.microsoft.com/en-us/agent-framework/agents/observability - "Observability | Microsoft Learn"
- https://learn.microsoft.com/en-us/agent-framework/workflows/ - "Workflow capabilities | Microsoft Learn" (from `/user-guide/workflows/overview`)
- https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/ - "Workflow concepts | Microsoft Learn"
- https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints - "Microsoft Agent Framework Workflows - Checkpoints | Microsoft Learn"
- https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop - "Microsoft Agent Framework Workflows - Human-in-the-loop (HITL) | Microsoft Learn"
- https://learn.microsoft.com/en-us/agent-framework/workflows/observability - "Microsoft Agent Framework Workflows - Observability | Microsoft Learn"
- https://github.com/microsoft/agent-framework/blob/main/docs/decisions/0037-agent-skills-design.md - "agent-framework/docs/decisions/0037-agent-skills-design.md at main - microsoft/agent-framework - GitHub"

Versions: the Learn pages above were last updated 2026-08-25. Python package
`agent-framework`, 1.18.0 on PyPI and installed for the Verify run below,
requires Python >= 3.10. Install with `uv add agent-framework` (the docs say
`pip install agent-framework`; uv is the house package manager). Python is the
house language, so the rules below quote the Python tabs; the .NET and Go
shapes differ and the pages carry all three.

## When to apply

- Any agent, tool, workflow, checkpoint or orchestration in a Python service.
- Choosing between a plain function, one agent call, and a workflow.
- Any LLM output that another piece of code consumes.
- Adding telemetry, cost limits or approval gates to agent code.

## Rules

**Choose the smallest thing that works**

- The overview's own rule first: "If you can write a function to handle the
  task, do that instead of using an AI agent."
  (https://learn.microsoft.com/en-us/agent-framework/overview/)
- Use an agent when the task is open-ended or conversational and one LLM call
  with tools suffices. Use a workflow when the process has well-defined steps,
  execution order matters, or several agents and functions must coordinate.
  (https://learn.microsoft.com/en-us/agent-framework/overview/)
- Agents are built from a chat client:
  `OpenAIChatClient(...).as_agent(name=..., instructions=..., tools=[...])`, or
  `Agent(client=..., ...)`. Provider choice is a constructor argument, not a
  rewrite. (https://learn.microsoft.com/en-us/agent-framework/overview/,
  https://learn.microsoft.com/en-us/agent-framework/concepts/agents/running-agents)
- Write a custom agent class only when no chat client shape fits; that path
  means implementing session creation and deserialization yourself.
  (https://learn.microsoft.com/en-us/agent-framework/concepts/agents/custom-agents)

**Structured outputs, always**

- Anything downstream code branches on is a Pydantic model passed as
  `options={"response_format": MyModel}`; the parsed instance comes back on
  `response.value`, and `response.text` is for humans.
  (https://learn.microsoft.com/en-us/agent-framework/agents/structured-outputs)
- Prefer the Pydantic model over the raw JSON-schema mapping form: with a schema
  dict, `response.value` is a plain `dict` or `list` and you have validated
  nothing. House rule (Pydantic v2 everywhere, no dataclasses) applies to every
  one of these models.
  (https://learn.microsoft.com/en-us/agent-framework/agents/structured-outputs)
- Guard the empty case. The docs' own example is
  `if response.value: ... else: print("No structured data found in response")`;
  a refusal is still `Content(type="text")` and carries
  `additional_properties["model_output_kind"] == "refusal"`, which structured
  output extraction does not parse.
  (https://learn.microsoft.com/en-us/agent-framework/agents/structured-outputs,
  https://learn.microsoft.com/en-us/agent-framework/concepts/agents/running-agents)
- When streaming, do not parse partial updates. Iterate for display, then take
  the parsed value from `await stream.get_final_response()`.
  (https://learn.microsoft.com/en-us/agent-framework/agents/structured-outputs)
- Not every agent type supports structured outputs natively; the chat-client
  agent does, with a compatible client. Check before designing around it.
  (https://learn.microsoft.com/en-us/agent-framework/agents/structured-outputs)
- Validators decide, not the model (house rule, `agent-workflow-rules`): where an
  LLM judges quality, its response model carries per-axis numeric scores and
  ordinary Python compares them against thresholds.

**Tools**

- A tool is a typed Python function. Describe every parameter with
  `Annotated[str, Field(description=...)]` so the model gets a real schema, and
  use `@tool(name=..., description=...)` when the function name and docstring
  are not the description you want.
  (https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)
- For full control of the schema the model sees, pass `schema=MyInputModel` (a
  Pydantic model) to `@tool`.
  (https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)
- Runtime-only values (session, request context, user id) arrive through
  `FunctionInvocationContext`, which is hidden from the model's schema. Never
  add a parameter the model must fill just to smuggle context in.
  (https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)
- Bound state (clients, flags, caches) belongs on a class whose bound methods
  are the tools, not on module-level globals.
  (https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)
- Bound the tool loop:
  `client.function_invocation_configuration.update({"max_iterations": ...,
  "max_function_calls": ..., "max_duration_seconds": ...})`. All default to
  unlimited. The docs call the limits best effort, checked after each batch of
  parallel calls, and approval wait time counts toward the duration, so treat
  them as a backstop rather than an exact budget.
  (https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)
- `approval_mode` on `@tool` is a security control. Anything that writes,
  spends, or leaves the process keeps approval on; `never_require` is for
  read-only tools and is a decision to state out loud.
  (https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)

**Workflows**

- Graph workflows are `WorkflowBuilder` plus typed executors, edges, events and
  state; Python also has an experimental functional `@workflow` API. Both
  produce the same observable results, so pick by execution model: fixed graphs
  and fan-out or fan-in favour the graph API, sequential pipelines with native
  control flow favour the functional one.
  (https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/)
- Workflows execute in supersteps. That is the unit of progress, of
  checkpointing, and of reasoning about parallelism.
  (https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- Long-running work gets a `checkpoint_storage` on the builder. A checkpoint
  captures executor state, pending messages for the next superstep, pending
  requests and responses, and shared state, at every superstep boundary.
  (https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- Pick storage by durability, not by convenience: `InMemoryCheckpointStorage`
  for tests, `FileCheckpointStorage` for one machine,
  `CosmosCheckpointStorage` (`agent-framework-azure-cosmos`) for production and
  cross-process. All three implement the same protocol, so the swap costs
  nothing later if you never depended on the in-memory one.
  (https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- A custom executor with its own state must implement both
  `on_checkpoint_save` (return the state dict) and `on_checkpoint_restore`
  (put it back). One without the other is a workflow that resumes wrong.
  (https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- Human input is a `RequestPort`: the executor sends a request, a
  `RequestInfoEvent` is emitted, an external system answers, and the framework
  routes the response back. Do not block a thread waiting for a person.
  (https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- Reach for the capability the docs already ship (agents in workflows,
  workflows as agents, declarative workflows, orchestration patterns) before
  writing your own coordinator.
  (https://learn.microsoft.com/en-us/agent-framework/workflows/)

**Observability and safety**

- Telemetry is OpenTelemetry, following the GenAI semantic conventions.
  Configure it once with `configure_otel_providers()` from
  `agent_framework.observability`, which reads the standard `OTEL_EXPORTER_OTLP_*`
  environment variables, or activate instrumentation alongside a third-party
  setup with `enable_instrumentation()`.
  (https://learn.microsoft.com/en-us/agent-framework/agents/observability)
- Sensitive data stays off outside development. The docs are explicit that
  prompts, responses, function-call arguments and results are the sensitive
  data, and that enabling it in production can expose user information in logs
  and traces. `enable_sensitive_data=True` is a development-only switch.
  (https://learn.microsoft.com/en-us/agent-framework/agents/observability)
- Instrument the chat client or the agent, not both, unless you want the chat
  context duplicated across spans.
  (https://learn.microsoft.com/en-us/agent-framework/agents/observability)
- Workflow spans are named and stable (`workflow.build`, `workflow.run`,
  `executor.process {executor_id}`, `edge_group.process`, `message.send`);
  build dashboards and alerts on those names rather than on log text.
  (https://learn.microsoft.com/en-us/agent-framework/workflows/observability)
- Credentials come from a specific credential in production. The docs warn that
  `DefaultAzureCredential` is a development convenience whose fallback probing
  is a latency and security risk; use something like `ManagedIdentityCredential`
  instead. Keys stay in the environment or a secret store, never in the prompt
  or the repo.
  (https://learn.microsoft.com/en-us/agent-framework/agents/structured-outputs,
  https://learn.microsoft.com/en-us/agent-framework/agents/observability)
- The framework does not load `.env` files for you, and third-party systems
  (non-Azure models, external agents and servers) run under their own terms:
  call `load_dotenv()` explicitly, and review what data crosses that boundary.
  (https://learn.microsoft.com/en-us/agent-framework/overview/)
- The framework's own agent-skills design is ADR 0037, status `proposed`
  (2026-03-23) and C#-first. Do not build a Python skills loader on it yet.
  (https://github.com/microsoft/agent-framework/blob/main/docs/decisions/0037-agent-skills-design.md)

Silent in these docs: per-step token and cost budgets, and versioning prompts
and schemas with the workflow. The harvested `agent-workflow-rules` pack governs
both, plus making replay and resume testable.

## Anti-patterns

- Parsing `response.text` with a regex or `json.loads` to decide what happens
  next. Failure: a wording change from the model becomes a production incident.
  Use `response_format` and `response.value`.
- A tool whose parameters are bare `str` with no `Field(description=...)`.
  Failure: the model guesses argument meaning and calls it wrongly, and the
  failure looks like a model problem rather than a schema one.
- `approval_mode="never_require"` on a tool that writes or spends. Failure: an
  agent takes an irreversible action nobody approved.
- No `max_iterations` or `max_function_calls`. Failure: a tool loop that only
  stops when the bill or the timeout does.
- One giant prompt that "does all the steps". Failure: nothing is resumable,
  nothing is inspectable, and one bad step poisons the whole output.
- A module-level agent or mutable global state shared across requests. Failure:
  cross-request leakage and tests that pass only in order.
- An in-memory checkpoint store in a service that restarts. Failure: the
  workflow claims durability and loses everything on deploy.
- An executor that saves state without `on_checkpoint_restore`. Failure: the
  resumed run looks healthy and computes on empty state.
- `enable_sensitive_data=True` in a deployed service. Failure: prompts,
  responses and tool arguments (which is to say user data) land in traces.
- An LLM judge that returns "pass" or "fail". Failure: the gate drifts with the
  model. The model scores; Python decides.
- Secrets interpolated into instructions or a prompt template. Failure: the
  secret is now in every trace, log and provider-side transcript.

## Verify

```bash
uv add agent-framework
uv run python -c "import importlib.metadata as m; print(m.version('agent-framework'))"
uv run python verify_maf.py     # structured output through a real chat client
```

Run 2026-09-10 with `agent-framework 1.18.0` against an Azure Foundry
deployment (`gpt-5.4-mini`), endpoint and key from the environment:

```
$ uv run python -c "import importlib.metadata as m; print(m.version('agent-framework'))"
1.18.0

# response_format=PersonInfo (a pydantic BaseModel)
type: PersonInfo
value: name='John Smith' age=35 occupation='software engineer'

# @tool with Annotated[str, Field(description=...)] plus response_format=Forecast
tool calls: ['Amsterdam']
type: Forecast value: city='Amsterdam' summary='Cloudy with a high of 15C.'
```

Expected: `response.value` is an instance of your model, not a `dict` and not a
string, and the tool actually ran (assert on your own recorded call list, not on
the prose in `response.text`). If `response.value` is falsy, the run produced no
structured data and the caller must handle that path.
