# SOURCE
- Upstream: https://github.com/grafana/skills
- Subtree: skills/grafana-lgtm/tempo
- Commit: 51d33e71e191b409bbd25fc7be2684c610d18166 (untagged; the repo has zero git tags, which is why the plan vendors instead of declaring a plugin dependency), committed 2026-08-18
- Vendored: 2026-09-10, plan 2026-09-10-stack-skills Task 16
- License: Apache-2.0 (also declared in the skill's own frontmatter `license:` field); LICENSE alongside, copied from the upstream repository root `LICENSE`; the upstream root has no NOTICE file, checked at this SHA, so Apache-2.0 section 4(d) adds nothing to carry
- Refresh:
  ```bash
  S=<scratch>; P=/Users/shonpazarker/projects/graph-engineering
  git clone --filter=blob:none --no-checkout https://github.com/grafana/skills $S/grafana-skills
  cd $S/grafana-skills && git sparse-checkout init --cone && git sparse-checkout set skills/grafana-lgtm/tempo
  git checkout 51d33e71e191b409bbd25fc7be2684c610d18166
  rsync -a --delete --exclude .git $S/grafana-skills/skills/grafana-lgtm/tempo/ $P/skills/observability/tempo/
  cp $S/grafana-skills/LICENSE $P/skills/observability/tempo/LICENSE
  # rewrite SOURCE.md, then run the recipe's step 5
  ```
- Local changes: none. The plugin wrapper is not vendored; only the skill directory is. House overrides, if any, live in a separate `skills/observability/*-house-rules` skill (spec 4.5 precedence); none exists today.
