"""Resolve the touched file to the project file that owns it, or to nothing.

Used by lint-touched-file.sh. Reads the PostToolUse JSON input from
$HOOK_INPUT and the session's project root from $CLAUDE_PROJECT_DIR, and prints
two lines on success, the directory then the kind, or nothing at all.

This is the security bound of the PostToolUse hook, so it lives in its own file
where each of its three guards can be tested directly:

  is_inside          the touched path must be STRICTLY inside the project
  os.path.isfile     the touched path must be a real file, not a directory and
                     not a path that has gone away
  find_project_file  the upward walk never inspects a directory outside the
                     project, whatever start point it is handed

The walk also passes a project file that declares neither `lint` nor
`typecheck` - but only on the way to an ancestor project file of the SAME kind.
That is not a security guard, it is a correctness one, and it was measured: in
a uv workspace the root owns the three script names and the member ships no
entry point at all, so stopping at the NEAREST pyproject.toml resolves every
file under packages/*/src/ to a project with no scripts, and the hook then exits
0 in silence (Equival-io/forge-platform docs/adr/0014-forge-libs-distribution.md
D2). The same-kind limit is what keeps a scriptless web/package.json under a
Python root from resolving to the root and running `uv run lint` on a .tsx file.
Whenever no same-kind scripted ancestor is found, the answer is the nearest
project file, exactly as before the walk learned to pass one.

The guards are layered on purpose. Given the caller's own check that
CLAUDE_PROJECT_DIR is a directory, the isfile guard already rejects everything
the other two would catch, so an end-to-end test cannot reach them. That is what
the unit cases in hooks/tests/cases-resolver.sh are for: they call these
functions directly, so removing any one guard fails the suite.

Input schema: https://code.claude.com/docs/en/hooks ("PostToolUse input").
"""

import json
import os
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

PROJECT_FILES = (("pyproject.toml", "pyproject"), ("package.json", "package"))

# The two scripts lint-touched-file.sh actually runs on a touched file. A project
# file declaring neither is not the project that owns it, so the walk continues.
# These names and that script's two `has_script` calls move together: stopping the
# walk somewhere the hook then declines to act on is the bug this tuple prevents.
SCRIPT_NAMES = ("lint", "typecheck")


def declares_scripts(directory, kind):
    """Does the project file in `directory` declare `lint` or `typecheck`?

    Returns True when the file cannot be read or parsed, and when tomllib is
    absent (Python < 3.11). An unreadable project file stops the walk where it
    is: the alternative is walking up to an ancestor and running THAT project's
    scripts against a file it does not own, which is worse than doing nothing.
    """
    if kind == "pyproject":
        if tomllib is None:
            return True
        try:
            with open(os.path.join(directory, "pyproject.toml"), "rb") as handle:
                data = tomllib.load(handle)
        except Exception:
            return True
        project = data.get("project") if isinstance(data, dict) else None
        scripts = project.get("scripts") if isinstance(project, dict) else None
    else:
        try:
            with open(os.path.join(directory, "package.json"), "rb") as handle:
                data = json.load(handle)
        except Exception:
            return True
        scripts = data.get("scripts") if isinstance(data, dict) else None

    if not isinstance(scripts, dict):
        return False
    return any(
        isinstance(scripts.get(name), str) and scripts[name].strip()
        for name in SCRIPT_NAMES
    )


def is_inside(touched, project):
    """Is `touched` strictly inside `project`?

    Equality is False: the touched path being the project root itself would
    start the walk one level above the root. The separator is what keeps a
    sibling such as /repo-evil out of /repo.
    """
    return touched.startswith(project + os.sep)


def find_project_file(directory, project):
    """Walk up from `directory` to the project file that owns it, never leaving
    `project`. Returns (directory, kind), or None.

    The nearest project file is the answer unless it declares neither of
    SCRIPT_NAMES; then the walk continues to the nearest ANCESTOR of the same
    kind that declares one. A directory holding a project file of another kind
    ends that search, and so does the bound: the nearest one is returned, as it
    was before this walk could pass one. See the module docstring.
    """
    nearest = None
    while True:
        if directory != project and not is_inside(directory, project):
            return nearest
        present = [
            kind
            for filename, kind in PROJECT_FILES
            if os.path.isfile(os.path.join(directory, filename))
        ]
        if present and nearest is None:
            if declares_scripts(directory, present[0]):
                return directory, present[0]
            nearest = directory, present[0]
            if len(present) > 1:
                return nearest
        elif present:
            if present != [nearest[1]]:
                return nearest
            if declares_scripts(directory, nearest[1]):
                return directory, nearest[1]
        parent = os.path.dirname(directory)
        if directory == project or parent == directory:
            return nearest
        directory = parent


def resolve(payload, project_dir):
    """Return (directory, kind) for the file this event touched, or None."""
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None

    raw = tool_input.get("file_path")
    if not isinstance(raw, str) or not raw or "\n" in raw or "\x00" in raw:
        return None
    if not os.path.isabs(raw):
        return None

    try:
        project = os.path.realpath(project_dir)
        touched = os.path.realpath(raw)
    except OSError:
        return None

    if not is_inside(touched, project):
        return None
    if not os.path.isfile(touched):
        return None

    return find_project_file(os.path.dirname(touched), project)


def main():
    try:
        payload = json.loads(os.environ["HOOK_INPUT"])
    except Exception:
        return 0
    found = resolve(payload, os.environ["CLAUDE_PROJECT_DIR"])
    if found is None:
        return 0
    print(found[0])
    print(found[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
