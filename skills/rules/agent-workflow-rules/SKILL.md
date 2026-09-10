---
name: agent-workflow-rules
description: Apply for AI agents, LLM workflows, Microsoft Agent Framework, model orchestration, structured outputs, validators, tool use, checkpoints, observability, and token/cost management.
---

# AI Agent + Workflow Rules
Harvested from the owner's global rule packs on 2026-09-10 (spec 4.3); the plugin copy is the portable one.

Framework default: Microsoft Agent Framework unless a project explicitly says otherwise.

## Core Patterns

- Structured outputs: Pydantic models / Zod schemas for LLM responses in code. Never parse free text for control flow.
- Workflows over single calls: break complex work into discrete steps with checkpoints.
- Durability: persist agent state after each step; recover from crashes without re-running completed work.
- Retry with state: resume from last checkpoint; don't restart whole workflows.
- Tool use with validation: validate tool inputs/outputs with schemas and handle tool failures explicitly.
- Token + cost budget: track and limit per step and per workflow; surface cost in run metadata.
- Observability: log every LLM call, tool invocation, and state transition.
- Validators decide: when output gates downstream work, LLM emits per-axis numeric scores; deterministic code decides pass/reject.
- Plain language by default for reader-facing prose unless the project demands otherwise.

## Design Bias

- Prefer durable workflows for multi-step business processes.
- Prefer typed state and explicit transitions.
- Keep model prompts and schemas versioned with the workflow.
- Avoid hidden mutable global agent state.
- Make replay/resume behavior testable.
