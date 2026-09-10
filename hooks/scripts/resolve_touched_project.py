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

PROJECT_FILES = (("pyproject.toml", "pyproject"), ("package.json", "package"))


def is_inside(touched, project):
    """Is `touched` strictly inside `project`?

    Equality is False: the touched path being the project root itself would
    start the walk one level above the root. The separator is what keeps a
    sibling such as /repo-evil out of /repo.
    """
    return touched.startswith(project + os.sep)


def find_project_file(directory, project):
    """Walk up from `directory` to the nearest project file, never leaving
    `project`. Returns (directory, kind), or None.
    """
    while True:
        if directory != project and not is_inside(directory, project):
            return None
        for filename, kind in PROJECT_FILES:
            if os.path.isfile(os.path.join(directory, filename)):
                return directory, kind
        parent = os.path.dirname(directory)
        if directory == project or parent == directory:
            return None
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
