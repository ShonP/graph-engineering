---
name: ux-evidence
description: Use whenever a change touches anything a user sees or does - screens, components, copy, layout, states, flows, animations. House rule - every UX change ships before/after evidence (screenshot pairs for static changes, short video or GIF pairs for flows) attached to the PR, committed under the project's docs, or pushed to the profile's evidence store. Covers what counts, what to capture, how to capture it as code, where it lives, and who checks it.
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
   - iOS: `xcrun simctl io "$SIM_UDID" screenshot <file>.png`,
     `xcrun simctl io "$SIM_UDID" recordVideo <file>.mp4`, with a capture
     script run as `bash <plugin-root>/scripts/sim-session.sh -- <script>`
     (headless; it boots the device, exports `SIM_UDID` and shuts it down
     after). Captures spread over several tool calls: `sim-session.sh acquire`
     once, each capture as `sim-session.sh run --lease <id> -- <command>`, then
     `sim-session.sh release --lease <id>`. Never `open -a Simulator`.
     Close what you open. Agents get dedicated `graph-sim-*` devices (the
     wrapper creates or reuses one) and never touch any other simulator: the
     owner's devices are theirs. When the profile declares `lanes:`, build
     the app in the `xcodebuild` lane and run a capture against the already
     built product (a `test-without-building` run, or install and launch) in
     the `xctest` lane, each through `lane-run.sh` as its own command
     (`lanes.xctest` slots, or the `xcodebuild` count when undeclared).
   - Android: `adb exec-out screencap -p > <file>.png`, `adb shell screenrecord`.
   - If the repo already has a capture pipeline (profile `rules`), extend it;
     never build a parallel one.
3. **Re-run the same script on the changed code** for "after". Same data,
   same viewport, same steps - the only variable is the change.
4. **Recordings**: cut every wait (loading, transitions, human-speed typing),
   ≤ 30s, one flow per clip, mp4 (h264, faststart) or GIF for short loops. Extract frames and look at
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

With no `uxEvidence.store` (the default), the media is committed in the folder
beside its README and capture script.

When the profile sets `uxEvidence.store`, the media files (png, jpg, jpeg, gif,
webp, mp4, webm, mov) are **not committed**: save them in the folder as above,
run `<store.push> <folder>` and commit only README.md and the capture script.
The repo-relative path is the storage key, so the README and PR body reference
files by that path. Reviewers and qa read them with `<store.pull> <folder>`;
the owner opens one with `<store.link> <file>`, a short-lived URL that is never
written into the PR body or any file. `<store.push>`, `<store.pull>` and
`<store.link>` are the profile's `uxEvidence.store` commands, each with the
folder or file appended.

- **PR body** gets a `## UX evidence` section: a two-column before | after table
  embedding the committed images when the media is committed (they render
  inline on GitHub), and a link per recording; with `uxEvidence.store`, list
  each pair's repo-relative paths in the table and drag the after images into
  the PR description through the GitHub UI if they should render inline. A PR
  for a UX change with no such section is incomplete.
- Without a store, recordings over ~5 MB are attached to the PR through the
  GitHub UI instead of committed; the folder README links to the PR. With
  `uxEvidence.store`, they are pushed like every other file.
- During a playbook run, also copy the folder to `.graph/<run>/assets/` so the
  merge gate can present it without leaving the ledger.

## Who does what

| Role | Duty |
| --- | --- |
| implementer | captures before at task start, after at task end; with `uxEvidence.store`, pushes the folder and commits only its text; a UI task is not `DONE` without both, and the report lists the paths |
| qa | runs `<store.pull> <folder>` first when the profile sets `uxEvidence.store`; uses the after capture as the row evidence for UI criteria; re-captures if it no longer matches the running system, and files a `FAILED` row if before and after are indistinguishable when the criteria say they should differ |
| reviewer | UI diff with no evidence folder (or, with `uxEvidence.store`, no pushed media under it: `<store.pull>` returns nothing) = **Blocking**, and the same for no PR section (stated house rule); evidence that contradicts the experience spec = Important |
| planner (merge node) | presents the pairs beside the diff; the owner approves what they can see |
