---
name: privacy-review
description: Review a diff for privacy defects - personal data collection, retention, consent, third-party sharing, logging of sensitive fields, and deletion paths. Use on every code review pass, especially where health, financial or location data is touched.
---

# Privacy review

Cross-cutting, so it runs on every diff. Security asks whether the wrong person
can reach the data. Privacy asks whether the right person should have collected
it at all.

## What to look for

**Collection.** Does this add a new personal field? Is it needed for the stated
feature, or is it being gathered because it was available? Data not collected
cannot leak.

**Special categories.** Health, biometric, financial, location, sexual
orientation, religion, and anything about children carry stricter duties in most
regimes. A fitness or medical context means most new fields land here.

Art. 9 names eight categories and permits processing only under one of the
Art. 9(2)(a)-(j) conditions, of which explicit consent is the usual one. Read
`references/special-category-data.md` when classifying a new field, for the
categories, the processing conditions, and automated detection indicators.

**Consent.** If the feature depends on consent, is it specific, informed and
revocable, and is revocation actually wired to something? A consent flag nothing
reads is worse than none, because it looks like compliance. See the
`gdpr-consent` skill when the change touches consent capture or a preference
center.

**Logging and telemetry.** Personal data in logs, analytics events, error
reports or LLM prompts. Analytics payloads and prompt strings are the two that
get missed most.

**Retention and deletion.** New data needs an answer to "how long, and what
deletes it". A new table with no deletion path quietly breaks an existing
erasure guarantee. See the `gdpr-erasure-retention` skill when the change adds
a store or a delete path.

**Third parties.** A new SDK, endpoint or model provider receiving personal data
is a data-sharing change, not just a dependency change.

## Judgement

State the concrete exposure: which field, to whom, for how long. "Privacy
concern" with no field named is not actionable.

Where a legal question is genuinely open, say so and mark it for the owner
rather than inventing a compliance verdict.

## Attribution

`references/special-category-data.md` adapts an Agent Skill by mukul975,
Apache-2.0.
