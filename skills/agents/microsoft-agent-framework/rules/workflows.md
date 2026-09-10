# Workflows

Rules for Microsoft Agent Framework workflows. Read with the parent `SKILL.md`
whenever the task builds, resumes or coordinates a multi-step run. Sources are
the ones listed in `SKILL.md`, fetched 2026-09-10.

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
