# Plugin hooks

Six scripts ship with `graph-engineering`, registered in `hooks/hooks.json` as
eight handlers. They are generic: nothing in them names a repo, a stack or a
package manager. What to run is declared by the project in
`.claude/graph-checks.json`; how agents are tiered is declared in the project's
`.claude/graph-profile.yaml`. One more script, `scripts/wait-run.sh`, is not a
hook: agents call it by path to wait on a long suite (see wait-run below).

| Event, matcher | Script | Mode | What it does |
| --- | --- | --- | --- |
| `PostToolUse`, `Edit\|Write` | `scripts/lint-touched-file.sh` | `async`, timeout 130 | Runs the configured lint on the file Claude just wrote and hands findings back on the next turn. Exit `0` always: it informs, it never blocks |
| `PreToolUse`, `Bash` | `scripts/guard-destructive.sh` | sync, timeout 10, three handlers gated by `if` | Asks before a destructive command, with evidence. Never denies |
| `PreToolUse`, `Agent\|Task` | `scripts/guard-agent.sh` | sync, timeout 15 | Enforces the profile's `policy:` block on subagent calls |
| `Stop`, no matcher | `scripts/test-before-stop.sh` | `asyncRewake`, timeout 620 | Runs the configured test after the turn ends and wakes Claude only when it fails. On an unchanged tree it replays the stored verdict instead (`<git common dir>/graph-engineering/checks-state.json`); any nonempty `GRAPH_CHECKS_NO_MEMO` turns that off |
| `SessionStart`, `startup\|clear\|compact` | `scripts/print-handoff.sh` | sync, timeout 15 | Prints the head of `docs/HANDOFF.md` into the new context, a warning when that file is over 150 lines, the reply contract when the repo has a profile, and one line when a run's success measures are due. Silent on resume, fork and `--agent` sessions. Exit `0` always |
| `SessionStart`, `startup` | `scripts/doctor-on-start.sh` | sync, timeout 5 | Cached setup check: up to 3 lines of doctor findings, or a `/graph-init` hint. Silent when clean. Exit `0` always |

## Claude Code versions

Minimum Claude Code 2.1.271, tested on 2.1.285. Feature floors the registrations
lean on:

| Feature | Floor | Used by |
| --- | --- | --- |
| `if` on a hook handler | 2.1.85 | the three `guard-destructive.sh` handlers |
| `if` evaluated inside compound commands (`a && b`, `$(...)`) | 2.1.89 | the same handlers, so `npm test && git push` still matches |
| `background_tasks` in the Stop input | 2.1.145 | the Stop hook's skip while background work runs |

## Opt-in via `.claude/graph-checks.json`

The Stop and lint hooks do nothing until the repo commits this file. The shape:

- `version`: `1`.
- `test`, `precheck` and `lint` blocks, each optional. A block takes `argv` (a
  list, spawned directly with no shell) and `timeout_seconds`.
- `lint.argv` has exactly one `{file}` element, replaced with the edited file's
  path relative to the config's directory (the repo root, or a package). `lint.extensions` is required: only files with a
  listed extension are linted.
- Timeouts are at most 600 for `test`, 120 for `lint` and 60 for `precheck`.
- `precheck` is a cheap gate for what the test needs (a daemon, a database) so a
  missing dependency reads as not verified instead of as a red test.

A complete example is at `templates/graph-checks.json`; copy it to
`.claude/graph-checks.json` and edit the argv lists for the repo's own tools.

**Without the file, both hooks do nothing. This breaks 0.14 autodetect (removed in 0.15).**

Where the hooks look: first the hook binds a root, the repository (or linked
worktree) being worked on. Then the nearest `.claude/graph-checks.json` wins,
walking up from the edited file's directory (lint) or from the session's working
directory, then `CLAUDE_PROJECT_DIR` (Stop), and never above that root. The
command runs from the directory holding `.claude/`. So a package in a monorepo
keeps its own file even when Claude Code was launched inside it
(`CLAUDE_PROJECT_DIR` is the launch directory), a nested repo in a multi-repo
workspace and a linked worktree use their own, and a package directory maps
into the linked worktree Claude is working in. A package's file is also a
package's memo: its verdict is keyed by its path as well as the tree. When no
file is found the hook exits in bash before starting Python, so a repo that
never opted in is never told that Python 3.11+ is missing.

Removed in 0.15: the `uv run test` and `package.json` script lookups and the Taskfile lookup.
A repo that relied on them has to add the file to keep the Stop gate and the lint.

