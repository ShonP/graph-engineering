---
name: ruff
description: Use when configuring or changing a Python project's lint and format rules, adding a banned-api rule, excluding a file from linting, wiring lint into a hook or CI step, or reviewing a diff that adds a `# noqa`. Covers rule selection that survives a codebase, banning symbols rather than modules, the exclude/force-exclude pair that makes a deliberate red control possible, and per-file invocation.
license: MIT
---

# ruff

Written for **ruff 0.16.8** (PyPI, uploaded 2026-09-16; the `==0.16.8` pin in `forge-libs`'
`uv.lock`). docs.astral.sh serves only the latest docs, so every citation below is the
source of that page **at the `0.16.8` tag** (fetched 2026-09-23, all HTTP 200):

- https://github.com/astral-sh/ruff/blob/0.16.8/docs/configuration.md - "Configuring Ruff"
- https://github.com/astral-sh/ruff/blob/0.16.8/crates/ruff_workspace/src/options.rs - the
  settings reference is generated from these doc comments (`force-exclude`, `src`, ...)
- https://github.com/astral-sh/ruff/blob/0.16.8/crates/ruff_linter/src/rules/flake8_tidy_imports/rules/banned_api.rs - TID251
- https://github.com/astral-sh/ruff/blob/0.16.8/docs/formatter.md - "The Ruff Formatter"
- https://docs.astral.sh/ruff/rules/blanket-noqa/ - PGH004 (verified against 0.16.8 by run)

In-house measurement: **ADR 0021** = `Equival-io/forge-platform`
`docs/adr/0021-temporal-converter-and-test-env.md`, "The lint: which `@dataclass` spellings
ruff alone misses" (a private repo; the matrix is quoted below where it is load-bearing) — a
thirteen-row matrix run against two real configurations. Every rule below that says
"measured" points there, and it is rung 1 evidence: code that was run, not a docs claim.

## When to apply

- Editing `[tool.ruff]`, `[tool.ruff.lint]` or any of its sub-tables.
- Adding a rule the house wants enforced, especially a **ban** on an import or an API.
- Excluding a file, or writing a fixture that is *supposed* to fail the lint.
- Wiring lint into a PostToolUse hook, a `lint` entry point, or CI.
- Reviewing a diff that adds `# noqa`, widens `select`, or adds an `extend-exclude` entry.

## Rules

### Configuration lives in `pyproject.toml`

- One `[tool.ruff]` table in the project's `pyproject.toml`, not a separate `ruff.toml` and
  not both. Ruff reads `pyproject.toml` only when it contains a `[tool.ruff]` section, and a
  `.ruff.toml`/`ruff.toml` beside it **takes precedence** over the `pyproject.toml` table —
  so two files is a silent override, not a merge (`configuration.md` at 0.16.8).
- Set `line-length` and `src` explicitly. `src` is what makes first-party import sorting (`I`)
  correct; without it a `src/` layout gets its own packages sorted as third-party
  (`options.rs` at 0.16.8, `src`).

### Select deliberately, and write down why

- **Name the rule sets you want; do not reach for `select = ["ALL"]`.** `ALL` is the
  advice most public ruff configs give and it does not survive contact with a codebase: it
  enables every rule including ones that conflict with the formatter and ones nobody has
  audited the repo against, so the first run is a backlog and the second is a pile of
  `# noqa`. A rule people silence is gone (ADR 0021, "The lint").
- Each selected set carries a comment saying what it buys. The house set is
  `["E", "F", "I", "B", "UP", "ASYNC", "S", "TID251"]` — pycodestyle/pyflakes, import order,
  bugbear, pyupgrade, blocking-call-in-async, the bandit subset that needs no config, and
  one banned-api rule.
- **Turn a security set on before the modules that need it land, not after.** `S` catches a
  hardcoded secret (S105-S107), an `assert` used as a runtime guard (S101), `subprocess`
  with `shell=True` (S602) and an unverified TLS call (S501). Enabling it once the auth, db
  and outbound-HTTP modules already exist means enabling it against a backlog.
