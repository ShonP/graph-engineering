---
name: short-attention-media
description: Use when producing any video, demo, reel, screenshot set, or generated image for an audience that scrolls - product demos, feature walkthroughs, social cuts, launch assets. Covers the hook window, pacing, captions, length caps, and render verification.
---

# Short-Attention Media

The viewer grants about **1.3 seconds** before scrolling on. Everything in this skill serves that number.

## The hook window

- **First 1.3s must show the payoff, not the setup.** Open on the result - the finished screen, the number moving, the before/after - then explain. Never open on a logo, a title card, or a loading state.
- The first frame is the thumbnail. It must read at feed size with the sound off.

## Length caps

| Asset | Cap | Why |
| --- | --- | --- |
| Social cut (X, LinkedIn, Reels) | ≤ 30s | completion rate is the ranking signal |
| Feature demo | ≤ 60-90s | one feature, one journey, no tour |
| Tutorial | chaptered, each chapter ≤ 90s | nobody watches a 10-minute video, everybody watches six 90s ones |

One video = one idea. A second feature is a second video, and both do better apart.

## Pacing

- **Cut every wait.** Loading states, page transitions, typing at human speed - all dead frames. Speed through or cut.
- A beat that doesn't change what's on screen within ~2s gets cut or a caption.
- Motion pulls the eye: prefer the take where something moves toward the point being made.

## Captions and sound

- **Captions always.** Most feed video plays muted. The video must work with sound OFF; narration is an enhancement.
- Caption text follows the short-form-posts cutting rules: numbers survive, adjectives die.

## Production shape (code, not screen-recording by hand)

The whole video is code, so a UI change means re-render, never manual re-record:
1. **Record real flows** with Playwright against a seeded local stack - real app, real data, deterministic.
2. **Narrate with TTS**, script in a versioned file so copy edits are diffs.
3. **Composite** with Remotion (or concat + ffmpeg for simple cuts): captions, zoom-pans, chapters.
4. **Encode for target**: web = h264 crf 26 + faststart + poster frame; social = per-platform aspect (9:16 reels, 1:1 or 16:9 X).

## Verification - the non-negotiable

**Never ship a render on exit codes alone.** Extract frames and look at them:

```bash
ffmpeg -ss <t> -i out.mp4 -frames:v 1 frame.png
```

Check the hook frame, one mid frame per section, and the last frame. A render pipeline once produced 100% error-overlay frames with exit 0. Verify captions render, narration aligns, no dev-tool chrome in shot.

## Images

- One idea per image; it must read at thumbnail size.
- Generated images: draft at low quality to validate direction, finalize high, exact text quoted verbatim in the prompt - and expect garbled text anyway, so keep load-bearing text out of generated images.
- Screenshots: seeded realistic data, never lorem ipsum or empty states (unless the empty state is the subject).
