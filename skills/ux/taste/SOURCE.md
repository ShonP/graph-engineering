# SOURCE
- Upstream: https://github.com/Leonxlnx/taste-skill (site https://www.tasteskill.dev/), a Claude Code plugin marketplace whose plugin `taste-skill` ships the skill `design-taste-frontend`
- Tag: v2.1.4
- Commit: 6010f91a9935f1c167dfc500fb1a475681892e6b, committed 2026-10-20 UTC
- License: MIT (Copyright 2026 Leonxlnx)
- Not vendored: upstream maintains it as a plugin (Node 22 and Chrome scripts, a direction library). Consumers install it at project scope pinned to the tag above (`SKILL.md`, "Install"); `SKILL.md` here is house text and copies nothing.
- At the pin: no hooks and no MCP servers in the plugin; `scripts/assets.mjs` uses the network to fetch pictures.
- Refresh: read the upstream diff from this tag to the new one (look for hooks, MCP servers, new network calls), then change the tag here, the `ref` in `SKILL.md` and in `README.md`, and the commit line, and run `bash scripts/run-all-tests.sh`.
