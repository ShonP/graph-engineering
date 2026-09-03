---
name: ux-evidence
description: Use whenever a change touches anything a user sees or does - screens, components, copy, layout, states, flows, animations. House rule - every UX change ships before/after evidence (screenshot pairs for static changes, short video or GIF pairs for flows) attached to the PR or committed under the project's docs. Covers what counts, what to capture, how to capture it as code, where it lives, and who checks it.
---

# UX change evidence

**House rule: no UX change merges without before/after evidence.** A reviewer
reading a diff cannot see what the user will see, and neither can the owner at
the merge gate. For a UX change the evidence *is* the change; the code is only
how it was done.

## What counts as a UX change

Anything that alters what a user sees or does:

- new or changed screens, components, layout, copy, iconography
- applied colors, spacing, typography (not token definitions alone)
- state beats: loading, empty, error, success, celebration
- navigation, flow order, number of steps, defaults
- animation, transitions, gestures
- accessibility-visible behaviour: focus order, labels, reduced-motion paths

Not a UX change: a refactor with identical render, backend-only work, tests,
docs. **When in doubt, capture.** A screenshot costs seconds; a reviewer
guessing what changed costs a round.

## What to capture

| Change | Evidence |
| --- | --- |
| Static (one screen, one state) | before + after screenshot, same viewport, same seeded data |
| Flow, interaction, animation | before + after recording, each ≤ 30s, or one side-by-side cut |
| New screen (no before) | "before" = the entry point as it was; after = every new screen; label it `new` |
| Multi-platform | one pair per platform the profile names |
| State beat touched | its own pair per state (loading / empty / error / success) |

Frame the capture at the change. A full-page screenshot of a moved button hides
the point; crop or highlight so the difference reads at thumbnail size.

## How: capture as code, before FIRST

1. **Capture "before" before touching any UI code.** Check out the base branch
   (or the worktree's starting commit), stand the app up with seeded data,
   capture. Once the code moves, before is gone and cannot be reconstructed.
2. **Write the capture as a script** and commit it beside the evidence, so a
   later UI change means re-render, never re-record:
   - Web: Playwright - fixed viewport, seeded deterministic data, no dev-tools
     chrome, `page.screenshot` / `recordVideo`.
   - iOS: `xcrun simctl io booted screenshot <file>.png`,
     `xcrun simctl io booted recordVideo <file>.mp4`.
   - Android: `adb exec-out screencap -p > <file>.png`, `adb shell screenrecord`.
   - If the repo already has a media pipeline (profile `rules`, media-producer
     assets), extend it; never build a parallel one.
3. **Re-run the same script on the changed code** for "after". Same data,
   same viewport, same steps - the only variable is the change.
4. **Recordings** follow `short-attention-media`: cut every wait, ≤ 30s,
   mp4 (h264, faststart) or GIF for short loops. Extract frames and look at
   them before calling the capture done - exit 0 is not a picture.

## Where it lives

The profile's `uxEvidence.path` (default `docs/ux/changes`):

```
<path>/<YYYY-MM-DD>-<slug>/
  README.md              one line per pair: what changed, why, which state
  capture.(ts|sh)        the script that produced every file below
  before-<screen>[-<state>].png|mp4|gif
  after-<screen>[-<state>].png|mp4|gif
```

- **PR body** gets a `## UX evidence` section: a two-column before | after table
  embedding the committed images (they render inline on GitHub), and a link per
  recording. A PR for a UX change with no such section is incomplete.
- Recordings over ~5 MB are attached to the PR through the GitHub UI instead of
  committed; the folder README links to the PR.
- During a playbook run, also copy the folder to `.graph/<run>/assets/` so the
  merge gate can present it without leaving the ledger.

## Who does what

| Role | Duty |
| --- | --- |
| implementer | captures before at task start, after at task end; a UI task is not `DONE` without both, and the report lists the paths |
| qa | uses the after capture as the row evidence for UI criteria; re-captures if it no longer matches the running system, and files a `FAILED` row if before and after are indistinguishable when the criteria say they should differ |
| reviewer | UI diff with no evidence folder or PR section = **Blocking** (stated house rule); evidence that contradicts the experience spec = Important |
| planner (merge node) | presents the pairs beside the diff; the owner approves what they can see |
| media-producer | builds launch demos from the same capture scripts; never re-records by hand |