Why opt-in: a guessed command is the one a repo never chose. In the measured
sessions a script named `lint` ran the whole project for every edited file, and a
test script needed a daemon nobody had started. The repo now says exactly which
command proves its own work, and how long it may take.

## Stop: test before finishing

- Runs after the turn ends. `asyncRewake` starts it in the background, so the
  turn is never held open.
- Wakes Claude only when the tests fail (exit `2`, the output arrives as a
  system reminder). A pass or a clean skip is silent.
- At most once per prompt. While the input carries `stop_hook_active: true`, Claude
  is already continuing because of this hook, so it stands down.
- Skipped while `background_tasks` holds a running task: the session is paused for
  that work, not finished.
- A `precheck` failure or a timeout means not verified. That is neither a pass
  nor a failure: the hook exits `0` and does not wake Claude.
- No `if` on this entry. On a non-tool event a hook with `if` never runs
  (spike e, 2.1.285).

Why the hook keeps no block counter of its own. Spike c measured the harness cap:
it honours 8 consecutive blocks, then overrides silently, and the count resets
per prompt. An override that says nothing looks like completion, so the hook
never relies on the cap to end a loop. It stands down after one wake per prompt
and reports what it could not verify.

## Lint: async, by extension

- Registered `async`, so the edit returns immediately and the result is delivered
  on the next turn. Claude Code does not enforce the registered `timeout` on a
  plain async hook, so the `lint.timeout_seconds` bound (at most 120) is the one
  that applies.
- Filtered by extension before anything is spawned: an edit to a file whose
  extension is not in `lint.extensions` costs a shell `case`, not a process tree.
- When the configured runner is missing, typically in a fresh linked worktree
  with no dependencies installed, the hook reports `lint skipped` and exits `0`
  rather than failing the edit.
- Informational only. Stop and the merge gate are what block.

## Destructive-command guard

`guard-destructive.sh` asks, with the evidence it gathered, and never denies. The
human or the harness decides. It asks for:

- `git remote remove` and `git remote rm`.
- A force push without `--force-with-lease`.
- `docker volume rm` and `docker volume prune`.
- `docker system prune -a` and `docker system prune --volumes`.
- A recursive `rm` of `/`, `$HOME`, a repository root, a `.git` path or the Docker
  data directories.

Registration is three handlers, one per `if`: `Bash(git *)`, `Bash(rm *)` and
`Bash(docker *)`. The git rule is the whole tool, not `git push*`, because git
takes global options before the subcommand: `git -C <worktree> push -f` is how
worktree flows force-push, and `git -c k=v` and `git --no-pager` shift it the
same way. Spike e found that `if` holds exactly one permission rule; a pipe, a
brace or a list inside it matches nothing. A command that matches none of the
three never spawns the script, and a git command that never says `push` or
`remote` stops at the script's bash `case`. Because `if` is
best-effort (Claude Code runs the hook when it cannot parse the command), the
script re-checks the command itself. For a hard stop, put the fixed string in
`permissions.deny`; a hook is the wrong tool for an absolute rule.

## Agent policy guard

`guard-agent.sh` is a no-op unless the project's profile has a `policy:` block.
With one, it blocks dispatch to `general-purpose` and to any model listed in
`policy.never`, and it sets the role's model tier on `Agent` calls. The matcher is
`Agent|Task` because the tool has carried both names.

A line `policy-override: <reason>` in the call's prompt skips the guard for that
call, and the override and its reason are logged to `.graph/ledger.md`.

## SessionStart matcher

`startup|clear|compact`. Spike i found the matcher is an exact-string list against
the start source. `resume` and `fork` keep their existing context, so printing the
handoff again would only add a stale copy; a fresh session, a `/clear` and a
compaction lose it, so those three print.

The doctor entry is `startup` alone: setup does not change on a resume, a `/clear`
or a compaction, so checking once per fresh session is enough.

## SessionStart doctor

`doctor-on-start.sh` tells a fresh session when this repo's graph-engineering
setup is broken, and says nothing otherwise. It always exits `0`: any failure
(no `uv`, no Python 3.11+, a doctor error, output it cannot read) is silent.

- `CLAUDE_PROJECT_DIR` without a `.git`: silent, so home and scratch sessions
  pay nothing.
- No `.claude/graph-profile.yaml`: one line pointing the owner at `/graph-init`,
  but only when the project root holds a stack marker (`package.json`,
  `pyproject.toml`, `go.mod`, `Cargo.toml`, `Package.swift`, `build.gradle`,
  `build.gradle.kts`, `pom.xml`, `Gemfile`). Otherwise silent.
