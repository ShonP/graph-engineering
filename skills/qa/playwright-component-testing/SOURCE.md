# SOURCE
- Upstream: https://github.com/microsoft/playwright
- Subtree: packages/playwright-core/src/tools/skills/playwright-component-testing
- Commit: af74c938e45f3e759dc2521993f201389eb16cb6 (untagged from this skill's point of view; the repo tags releases of the library, not of the skills, so this SHA is the pin), committed 2026-09-10 UTC (2026-09-09T17:19:41-07:00 committer time)
- Vendored: 2026-09-10, plan 2026-09-10-stack-skills Task 14
- License: Apache-2.0; LICENSE alongside, copied from the upstream repository root `LICENSE`; NOTICE alongside, copied from the upstream repository root `NOTICE`, because Apache-2.0 section 4(d) requires the NOTICE text to travel with every redistribution
- Refresh:
  ```bash
  S=<scratch>; P=$(git rev-parse --show-toplevel)   # run from anywhere inside this repo
  git clone --filter=blob:none --no-checkout https://github.com/microsoft/playwright $S/playwright
  cd $S/playwright && git sparse-checkout init --cone && git sparse-checkout set packages/playwright-core/src/tools/skills
  git checkout af74c938e45f3e759dc2521993f201389eb16cb6
  rsync -a --delete --exclude .git $S/playwright/packages/playwright-core/src/tools/skills/playwright-component-testing/ $P/skills/qa/playwright-component-testing/
  cp $S/playwright/LICENSE $P/skills/qa/playwright-component-testing/LICENSE
  cp $S/playwright/NOTICE $P/skills/qa/playwright-component-testing/NOTICE
  # rewrite SOURCE.md, then run the recipe's step 5
  ```
- Local changes: none. The upstream frontmatter is kept byte-identical.
- Grant: this skill's frontmatter sets no `allowed-tools`, so it grants nothing on its own. The sibling `playwright-cli` and `playwright-trace` skills vendored from the same upstream do; the note below applies to them and is repeated here so a reader of any one of the three sees the same ruling.
- Tool grant, and how it is closed: `allowed-tools` lets the skill run those commands without a permission prompt for the turn that invokes it, and workspace trust does not gate the field. A sibling `*-house-rules` skill cannot narrow it: a skill's `allowed-tools` (and `disallowed-tools`) apply only while that same skill is active, so spec 4.5 precedence has no purchase on this field. The binding control is a host permission rule, because a matching `ask` or `deny` rule aborts the invocation regardless of `allowed-tools`. This plugin's recommendation, shipped in the README and the `/graph-init` output by Task 18, is:

  ```json
  { "permissions": { "ask": ["Bash(npx:*)", "Bash(npm:*)"] } }
  ```

  That restores the prompt on the two commands worth prompting on while leaving the skill fully usable. Not registering the skill is the other control. Editing the vendored file is not: it would break the refresh contract and the Apache-2.0 provenance.
