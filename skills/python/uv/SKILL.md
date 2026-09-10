---
name: uv
description: Use when a Python project has a pyproject.toml, a uv.lock or a .python-version, when adding or removing dependencies, or when writing a CI step or Dockerfile that installs Python dependencies. Covers project layout, dependency groups, locking and syncing, interpreter pinning and workspaces.
license: MIT
---

# uv

Sources (fetched 2026-09-10 with curl; docs site serves the latest release, uv
0.12.12, published 2026-09-09 per the GitHub releases API; the machine this was
written on had `uv 0.9.16 (a63e5b62e 2025-12-06)` installed, so a few pages
describe behaviour newer than that binary and the rules below say where):

- https://docs.astral.sh/uv/concepts/projects/ - "Projects | uv"
- https://docs.astral.sh/uv/concepts/projects/layout/ - "Structure and files | uv"
- https://docs.astral.sh/uv/concepts/projects/init/ - "Creating projects | uv"
- https://docs.astral.sh/uv/concepts/projects/dependencies/ - "Managing dependencies | uv"
- https://docs.astral.sh/uv/concepts/projects/run/ - "Running commands | uv"
- https://docs.astral.sh/uv/concepts/projects/sync/ - "Locking and syncing | uv"
- https://docs.astral.sh/uv/concepts/projects/workspaces/ - "Using workspaces | uv"
- https://docs.astral.sh/uv/concepts/python-versions/ - "Python versions | uv"
- https://docs.astral.sh/uv/reference/cli/ - "Commands | uv"

House rule: uv is the package manager for every Python project here. Model and
DTO shape is not this skill's business; that is `pydantic-house-rules`.

## When to apply

- Any repository holding a `pyproject.toml`, `uv.lock`, `.python-version` or `uv.toml`.
- Adding, removing, upgrading or grouping a Python dependency.
- Writing a CI install step, a Dockerfile or a Taskfile target for a Python service.
- Choosing or pinning the interpreter for a project.
- Splitting a Python repo into several packages (workspaces).

## Rules

**Project files**

