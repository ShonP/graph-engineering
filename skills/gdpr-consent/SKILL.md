---
name: gdpr-consent
description: Implement GDPR-valid consent - the five Article 7 conditions, mobile consent flows (Apple ATT, Android ad ID, SDK propagation), and a multi-purpose preference center with withdrawal and audit trail. Use when adding, reviewing or auditing any consent capture, cookie banner, tracking permission or preference UI.
---

# GDPR consent

Consent is the weakest lawful basis and the easiest to get wrong. If another
basis genuinely fits - contract, legitimate interest - use it and skip this.
Consent that can be withdrawn at any time is a poor foundation for a feature
that stops working when it is.

## The five conditions

Consent is valid only if it is **freely given, specific, informed,
unambiguous, and given by clear affirmative action** (Art. 4(11), Art. 7).

The failures that actually appear in code:

- **Pre-ticked boxes.** Prohibited outright. *Planet49*, CJEU C-673/17.
- **Bundling.** One checkbox covering analytics, marketing and personalisation is not specific. One purpose, one signal.
- **Conditionality.** Access refused unless the user consents to unrelated processing is not freely given (Art. 7(4)).
- **Withdrawal harder than granting.** Art. 7(3) requires it to be as easy. A one-tap opt-in with a support-ticket opt-out fails.
- **Silence or inactivity.** Scrolling, continuing to browse, or a timeout are not affirmative action.

Read `references/valid-consent.md` for each condition against its recitals, plus a consent-form audit checklist.

## Mobile

Two consent systems stack: the platform's and yours. Apple ATT gates IDFA
access and must be requested at a moment the user can understand; Android 13+
restricts the advertising ID; and neither replaces GDPR consent, they sit on
top of it.

The one that gets missed: **SDK propagation.** Third-party SDKs initialised
before consent is resolved will collect anyway. Initialise them from the
consent state, not from app start.

Read `references/mobile-consent.md` for ATT states and handling, the Android
model, first-launch flow design, and SDK initialisation patterns.

## Preference center

Per-purpose granularity, withdrawal under Art. 7(3), version history, and an
audit trail proving what was consented to and when. Consent you cannot
evidence is consent you do not have.

Read `references/preference-center.md` for the data model, API design, TCF
v2.2 integration and UI component specification.

## Reviewing consent code

- Is the signal recorded per purpose, with a version and timestamp?
- Does withdrawal actually stop the processing, or only flip a flag nothing reads?
- Are SDKs gated on consent state at initialisation?
- Can you produce, for one user, what they consented to and when?

A consent flag nothing reads is worse than no flag, because it looks like
compliance.

## Attribution

The references adapt Agent Skills by mukul975, Apache-2.0.