- A profile: runs `graph-control.py doctor --root <dir> --quick`, the subset of
  `/graph-doctor` that starts no process (no profile, an unreadable profile,
  `schema_version`, removed keys, missing `.claude/graph-checks.json`, plugin version differs from the
  installed one), and prints at most 3 lines,
  `graph-engineering doctor: <message> - fix: <fix>`, errors first. Run
  `/graph-doctor` for the full list.
- A clean result is cached in `$(git rev-parse --git-common-dir)/graph-engineering/doctor-cache`,
  one line per project directory (linked worktrees share the file), keyed by the
  plugin version and the mtimes of the profile and `.claude/graph-checks.json`. A
  hit exits before starting `uv`; editing either file or updating the plugin
  misses it. A run with findings is never cached, so they repeat until fixed.
  Delete the file to force a check.

## SessionStart: due success measures

A merged run can promise `success_signals` in its `plan.json` (schema 2): a
goal, an argv `command` that prints one aggregate, a `success_condition` and a
`window_days`. Long windows end days after the run, in a session that knows
nothing about it, so `print-handoff.sh` is the lazy trigger. After everything
else it prints, it may add

```
graph-engineering: <n> success measure(s) due (<run ids>). Run: python3 <plugin>/scripts/measure_signals.py .graph/<run>
```

- Only when a bash glob finds `.graph/*/plan.json` under `CLAUDE_PROJECT_DIR`.
  Without one no interpreter starts, so every repo that never ran a plan pays
  one glob.
- Then one Python call, `measure_signals.py --due <project dir>`, counts the
  signals whose window has elapsed since the ledger's `merged: <sha>` (the
  commit time from `git show -s --format=%cI`) and that have no row in that
  run's `measure.md`. It reads files and asks git for one date per run; it
  never runs a signal's command. No Python 3.11+, a malformed plan or an
  unmerged run: silent.
- Measuring is a separate, deliberate step: the owner or `/graph-ship` runs the
  printed command for a run, which writes `measure.md` and the ledger lines. The
  contract (sources, the aggregate-only output rule, `baseline.json`) is in the
  `post-deploy-verification` skill.

## wait-run: a bounded wait for long suites

Spike f (2.1.285): a foreground subagent's background jobs are killed when it
ends its turn, and a background subagent is re-woken only when its lead goes
idle. The harness also blocks a bare `sleep N`. So a suite longer than one tool
call runs through

```
<plugin root>/hooks/scripts/wait-run.sh --log <absolute path> [--max-block S] [-- <argv...>]
```

- With argv: starts it detached, then waits. Refused with exit `2` and `a job
  for this log is still running; call again without a command to attach` while
  `<log>.pid` names a live job that has not written `<log>.exit`.
- Without argv: attaches to the job for that log and waits.
- Blocks at most S seconds: default 270, so each return lands inside the
  5-minute worker cache; above 590 is clamped to 590. Give the Bash call a
  longer timeout than S (300000 ms for the default).
- Prints exactly one line,
  `wait-run: exit=<n>|running state=complete|partial elapsed=<s>s max_block=<S>s log=<path>`.
  `elapsed` is the job's age; `max_block` is S after clamping. A completed job
  with a nonzero exit adds the last 20 lines of the log, at most 2000 characters.
- Exit: the job's code when complete (128+N when signal N killed it, 127 when
  argv could not start), `75` (EX_TEMPFAIL) when still running, `2` on a usage
  error, a refusal, no job for the log, or a job that died without writing an
  exit code. Errors print no summary line, which tells them from a job that
  itself exited 2 or 75.
- Beside the log: `<log>.pid`, the supervisor's pid and the job's process
  group (`kill -- -"$(cat <log>.pid)"` stops the job), and `<log>.exit`. Each
  start truncates the log. All three are created mode 0600, and a symlink in
  their place is refused rather than followed. Keep the log outside the
  worktree, in the run directory or a temp dir, so it never lands in a commit.
- Why the job survives its caller: a double fork with `setsid` reparents the
  supervisor to init in its own session, and it closes every descriptor above
  2. A process-group kill or a tree kill of the caller does not reach it, and a
  harness waiting for EOF on its pipes is not held open by it.
- Argv is spawned directly, with the caller's working directory and
  environment and stdin from `/dev/null`: no shell, no network. The logic is
  `scripts/wait_run.py`, stdlib only, run by the interpreter
  `python-runtime.sh` selects.

## Scope and least privilege

