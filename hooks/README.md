# Plugin hooks

Three hooks ship with `graph-engineering`. They are generic: they key on the
script names `test`, `lint` and `typecheck` across three project conventions, and
on `docs/HANDOFF.md`. Nothing in them is specific to one repo.

| Event | Script | What it does | Exit codes |
| --- | --- | --- | --- |
| `PostToolUse`, matcher `Edit\|Write` | `scripts/lint-touched-file.sh` | Lints and typechecks the file Claude just wrote, and hands any findings back as context next to the tool result | `0` always. It informs, it never blocks |
| `Stop` | `scripts/test-before-stop.sh` | Runs the project's test script and holds the turn open until it is green | `2` with a short reason on stderr when the tests fail, `0` when they pass or when no test script applies |
| `SessionStart`, no matcher | `scripts/print-handoff.sh` | Prints the first 40 lines of `docs/HANDOFF.md` into the new session's context | `0` always |

## Detection order

Both working hooks find the project's script the same way, and stop at the first
convention that matches.

| Order | Project file | Condition | Command |
| --- | --- | --- | --- |
| 1 | `pyproject.toml` | the script is declared under `[project.scripts]` | `uv run <script>` |
| 2 | `package.json` | the script is declared under `scripts` | `<pm> run <script>` |
| 3 | `Taskfile.yml` | `task --list-all --silent` prints a line `test` | `task test` (`Stop` only) |

`<pm>` is chosen by lockfile: `pnpm-lock.yaml` gives `pnpm`, `yarn.lock` gives
`yarn`, `bun.lock` or `bun.lockb` gives `bun`, anything else gives `npm`.

Taskfiles are `Stop` only. A single-file lint or typecheck has no Taskfile shape,
so `PostToolUse` skips a Taskfile project in silence.

The file argument is passed with no `--` separator: measured on 2026-09-10,
npm 11.12.1 strips a leading `--` while pnpm 10.33.3 forwards it to the script as
a literal first argument, so the bare form is the one that behaves the same on
both. Open question, not a rule: yarn and bun were not measured, because neither
was installed on the machine where this was written. The bare form is what their
docs describe, but if a yarn or bun repo sees a mangled lint argument, that pair
is where to look first.

When nothing matches, or when the tool a project needs (`uv`, the package
manager, `task`) is not installed, the hook exits 0 and prints nothing.

## Scope and least privilege

- `PostToolUse` acts only when `tool_input.file_path` resolves to a path inside
  `$CLAUDE_PROJECT_DIR`. Both paths are canonicalised first, and containment
  requires a path separator, so a sibling directory that merely shares the
  project's name prefix is out. A file outside the project exits 0 with no
  command run, which is what keeps an edit inside a scratch clone of somebody
  else's repo from running that repo's scripts.
- Inside the project it walks up from the edited file to the nearest project
  file and no further than `$CLAUDE_PROJECT_DIR`.
- `Stop` looks in `$CLAUDE_PROJECT_DIR` only and does not walk.
- The only commands these hooks run are the project's own named scripts. Nothing
  is taken from the contents of the edited file, there is no `eval`, no shell
  interpolation of a path, and no network access.
- Enabling this plugin therefore means a repo's own `lint`, `typecheck` and
  `test` scripts run automatically in that repo. `SessionStart` also reads
  `docs/HANDOFF.md` into context. Treat both the way you treat opening an
  untrusted repo at all: a repo you would not run `task test` in is a repo whose
  hooks you should turn off before you open it.

## Dependencies

`bash` and `python3` only. `python3` parses the hook's JSON input and the
project files; no `jq`, no packages to install. A machine without `python3`
gets a silent exit 0 from every hook.

`uv`, the package manager and `task` are invoked only when the matching project
file is present and the tool is on `PATH`.

## The Stop loop, and its cap

The `Stop` hook blocks by exiting 2, and Claude Code hands Claude the stderr text
as the reason to keep going ("Stop decision control"). It keeps no counter of its
own, because the platform owns the cap: "Claude Code overrides the hook and ends
the turn after 8 consecutive blocks" ("Stop input"). The `stop_hook_active` flag
from the input is echoed into the reason line so the loop state is visible in the
transcript.

## Turning them off

There is no documented per-hook disable for a plugin's hooks. The documented
ways out, in order of least collateral damage:

- Let them no-op. A repo with no `test`, `lint` or `typecheck` script under any
  of the three conventions, and no `docs/HANDOFF.md`, never triggers a command.
- `claude plugin disable graph-engineering` turns off the plugin, hooks included
  (plugins reference, "plugin disable").
- `"disableAllHooks": true` in a settings file turns off every hook from every
  source for that scope (hooks reference, "Disable or remove hooks").

## Tests

```
bash hooks/tests/run-tests.sh
```

Runs from any working directory and needs nothing but `bash` and `python3`:
`uv`, `pnpm` and `task` are stubbed under `hooks/tests/fixtures/stubs/` and are
installed onto `PATH` inside the sandbox, so the suite never touches the real
tools or the network. It copies `hooks/tests/fixtures/` into a `mktemp`
directory, writes only there, removes it on the way out, and exits non-zero when
any case fails.

The fixtures are one mini project per convention (`py/` for `uv`, `node/` for
the package manager, `taskfile/` for `task`), one with no scripts at all
(`bare/`), and two whose scripts must never run: `outside/`, which stands for a
clone of somebody else's repo outside the project directory, and `py-evil/`,
which sits next to `py/` and shares its name prefix.

## Registration

`hooks/hooks.json` at the plugin root is the default location and loads with no
entry in `.claude-plugin/plugin.json`; the manifest's `hooks` key exists for
configs kept somewhere else (plugins reference, "Hooks" and "Component path
fields"). Note that `claude plugin validate <plugin dir>` reads this file, but
`claude plugin validate <repo root>` validates the marketplace manifest and does
not, so the JSON is checked here with `python3 -m json.tool`.

## Sources, fetched 2026-09-10

- https://code.claude.com/docs/en/hooks "Hooks reference - Claude Code Docs"
- https://code.claude.com/docs/en/plugins-reference "Plugins reference - Claude Code Docs"
- https://docs.astral.sh/uv/concepts/projects/run/ "Running commands | uv"
- https://taskfile.dev/reference/cli/ "Command Line Interface Reference | Task"