- `pyproject.toml` is what marks the project root; uv requires it to find the
  project. A minimal one is `[project]` with `name` and `version`.
  (https://docs.astral.sh/uv/concepts/projects/layout/)
- `uv.lock` sits next to `pyproject.toml`, is committed to version control, and
  is never hand edited: it is "a universal or cross-platform lockfile", "managed
  by uv and should not be edited manually".
  (https://docs.astral.sh/uv/concepts/projects/layout/)
- `.venv` lives next to `pyproject.toml` and stays out of version control; uv
  excludes it with an internal `.gitignore`. Do not modify it by hand.
  (https://docs.astral.sh/uv/concepts/projects/layout/)
- Create projects with `uv init` (application by default, `--lib` for a
  library). Both templates use a `src/<project_name>/` layout and define a build
  system; `--no-package` or `--bare` opts out. Applications only get a default
  build system from uv 0.12 onward, so check what your uv version wrote.
  (https://docs.astral.sh/uv/concepts/projects/init/)

**Dependencies**

- Change dependencies with `uv add` and `uv remove`; both edit `pyproject.toml`
  and the lockfile in one step. `uv add httpx` writes a bound such as
  `httpx>=0.27.2`; adjust it with `--bounds` or state the constraint yourself.
  (https://docs.astral.sh/uv/concepts/projects/dependencies/)
- Runtime dependencies go in `project.dependencies`; published extras in
  `project.optional-dependencies`; local-only development dependencies in
  `[dependency-groups]` (PEP 735) via `uv add --dev` or `uv add --group <name>`.
  Development groups are never published.
  (https://docs.astral.sh/uv/concepts/projects/dependencies/)
- The `dev` group is special-cased and synced by default; other groups need
  `--group <name>` or `--all-groups`, and exclusions beat inclusions
  (`uv sync --no-group foo --group foo` installs nothing from `foo`).
  (https://docs.astral.sh/uv/concepts/projects/sync/)
- A dependency that does not come from a package index (git, url, path,
  workspace member, a specific index) gets a `tool.uv.sources` entry. Pin git
  sources with `--tag` or `--rev`, not a branch: uv prefers the locked commit
  for a branch source but `--upgrade` moves it.
  (https://docs.astral.sh/uv/concepts/projects/dependencies/)
- `tool.uv.sources` is uv-only. Any other tool reading the project sees only the
  standard tables, so a source-only dependency must be restated for that tool.
  (https://docs.astral.sh/uv/concepts/projects/dependencies/)
- Platform-specific and version-specific dependencies use environment markers
  (`uv add "jax; sys_platform == 'linux'"`), not an `if` at import time.
  (https://docs.astral.sh/uv/concepts/projects/dependencies/)

**Locking and syncing**

- Locking and syncing are automatic: `uv run` locks and syncs before running the
  command, so the environment matches the lock without a manual step.
  (https://docs.astral.sh/uv/concepts/projects/sync/)
- `--locked` asserts the lockfile is already up to date and errors instead of
  updating it. `--frozen` uses the lockfile without checking it at all. Use
  `--locked` where a stale lock must fail the build (CI install, release job);
  `--frozen` only where a separate step already proved freshness (an image build
  layered on a checked lock).
  (https://docs.astral.sh/uv/concepts/projects/sync/,
  https://docs.astral.sh/uv/reference/cli/)
- The drift gate is `uv lock --check`, "equivalent to the `--locked` flag for
  other commands". `uv sync --check` is its environment-side twin: it checks
  whether the environment matches the project.
  (https://docs.astral.sh/uv/concepts/projects/sync/,
  https://docs.astral.sh/uv/reference/cli/)
- Upgrades are explicit. A new release upstream does not make a lockfile
  outdated; only a metadata change does. Move versions with `uv lock --upgrade`
  or, preferably, `uv lock --upgrade-package <name>`, inside the declared
  constraints.
  (https://docs.astral.sh/uv/concepts/projects/sync/)
- `uv sync` is exact by default and removes packages not in the lockfile;
  `uv run` is inexact by default. When a job must prove the environment holds
  nothing extra, sync (or `uv run --exact`), do not assume.
  (https://docs.astral.sh/uv/concepts/projects/sync/)
- For image layer caching, split the install: `uv sync --no-install-project`
  (dependencies only) as one layer, then a full `uv sync` after the source is
  copied. Dependencies of the skipped target are still installed, and misuse of
  these flags leaves a broken environment, so end with a full sync.
  (https://docs.astral.sh/uv/concepts/projects/sync/)
- `uv export --format requirements.txt|pylock.toml|cyclonedx1.5` exists for
  tools that cannot read `uv.lock`. Treat the export as a generated artifact of
  the lock, never as an input.
  (https://docs.astral.sh/uv/concepts/projects/sync/)
- Supply chain: uv can check the lockfile against OSV malware advisories and
  terminate the sync on a hit, with `audit.malware-check = true` or
  `UV_MALWARE_CHECK=1`. It is a preview feature as of these docs, so enable it
  deliberately and record the uv version.
  (https://docs.astral.sh/uv/concepts/projects/sync/)

**Running code**

- Run every command through `uv run` (`uv run pytest`, `uv run python -c ...`,
  `uv run bash scripts/foo.sh`). The project environment is isolated from the
  shell, so a bare `python -c "import example"` fails by design.
  (https://docs.astral.sh/uv/concepts/projects/run/)
- One-off tools and one-off versions use `uv run --with <pkg>` or `uvx`, which
  do not touch the project's dependencies.
  (https://docs.astral.sh/uv/concepts/projects/run/,
  https://docs.astral.sh/uv/concepts/projects/layout/)
- A standalone script declares its own dependencies in PEP 723 inline metadata
  and `uv run script.py` executes it in an isolated environment. Do not add a
  script's dependency to the project to make the script run.
  (https://docs.astral.sh/uv/concepts/projects/run/)

**Interpreter**

- Declare `requires-python` in `pyproject.toml`; uv honours it on every project
  command and picks the first compatible interpreter.
  (https://docs.astral.sh/uv/concepts/python-versions/)
- Pin the concrete version with a `.python-version` file, created by
  `uv python pin`; uv searches the working directory and its parents and stops
  at the project or workspace boundary. Use a plain version number so other
  tools can read it.
  (https://docs.astral.sh/uv/concepts/python-versions/)
- Available Python versions are frozen per uv release, so bumping the
  interpreter can require bumping uv. Pin the uv version in CI alongside the
  Python version. (https://docs.astral.sh/uv/concepts/python-versions/)

**Workspaces**

- A monorepo of Python packages is a workspace: `tool.uv.workspace` with
  `members` (and optional `exclude`) globs in the root `pyproject.toml`, one
  shared `uv.lock` for all members. Every member directory must hold a
  `pyproject.toml`.
  (https://docs.astral.sh/uv/concepts/projects/workspaces/)
- Depend on a sibling with `<name> = { workspace = true }` in
  `tool.uv.sources`, never a relative path install.
  (https://docs.astral.sh/uv/concepts/projects/workspaces/)
- `uv lock` covers the whole workspace; `uv run` and `uv sync` default to the
  root and take `--package <member>` to target one member from anywhere.
  (https://docs.astral.sh/uv/concepts/projects/workspaces/)

## Anti-patterns

- `pip install` or `uv pip install` into a project's `.venv`. The docs call
  modifying the project environment manually "not recommended"; the failure is an
  environment that satisfies nobody's lockfile and a green local run that dies
  in CI. Use `uv add`, or `uv run --with` for a one-off.
  (https://docs.astral.sh/uv/concepts/projects/layout/)
- Committing a `pyproject.toml` dependency change without the regenerated
  `uv.lock`. Failure: every `--locked` consumer fails the build, and every
  `--frozen` consumer silently installs the old resolution.
- Treating `requirements.txt` (or an exported `pylock.toml`) as the source of
  truth. Failure: two dependency graphs drift apart and the deployed one is the
  unreviewed one.
- `source .venv/bin/activate` or a bare `python` in CI, a Taskfile or a
  Dockerfile entrypoint. Failure: the command runs against whatever the
  environment last held rather than the lock.
- `--frozen` everywhere, including the gate. Failure: nothing ever checks the
  lock, so a stale lock ships. Keep one `uv lock --check` (or a `--locked`
  install) on the critical path.
- Editing `uv.lock` by hand to resolve a conflict. Failure: an unresolvable file
  uv will rewrite anyway; re-run `uv lock` instead.
- A git dependency on a branch with no `--tag` or `--rev`. Failure: the next
  `--upgrade` silently moves production code.
- Adding a development-only tool (pytest, ruff, mypy) to
  `project.dependencies`. Failure: it ships to every consumer of the package.
  Use `uv add --dev` or a named group.

## Verify

```bash
uv --version                       # record it; behaviour differs across minors
uv lock --check                    # exit 0: lockfile matches pyproject.toml
uv sync --locked                   # exit 0: environment installed from that lock
uv run python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'
cat .python-version                # must agree with the line above
uv sync --check                    # exit 0: environment matches the project
```

Expected: `uv lock --check` and `uv sync --locked` both exit 0 and print no
resolution changes; the interpreter printed by `uv run` matches
`.python-version`. A non-zero `uv lock --check` means the lock is stale: run
`uv lock` and commit the result, do not switch the command to `--frozen`.
