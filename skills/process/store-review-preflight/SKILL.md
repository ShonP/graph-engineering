---
name: store-review-preflight
description: Use before every App Store or Google Play submission or resubmission, after any rejection, and whenever a change removes or adds a feature a store declaration names (age gate, sign-in, tracking SDK, purchases, health data, user content) - walks the declarations-match-the-binary ledger and the most common rejection causes so a review fails at most for something new.
---

# Store review preflight

Most rejections are not bugs. They are a store answer that no longer matches
the build: a questionnaire ticked months ago, a feature removed since, a
reviewer who cannot find what the metadata promises. The reviewer checks the
listing against the build on whatever device they hold (often an iPad), with
no context beyond the review notes.

## 1. The declaration ledger

Keep every store answer as data in the repo (a listing config the store API
applies, or a table with one row per answer), each row naming the code path or
screen that makes it true. A PR that adds, removes or gates a feature named in
the ledger changes the row in the same PR. Prefer an executable check that
fails when a row and the code disagree over a prose reminder.

| Declaration | True only when | Reviewer must be able to |
|---|---|---|
| Age rating: In-App Controls (Parental Controls, Age Assurance) | the build ships a control that restricts content or features by age or by a guardian | reach it from the review notes; otherwise answer No (Guideline 2.3.6) |
| Age rating content and capabilities (UGC, chat, social, web access, ads, gambling, loot boxes, contests, medical/wellness) | the feature is in this build | see it, or not find it |
| Age override / Made for Kids | the audience really is that band | - |
| App Privacy label, Play Data safety | every linked SDK's collection is listed with its linking and purpose; privacy manifest (`PrivacyInfo.xcprivacy`) agrees | - |
| Tracking (ATT) | the app or an SDK tracks across apps; prompt shown before it | see the prompt |
| Sign-in | third-party login offers Sign in with Apple (4.8); in-app account deletion exists (5.1.1(v)) | sign in with the demo account or as a guest, and delete |
| Purchases | StoreKit/Play Billing for digital goods (3.1.1); restore; terms and privacy links and price/period on the paywall (3.1.2) | buy in sandbox and restore |
| Health, camera, location, photos, motion, notifications | each permission has a specific usage string; health data never feeds ads or iCloud (5.1.3) | trigger each prompt |
| Encryption | export answer matches the binary (`ITSAppUsesNonExemptEncryption`) | - |

## 2. Before submit

- Diff the ledger against the release branch: every feature added or removed since the last approved build has its declaration row updated.
- Review notes say how to reach every declared control, sign-in path, purchase and permission; give a demo account when sign-in gates anything; attach a device recording when a flow needs hardware, an account or a region the reviewer lacks.
- Run the build on the reviewer's likely devices: smallest supported iPhone and an iPad (an iPhone-only app still runs there in compatibility mode). No crash with no network, no placeholder or beta wording, no dead links.
- Metadata: name, subtitle, description and screenshots show only what the build does; screenshots come from the build; no other platform's names or prices; support and privacy URLs load.
- Accounts the store needs (paid apps agreement, tax, DSA trader status, content rights, encryption) are complete.

## 3. After a rejection

1. Read the cited guideline and the exact sentence; classify it: metadata mismatch (fix in the console, no new build), missing information (answer and attach), or binary defect (new build).
2. Reply in the review thread before resubmitting when the console still offers it; cancelling or removing a submission can close the thread.
3. Fix the root: update the ledger row and add or extend the check that would have caught it, in the same PR.
4. Resubmit with notes that open with what changed and where to see it. Submitting stays a human-confirmed step; an agent may prepare the build, notes and answers.

## 4. API reach (App Store Connect)

The API can read and write the age-rating declaration, review notes, the
version's build, and resolve and resubmit a submission (`reviewSubmissionItems`
`resolved`, `reviewSubmissions` `submitted`). It cannot post in the review
thread, edit the App Privacy label, or set DSA trader status; those are web-UI
steps the preflight lists for a human.
