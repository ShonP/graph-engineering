---
name: short-form-posts
description: Use when writing or editing any short-form text post - an X post or thread, a LinkedIn post, a caption, a subject line, or above-the-fold copy. Covers hooks, cutting length, thread structure, and the rules that make text stop a scroll rather than get skipped.
---

# Short-Form Posts

**Read the voice doc first** - the file named by the profile's `content.voiceDoc`. It holds who the author is, what they have actually shipped, and the verified stories. A post not grounded in it is generic, and generic is the one failure mode this skill exists to prevent. Never put a claim in a post the voice doc or a live number from the repo cannot back. If the profile names no voice doc, report `NEEDS_SETUP` - do not invent a voice.

The reader is scrolling. The first line is the only thing that gets a fair hearing; everything after it is borrowed time.

## The one rule everything else serves

**The first line is the whole post.** On X, roughly the first two lines show before "Show more"; in a feed the eye grants about a second. Write the post, then write the first line last, then delete whatever came before it.

## Structure: Hook, Retain, Reward

1. **Hook** - earn the stop.
2. **Retain** - a list, a number, a story, or an open loop that makes the next line feel owed.
3. **Reward** - land something they can use, repeat, or argue with. A post that ends on a summary teaches nobody to come back.

## Cutting - do these in order on a finished draft

- **Delete the first sentence.** It is almost always a run-up. The real post starts at sentence two.
- **Delete every adverb and hedge.** Hedging reads as low confidence, and low confidence does not get shared.
- **One idea per post.** Two ideas is two posts, and both do better apart.
- **Cut the explanation of the thing you just said.** Trust the reader once.
- **Numbers survive, adjectives die.** "14 users" beats "a small number of users".
- **Say it out loud.** Anything you stumble on is a rewrite, not a typo.

## Hooks that work for a technical audience

| Pattern | Shape | Example |
| --- | --- | --- |
| Contradiction | The thing everyone believes, denied | "The review gate mattered more than the code generation." |
| Specific number | A count that implies a story | "Two of our 14 users can legally receive that email." |
| Confession | A failure you own, stated flatly | "Our test suite was green and the invariant was false in production." |
| Before / after | Two states, no filler between | "Local: passed. Production: false. Same migration." |
| Named enemy | The practice you are against | "Stop asking how to make the model write more code." |

Anti-hooks, all of which read as an ad: "Excited to share", "Thread 🧵👇" as the first line, a question nobody was asking, anything beginning with "In today's world".

## Formatting for a feed

- One thought per line. White space is a retention device: a wall of text is a skip.
- Short line, short line, long line. Rhythm keeps the eye moving down.
- No hashtags on X. No link in the opening post - links are down-ranked; put it in a reply.
- Emoji: at most one, and only when it replaces a word.

## Before posting - the checklist

1. Does line one work with the rest of the post covered?
2. Is there a number in the first three lines?
3. Did I delete the run-up sentence?
4. Can any line lose 20% without losing meaning?
5. Is the last line something a person can reply to in four words?
6. Read aloud, no stumbles.

For threads and the X algorithm's actual reward structure (engagement weights, the first-30-minutes rule, the posting ritual), read `references/x-mechanics.md` before posting to X.
