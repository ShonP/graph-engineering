---
name: product-spec
description: Write a product spec that states intent, value, success metrics and non-goals, and that surfaces open questions instead of burying them. Use when turning a stated goal into something a plan can be built from.
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

## The rule that matters

An assumption the owner can see and reject is worth more than a guess that reads
like knowledge. When you do not know, write "Assumption:" and keep going. Do not
smooth over the gap with confident prose.

## Length

Scale to the work. A one-line fix needs three sentences. A new subsystem needs
the full set. Ceremony spent on a small change is attention taken from a large
one.
