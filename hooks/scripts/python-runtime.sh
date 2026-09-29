#!/usr/bin/env bash
# Select a supported, already installed interpreter. Never download from a hook.
ge_python_runtime() {
  local candidate
  if [ -n "${GE_PYTHON:-}" ] && "$GE_PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    export GE_PYTHON
    return 0
  fi
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    GE_PYTHON="$(command -v python3)"
    export GE_PYTHON
    return 0
  fi
  if command -v uv >/dev/null 2>&1; then
    candidate="$(uv python find --no-python-downloads '>=3.11' 2>/dev/null)" || candidate=""
    if [ -n "$candidate" ] && "$candidate" -c 'import tomllib' 2>/dev/null; then
      PATH="$(dirname "$candidate"):$PATH"
      GE_PYTHON="$candidate"
      export PATH GE_PYTHON
      return 0
    fi
  fi
  printf 'Graph Engineering requires Python 3.11+ for project checks. Install it (for example: uv python install 3.12) and restart. No checks ran.\n' >&2
  return 1
}