- **Select `TID251`, not the `TID` category.** The category also brings TID252
  (relative imports) and TID253 (banned module-level imports), neither of which the repo has
  been audited for; selecting the category turns two unaudited rules on by accident.

### Ban SYMBOLS, not modules

This is the rule this skill exists for, and it was decided by measurement rather than taste
(ADR 0021, "The lint").

- `[tool.ruff.lint.flake8-tidy-imports.banned-api]` keys are dotted paths, and a **module**
  key bans every name under it while a **symbol** key bans exactly that name
  (`banned_api.rs` at 0.16.8).
- **Ban the symbol.** Banning the `dataclasses` module also flags
  `from dataclasses import replace`, and `dataclasses.replace(...)` is the supported
  composition for adapting a third-party object (in `forge-libs`, adding `external_storage`
  to Temporal's `pydantic_data_converter`). A rule that flags borrowed, correct code gets
  `# noqa`'d on day one.
- Measured coverage, from the thirteen-row matrix: the symbol ban catches **seven**
  spellings — `from`-import, module attribute, aliased symbol, aliased module, the
  `pydantic.dataclasses` pair, and the functional `make_dataclass` API. The module ban
  catches those seven **plus `from dataclasses import *`** — eight — and pays for the
  eighth with the `replace` false positive above. The house takes the symbol ban and
  catches the star import with an AST check instead (`forge-libs`
  `tools/forge_libs_dev/no_dataclass.py`), so the house lint catches eight with no false
  positive. **Four escape both configurations**, and really are dataclasses at runtime:
  `__import__("dataclasses").dataclass`, `importlib.import_module("dataclasses").dataclass`,
  a house module that re-exports the symbol, and `class Payload(SomeDataclass)` — inherited,
  with no decorator in the file at all.
- **Say that out loud in the config.** A ban is a guard rail, not a sandbox; the reviewer is
  the backstop. A team that believes the lint is complete stops looking.
- Reach past ruff for the two spellings worth catching statically — a star import and a
  same-file inherited dataclass are both a short `ast` walk (that `no_dataclass.py`) — and
  leave the genuinely dynamic ones to review.
- **Every ban carries a `msg` that names the replacement and the one sanctioned way out.**
  A ban that only says "banned" gets worked around; one that says what to use instead gets
  followed. The escape hatch is a *narrow* `# noqa` with a reason beside it —
  `# noqa: TID251  # framework adapter exception: <the library call that forces it>` —
  never a bare `# noqa`, which silences every rule on that line forever.

### Excluding a file, and the red control that proves the lint works

- `exclude`/`extend-exclude` name **files or directories**; prefer naming the single file.
  Excluding the directory means the next fixture added beside it is silently unlinted,
  whereas a file entry leaves the default (lint it) in place for everything new.
  (`options.rs` at 0.16.8, `extend-exclude`).
- **`force-exclude` defaults to `false`, and that default is load-bearing.** Verbatim from
  the `force_exclude` doc comment in `options.rs` at 0.16.8: "Typically, Ruff will lint any
  paths passed in directly, even if they would typically be excluded." So a file on
  `extend-exclude` is skipped by the bare `ruff check` sweep and **still checked when named
  on the command line**.
- That pair is what lets a repo keep a **deliberate violation as a live test**: a fixture
  that breaks the rule, excluded so the default sweep stays green, and asserted red by
  naming it directly. A lint rule whose failure has never been observed is not known to
  fire — this is the cheapest way to observe it. Set `force-exclude = true` only for
  pre-commit, which passes every changed file explicitly.
- `per-file-ignores` is the right tool for a directory with genuinely different rules (a
  spikes tree, a tests tree). Narrow each entry to the smallest path that needs it and
  comment the reason; `per-file-ignores` on `src/**` is a rule deletion wearing a path.

### Format, and how lint is invoked

- The formatter is a separate command from the linter: `ruff format` writes,
  **`ruff format --check`** only reports and exits non-zero on a file that would change.
  CI and the `lint` entry point use `--check`; nothing in an automated path rewrites files
  (`formatter.md` at 0.16.8).
- If you select formatter-conflicting rules, the docs list them and
  `ruff format` will fight `ruff check --fix` over them. Narrow `select` avoids the
  question entirely.
- **Lint must accept a single file path.** An editor hook lints the file just edited, so the
  project's `lint` entry point takes optional paths and falls back to the default sweep when
  given none. A `lint` script hardcoded to `.` turns a per-file hook into a whole-repo run on
  every keystroke-sized edit.
- **A project that declares no `lint` entry point gets no lint from the hook, silently.**
  graph-engineering's PostToolUse hook runs `uv run lint <file>` only when `[project.scripts]`
  declares `lint`; with no such script it exits 0 and says nothing. In a uv **workspace**,
  the nearest `pyproject.toml` to an edited file is the member's, and a member that ships no
  entry point is exactly this case — see `hooks/scripts/resolve_touched_project.py`, which
  walks past a scriptless `pyproject.toml` to a same-kind ancestor for this reason.

## Anti-patterns

- **`select = ["ALL"]`.** Every rule, including unaudited and formatter-conflicting ones.
  The first run produces a backlog and the fix is always a widening `ignore` list.
- **Banning a module when you meant a symbol.** It flags the legitimate sibling API
  (`dataclasses.replace`) to buy one spelling — the star import — that a ten-line `ast`
  check catches without the false positive (measured, ADR 0021: seven vs eight).
- **Believing the ban is complete.** Four spellings reach a real dataclass past both
  configurations. State the limit where the rule is written.
- **A bare `# noqa`.** It disables every current and future rule on that line. Use
  `# noqa: <CODE>` with a comment naming the reason; `PGH004` enforces it.
- **A `msg` that does not name the replacement.** "X is banned" leaves the author to guess,
  and guessing produces the `# noqa`.
- **Excluding a directory to hide one file.** The next file added there is unlinted and
  nobody finds out.
- **`force-exclude = true` outside pre-commit.** It removes the "named directly is still
  checked" behaviour, and with it the ability to keep a deliberate red control.
- **A `lint` script that ignores its arguments.** The per-file hook silently becomes a
  full-repo lint, and the feedback that was supposed to be immediate is not.
- **Two config files.** `ruff.toml` beside a `[tool.ruff]` in `pyproject.toml` means the
  `pyproject.toml` table is ignored, with no warning.

## Verify

```bash
# 1. The version the config was written against.
uv run ruff --version
# expect: the pinned version, e.g. ruff 0.16.8

# 2. Ruff sees exactly one config, and it is the one you think.
uv run ruff check --show-settings . 2>/dev/null | head -3
# expect the resolved settings to open on this project's pyproject.toml

# 3. The default sweep is green, and the formatter agrees.
uv run ruff check .
uv run ruff format --check .
# expect: "All checks passed!" and "N files already formatted", exit 0 both

# 4. The ban actually fires. Name the deliberately-violating fixture DIRECTLY — the bare
#    sweep skips it via extend-exclude, and force-exclude=false is why naming it still works.
uv run lint tests/fixtures/has_dataclass.py; echo "exit=$?"
# expect exit=1 and the rule code on the offending line, e.g.
#   TID251 `dataclasses.dataclass` is banned: <the msg, naming the replacement>
#     --> tests/fixtures/has_dataclass.py:14:25
# A green here means the fixture stopped violating, the exclude became a directory, or
# force-exclude was turned on. All three are bugs in the guard, not passes.

# 5. The sweep still skips it, so the red control costs the default run nothing.
uv run lint >/dev/null; echo "exit=$?"
# expect exit=0

# 6. No bare `# noqa` anywhere: every suppression names its rule. PGH004 reads comments
#    from ruff's tokenizer, so a docstring that MENTIONS "# noqa" is not a hit (a grep is).
uv run ruff check --select PGH004 src tools tests; echo "exit=$?"
# expect "All checks passed!" exit=0; on `import os  # noqa` it prints
#   PGH004 Use specific rule codes when using `noqa`   and exit=1

# 7. Lint takes a single file, the way the editor hook calls it.
uv run lint src/<some_module>.py; echo "exit=$?"
# expect exit=0 and a per-file run, not a whole-repo sweep
```
