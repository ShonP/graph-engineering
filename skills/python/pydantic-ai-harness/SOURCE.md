# SOURCE
- Upstream: https://github.com/pydantic/skills
- Subtree: plugins/pydantic-ai-harness/skills/pydantic-ai-harness
- Commit: 9e9390ee24d44b32cf5379c58acaebd7563f5f86 (untagged; the repo has zero git tags, so this SHA is the pin), committed 2026-09-01 UTC
- Vendored: 2026-09-10, plan 2026-09-10-stack-skills Task 8
- License: MIT; LICENSE alongside, copied from the upstream repository root `LICENSE`; the upstream root has no NOTICE, so none is copied
- Refresh:
  ```bash
  S=<scratch>; P=$(git rev-parse --show-toplevel)   # run from anywhere inside this repo
  git clone --filter=blob:none --no-checkout https://github.com/pydantic/skills $S/skills
  cd $S/skills && git sparse-checkout init --cone && git sparse-checkout set plugins/pydantic-ai-harness/skills/pydantic-ai-harness
  git checkout 9e9390ee24d44b32cf5379c58acaebd7563f5f86
  rsync -a --delete --exclude .git $S/skills/plugins/pydantic-ai-harness/skills/pydantic-ai-harness/ $P/skills/python/pydantic-ai-harness/
  cp $S/skills/LICENSE $P/skills/python/pydantic-ai-harness/LICENSE
  # rewrite SOURCE.md, then run the recipe's step 5
  ```
- Local changes: none. The plugin wrapper (`.claude-plugin/plugin.json` and the plugin README) is deliberately not vendored; only the skill directory is.
