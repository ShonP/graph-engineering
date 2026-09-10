# SOURCE
- Upstream: https://github.com/temporalio/skill-temporal-developer
- Subtree: repository root (whole repo, minus `.git/` and `.github/`)
- Commit: 2d7fda32ffbf71106c65c98478ee1031aca1b65b (tag `v0.6.2`), committed 2026-09-04 UTC
- Vendored: 2026-09-10, plan 2026-09-10-stack-skills Task 6
- License: MIT; LICENSE alongside, in-tree at the upstream root; the upstream root has no NOTICE, so none is copied
- Refresh:
  ```bash
  S=<scratch>; P=$(git rev-parse --show-toplevel)   # run from anywhere inside this repo
  git clone --filter=blob:none --no-checkout https://github.com/temporalio/skill-temporal-developer $S/skill-temporal-developer
  git -C $S/skill-temporal-developer checkout 2d7fda32ffbf71106c65c98478ee1031aca1b65b
  rsync -a --delete --exclude .git --exclude .github $S/skill-temporal-developer/ $P/skills/temporal/temporal-developer/
  # LICENSE is in-tree; rewrite SOURCE.md, then run the recipe's step 5
  ```
- Local changes: none. `.github/**` (2 files) is excluded as CI belonging to the upstream repo, not to the skill. House overrides, if any, live in `skills/temporal/temporal-house-rules` (spec 4.5 precedence); none exists today.
- Note for Task 9: `references/python/data-handling.md` is the Pydantic data-converter reference that `skills/python/pydantic-house-rules` cites.
