# shellcheck shell=bash
#
# Decide in bash alone whether a repository opted into a check, so a hook with
# nothing to do spawns no interpreter and needs no Python on the host.
#
# The only config that can apply to a path sits at <ancestor>/.claude/
# graph-checks.json: project_root.py binds a hook to CLAUDE_PROJECT_DIR, to the
# repository containing the path (a multi-repo workspace), or to the linked
# worktree containing it, and each of those is an ancestor of the path. So a
# walk up from the path finds every config Python could choose, and finding none
# proves there is nothing to run. Finding one only means Python decides.

# ge_input_path <json> <key>: set GE_INPUT_PATH to the first "<key>": "<value>"
# string in a hook's input. Returns 0 for an absolute path, 1 when the key is
# absent or the value is not absolute (Python ignores those too), and 2 when the
# value holds a JSON escape bash cannot decode: undecidable here, let Python run.
ge_input_path() {
  local pattern="\"$2\"[[:space:]]*:[[:space:]]*\"([^\"]*)\""
  GE_INPUT_PATH=
  [[ $1 =~ $pattern ]] || return 1
  GE_INPUT_PATH="${BASH_REMATCH[1]}"
  case "$GE_INPUT_PATH" in
    *\\*) return 2 ;;
    /*) return 0 ;;
    *) return 1 ;;
  esac
}

# ge_opted_in <key> <absolute-path>...: 0 when .claude/graph-checks.json exists
# in a given directory or any of its ancestors and, for a non-empty key,
# mentions "<key>". Relative paths are skipped. Only [ -f ] per level: no fork
# until a config is found.
ge_opted_in() {
  local key="$1" dir config
  shift
  for dir in "$@"; do
    case "$dir" in /*) ;; *) continue ;; esac
    while :; do
      dir="${dir%/}"
      config="$dir/.claude/graph-checks.json"
      if [ -f "$config" ]; then
        [ -z "$key" ] && return 0
        [[ $(<"$config") == *"\"$key\""* ]] && return 0
      fi
      [ -n "$dir" ] || break
      dir="${dir%/*}"
    done
  done
  return 1
}
