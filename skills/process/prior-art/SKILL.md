---
name: prior-art
description: Use at the start of EVERY ask and again mid-task whenever a design decision, library choice, or surprise appears. House rule - before working, look at what others do (competitors, GitHub open source, articles, docs, papers), check whether an existing skill, plugin or library already solves it, evaluate every claim skeptically, spike the load-bearing ones, and only then start. Covers the skip rule, the source ladder, the skepticism checklist, the reuse-before-build check, and the prior-art note every task carries.
---

# Prior art before work

**House rule: no ask starts from priors.** A model working from memory is the
baseline; a model that first gathered what others do, checked what already
exists, and tested the claims it is about to build on is the product. The
difference is this skill, and it costs minutes.

## When it fires

- **At the start of every ask** - feature, bug, refactor, rule, doc, content.
- **Mid-task**, whenever any of these appear: a design decision with more than
  one credible shape; a library or API you are not certain of; two failed
  attempts at the same thing; a surprising behaviour; a "let me just write my
  own" impulse.

**Skip only for:** pure logic with no external dependency, a mechanical change
(rename, config tweak, typo), or a hotfix whose root cause is already proven.
A skip is written down: `Prior art: skipped - <reason>`. An unwritten skip is a
missed check.

## Budget

Scale to the ask. A small task gets 2-4 searches and one fetch, under five
minutes. A feature run dispatches the `researcher` MAP (ux, tech, competitor in
parallel) and each report has its own turn budget. A spike gets its dispatch's
`maxTurns` and reports `PARTIAL` when it runs out. Research past the budget is
procrastination wearing a lab coat.

## What to look at, in this order

1. **Reuse candidates - before anything else.** Is there an existing skill in
   this plugin, an installed plugin, a library, a CLI, a GitHub project, or a
   platform feature that already does this? Search the skill listing, the
   package registry, and GitHub. Reuse or adapt beats build; build only when
   you can name what the candidates lack.
2. **Competitors and best-in-class products** - how do they solve this exact
   moment? Interaction patterns, defaults, edge-case handling. Observe the
   product where you can; a review's description of it is second-hand.
3. **Open source** - repos solving the same problem. Read the code, not the
   README; clone and run when the claim matters.
4. **Official docs, changelogs, maintainer issues and PRs** - versioned, dated.
5. **Articles, blog posts, papers, talks** - inspiration and vocabulary.
   Never load-bearing on their own.

## The source ladder - how much a source is worth

| Rung | Source | Worth |
| --- | --- | --- |
| 1 | Code you ran, an experiment you performed | evidence |
| 2 | Official docs, changelog, release notes - with version and date | strong, verify the version matches yours |
| 3 | Maintainer issue / PR / design doc | strong for intent, check whether it shipped |
| 4 | Named author, dated, cites sources, shows code or numbers | usable, one rung below anything it cites |
| 5 | Anonymous post, SEO listicle, "experts agree", undated | inspiration only, never a decision input |

## Skepticism checklist - every claim you are about to build on

- **Who** says it, and what do they gain if you believe it?
- **When** - which version, which year? A 2023 answer about a library on a
  major release a year is a rumor about today.
- **What evidence** is shown - code, numbers, a reproduction, or adjectives?
- **Does it reproduce** in this repo, with these versions? If the claim is
  load-bearing for the design and you have not reproduced it, it is not yet
  true: spike it. Dispatch `researcher` in spike mode, or run the smallest
  experiment that could kill the claim yourself.
- **Never validate on one happy-path run.** A spike verdict is
  `VALIDATED`, `PARTIAL`, or `INVALIDATED`, and it names the edge case tried.
- **Separate observation from inference** in what you write down: "the docs
  say X" and "so Y should work" are different sentences.

Worked example: a paper reports instruction files cut agent wall-clock ~29%.
Read further: 10 repos, one model, PRs under 100 lines, no quality
evaluation. Usable as "instruction files are cheap and probably help", not as
"29%" and not as "longer files are better" - the paper never tested that.

## Output - the prior-art note

Every task carries one, however short. Small task: a `## Prior art` section in
the plan or PR body. Feature run: `.graph/<run>/research/prior-art.md`,
composed from the researcher reports. Content:

```
Reuse candidates : <what exists> -> adopt / adapt / reject, with the lack named
Looked at        : <source> (<rung>, <date/version>) - one line each
Borrowed         : <pattern> from <source>
Rejected         : <pattern> from <source> - <why>
Spiked           : <claim> -> VALIDATED / PARTIAL / INVALIDATED (<edge case>)
Skipped          : <reason>   (only when the skip rule applied)
```

## Who

| Role | Duty |
| --- | --- |
| planner | goal node frames the research questions; plan node reads the reports, writes the note, and names the reuse decision before any build task |
| researcher | executes ux / tech / competitor / spike modes; the note cites its reports |
| implementer | reads the run's note before code; runs the small-task version when there is none; re-fires on any mid-task trigger and appends to the note |
| reviewer | plan or PR without a prior-art note or a written skip reason is Important; new code that re-implements an available, adequate library or skill is Important |
| ux-designer | pattern research in `ux-journey` step 3 is this rule for UX; cite patterns, not pixels |
