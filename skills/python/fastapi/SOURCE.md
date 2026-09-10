# SOURCE
- Upstream: https://github.com/fastapi/fastapi
- Subtree: fastapi/.agents/skills/fastapi (the skill sits under the `fastapi/` package directory of the monorepo, so the sparse path starts with `fastapi/`)
- Commit: 50113da16fec53b66b80d75e80a89296de4fa5a5 (untagged from this skill's point of view; the repo tags releases of the library, not of the skill, so this SHA is the pin), committed 2026-09-01 UTC
- Vendored: 2026-09-10, plan 2026-09-10-stack-skills Task 10
- License: MIT; LICENSE alongside, copied from the upstream repository root `LICENSE`; the upstream root has no NOTICE, so none is copied
- Refresh:
  ```bash
  S=<scratch>; P=$(git rev-parse --show-toplevel)   # run from anywhere inside this repo
  git clone --filter=blob:none --no-checkout https://github.com/fastapi/fastapi $S/fastapi
  cd $S/fastapi && git sparse-checkout init --cone && git sparse-checkout set fastapi/.agents/skills/fastapi
  git checkout 50113da16fec53b66b80d75e80a89296de4fa5a5
  rsync -a --delete --exclude .git $S/fastapi/fastapi/.agents/skills/fastapi/ $P/skills/python/fastapi/
  cp $S/fastapi/LICENSE $P/skills/python/fastapi/LICENSE
  # rewrite SOURCE.md, then run the recipe's step 5
  ```
- Local changes: none. House overrides, if any, live in a separate `skills/python/*-house-rules` skill (spec 4.5 precedence); none exists for FastAPI today.
