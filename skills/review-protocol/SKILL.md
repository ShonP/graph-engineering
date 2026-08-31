---
name: review-protocol
description: The severity scale, refutation rules and finding format every reviewer uses. Use whenever reporting code review findings so that severity means the same thing across reviewers and runs.
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

## Format

```
severity | file:line | failure scenario | rule reference | confidence
```

The failure scenario is concrete inputs leading to a wrong result. Not "could be
unsafe" but "with `next: []` this returns valid and the run never terminates".

Order blocking, important, nit. End with **PASS** or **CHANGES-REQUESTED**.

## Do not

Praise. Soften. Pad with observations to look thorough. Fix anything - you
report, someone else decides.
