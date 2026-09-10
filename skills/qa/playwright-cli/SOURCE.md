# SOURCE
- Upstream: https://github.com/microsoft/playwright
- Subtree: packages/playwright-core/src/tools/skills/playwright-cli
- Commit: af74c938e45f3e759dc2521993f201389eb16cb6 (untagged from this skill's point of view; the repo tags releases of the library, not of the skills, so this SHA is the pin), committed 2026-09-09
- Vendored: 2026-09-10, plan 2026-09-10-stack-skills Task 14
- License: Apache-2.0; LICENSE alongside, copied from the upstream repository root `LICENSE`; NOTICE alongside, copied from the upstream repository root `NOTICE`, because Apache-2.0 section 4(d) requires the NOTICE text to travel with every redistribution
- Refresh:
  ```bash
  S=<scratch>; P=/Users/shonpazarker/projects/graph-engineering
  git clone --filter=blob:none --no-checkout https://github.com/microsoft/playwright $S/playwright
  cd $S/playwright && git sparse-checkout init --cone && git sparse-checkout set packages/playwright-core/src/tools/skills
  git checkout af74c938e45f3e759dc2521993f201389eb16cb6
  rsync -a --delete --exclude .git $S/playwright/packages/playwright-core/src/tools/skills/playwright-cli/ $P/skills/qa/playwright-cli/
  cp $S/playwright/LICENSE $P/skills/qa/playwright-cli/LICENSE
  cp $S/playwright/NOTICE $P/skills/qa/playwright-cli/NOTICE
  # rewrite SOURCE.md, then run the recipe's step 5
  ```
- Local changes: none. The upstream frontmatter is kept byte-identical, including the `allowed-tools` field where the upstream sets one. House overrides, if any, live in a separate `skills/qa/*-house-rules` skill (spec 4.5 precedence); none exists today.
