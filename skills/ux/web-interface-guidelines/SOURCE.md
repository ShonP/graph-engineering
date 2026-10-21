# SOURCE
- Upstream: https://github.com/vercel-labs/web-interface-guidelines (published at https://vercel.com/design/guidelines)
- File: `AGENTS.md` at the repository root, copied byte for byte
- Commit: 434b7f91364665f2f733b310ec54809bf8f37937 (the repo has no tags), committed 2026-10-05 UTC
- AGENTS.md blob: 2785de041ab86453abcdbedd999084e6c207d6df
- Vendored: 2026-10-21
- License: MIT (Copyright 2025 Vercel Labs); LICENSE alongside, copied from the upstream root `LICENSE`; no NOTICE upstream
- Not vendored: Vercel's `web-design-guidelines` agent skill in `vercel-labs/agent-skills`. It fetches `command.md` from `main` on every run, so it is unpinned and needs network; the pinned `AGENTS.md` gives the same rules at a known version.
- Refresh:
  ```bash
  P=$(git rev-parse --show-toplevel); C=<new commit>
  gh api "repos/vercel-labs/web-interface-guidelines/contents/AGENTS.md?ref=$C" --jq .content | base64 -d > $P/skills/ux/web-interface-guidelines/AGENTS.md
  gh api "repos/vercel-labs/web-interface-guidelines/contents/LICENSE?ref=$C" --jq .content | base64 -d > $P/skills/ux/web-interface-guidelines/LICENSE
  git hash-object $P/skills/ux/web-interface-guidelines/AGENTS.md
  ```
  Update the commit, date and blob lines above, then run `bash scripts/run-all-tests.sh`.
- Local changes: none. `SKILL.md` is house text; where it diverges from `AGENTS.md` (contrast), it wins.