- The only commands these hooks run are the argv arrays committed in
  `.claude/graph-checks.json`, each spawned directly. There is no `eval`, no shell
  interpolation of a path (`{file}` is a whole argv element) and no network access.
- Nothing is taken from the contents of an edited file.
- Linked Git worktrees resolve through their common Git directory, including nested
  worktrees. A different repository in a Stop event fails with a binding error.
- `doctor-on-start.sh` runs only the plugin's own pinned helper, which reads the
  profile and `.claude/graph-checks.json` and executes neither; it writes only
  its cache file inside the repo's Git directory.
- Enabling this plugin therefore means a repo's own committed checks run
  automatically in that repo. `SessionStart` also reads `docs/HANDOFF.md` into
  context. Treat that the way you treat opening any untrusted repo: a repo whose
  checks you would not run by hand is a repo whose hooks you turn off first.
- The due-measures line reads `.graph/<run>/plan.json`, `measure.md` and
  `ledger.md` and runs `git show` for a commit date. A signal's `command` runs
  only when someone runs `scripts/measure_signals.py` by hand or from a run.

## Dependencies

`bash` and a Python 3.11+ interpreter, found on `PATH` or among interpreters uv
has already installed. Hooks never download one, and in a repo that opted in an
unavailable interpreter fails visibly instead of skipping a check; a repo that did
not opt in never needs one. The due-measures line needs one only when the repo
has a `.graph/*/plan.json`, and is silent without it. No `jq`, no packages to install. The agent guard and
the SessionStart doctor also need `uv`, and skip silently without it.
Whatever the configured argv lists name (a linter, a build tool) is the repo's own
dependency, not the plugin's.

## Turning hooks off

There is no per-hook disable for a plugin's hooks (hooks reference, "Disable or
remove hooks"). The ways out, in order of least collateral damage:

- Let them no-op. No `.claude/graph-checks.json`, no `policy:` block in the profile
  and no `docs/HANDOFF.md` means the lint, the Stop gate, the agent guard and the
  handoff all do nothing. The destructive-command guard still asks on the commands
  above; answer it, or use the next two.
- `policy-override: <reason>` in one agent prompt skips the agent guard for that call.
- `claude plugin disable graph-engineering` turns off the plugin, hooks included.
- `"disableAllHooks": true` in a settings file turns off every hook from every
  source for that scope; `--settings '{"disableAllHooks": true}'` does it for one
  run.

## Tests

```
bash scripts/run-all-tests.sh
```

runs every suite in the repo. The hook suites on their own:

```
bash hooks/tests/run-tests.sh
python3 hooks/tests/test_configured_checks.py
python3 hooks/tests/test_hooks_registration.py
python3 hooks/tests/test_doctor_on_start.py
python3 hooks/tests/test_wait_run.py
python3 -m unittest discover -s tests/measure
```

`run-tests.sh` needs only `bash` and `python3`. It copies `hooks/tests/fixtures/`
into a `mktemp` directory, drives each hook the way Claude Code does (the event's
JSON on stdin, `CLAUDE_PROJECT_DIR` in the environment), writes only in the sandbox
and exits non-zero when any case fails. `test_hooks_registration.py` checks that
`hooks/hooks.json` holds exactly the registrations above and that this README keeps
stating the floors, the opt-in file and the breaking change.

## Registration

`hooks/hooks.json` at the plugin root is the default location and loads with no
entry in `.claude-plugin/plugin.json`; the manifest's `hooks` key exists for
configs kept somewhere else (plugins reference, "Hooks"). `claude plugin validate
<plugin dir>` reads this file, but `claude plugin validate <repo root>` validates
the marketplace manifest and does not, so the JSON is also checked with
`python3 -m json.tool hooks/hooks.json`. Entries keep the `type: command`,
`args: []` exec form, so `${CLAUDE_PLUGIN_ROOT}` is substituted as one argument with
no shell quoting.

## Sources, fetched 2026-09-30

Read the raw markdown (append `.md` to the docs URL). WebFetch summaries of the hooks
page were wrong in spikes d and e.

- https://code.claude.com/docs/en/hooks.md: handler fields (`if`, `async`,
  `asyncRewake`), "Run hooks in the background", "Stop input" (`stop_hook_active`,
  `background_tasks`, the 8-block cap), the SessionStart matcher values.
- https://code.claude.com/docs/en/plugins-reference.md: `hooks/hooks.json` default
  location.
- The 2026-09-30 spikes, summarised in `docs/superpowers/plans/2026-09-30-ge-0-15.md`: c (cap
  behaviour), e (`if` and `asyncRewake` on 2.1.285), i (SessionStart sources).
