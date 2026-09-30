---
name: product-spec
description: Write a product spec that states intent, value, success metrics and non-goals, and that surfaces open questions instead of burying them. Use when turning a stated goal or a new product idea into something a plan can be built from.
---

# Product spec

A spec exists so that a plan can be argued from something. If it does not
constrain what gets built, it is a summary, not a spec.

## Sections

**Intent.** One sentence. What changes for someone once this exists. If it takes
a paragraph, the work is not one feature.

**Who it is for.** A named user in a named situation. "Users" is not an answer.

**Value.** Why this over the next thing on the list. An honest "because the owner
asked" is better than an invented business case.

**Success metrics.** How you will know it worked, stated so a disagreement about
it is settleable. Prefer something already measured over something that would
need new instrumentation.

**Non-goals.** What this deliberately does not do. This section prevents more
rework than any other, because it is where scope creep is refused in advance.

**Open questions.** Every unknown, listed. Each one leaves this section by being
spiked or by becoming a stated assumption in the plan. Never by being resolved
quietly.

The next three sections are required in a product concept (`concept.md`) and
whenever the goal carries `product-discovery: yes`; a bounded change on an
established contract leaves them out.

**Options.** 2-3 ways to meet the intent, each with its cost and what it gives
up. One is always the smallest thing that puts the intent in front of a real
user. One is always buy / do nothing: an existing product, service or library,
or not building it, with what that costs the named user. A recommendation
closes the section.

**Riskiest assumption.** One per option: the belief that, if false, kills that
option (value, usability, feasibility or viability), and the cheapest spike
that would test it.

**Completeness checklist.** One row each for design system, auth and session,
developer experience and CI, QA, observability, cost, and skills per
technology: `covered`, `gap` or `n/a`, with the research line or reason that
says so. A `gap` on the recommended option is a task or an open question.

**Signal.** One line under the success metrics,
`signal: already logged | instrumentation task`: whether the success metric is
already measured where the product runs (name the metric, event or table), or
needs an instrumentation task that ships ahead of the change so a baseline
exists. Internal, refactor and infra work with no user-facing outcome has no
signal line; its plan says why instead.

## The rule that matters

An assumption the owner can see and reject is worth more than a guess that reads
like knowledge. When you do not know, write "Assumption:" and keep going. Do not
smooth over the gap with confident prose.

## Length

Scale to the work. A one-line fix needs three sentences. A new subsystem needs
the full set. Ceremony spent on a small change is attention taken from a large
one.
