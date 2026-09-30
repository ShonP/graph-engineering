#!/usr/bin/env bash
# Remove linked worktrees whose work is already merged:
#   worktree-gc.sh [--apply] [--base <ref>]
#
# A candidate is a linked worktree (never the main one, never the one holding
# the current directory, never a locked or bare one, never one on the base's
# own branch) whose HEAD is an ancestor of <base> and whose
# `git status --porcelain --untracked-files=normal` is empty. <base> defaults
# to origin/HEAD, then the local default branch (init.defaultBranch, main,
# master). A squash-merged branch is not an ancestor, so it is kept: the gc
# only removes what git itself can prove merged.
#
# Dry run (default) prints `would remove <path> (<branch>)` per candidate.
# --apply runs `git worktree remove <path>` (never --force, so git refuses
# anything dirty; ignored files such as build output go with the tree), then
# `git branch -d <branch>` (never -D), then `git worktree prune`.
# Exit: 0 done, 1 a remove or branch delete was refused (reported, the rest
# continue), 2 usage, no repository or an unknown base.
set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

usage() { echo "usage: worktree-gc.sh [--apply] [--base <ref>]" >&2; exit 2; }
die() { echo "worktree-gc: $1" >&2; exit 2; }

apply=0 base=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) apply=1 ;;
    --base) [ $# -ge 2 ] || usage; base="$2"; shift ;;
    *) usage ;;
  esac
  shift
done

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"
if [ -z "$base" ]; then
  base="$(git symbolic-ref -q --short refs/remotes/origin/HEAD)" || base=""
  if [ -z "$base" ]; then
    for name in "$(git config --get init.defaultBranch)" main master; do
      if [ -n "$name" ] && git show-ref -q --verify "refs/heads/$name"; then base="$name"; break; fi
    done
  fi
  [ -n "$base" ] || die "no origin/HEAD and no local default branch; pass --base <ref>"
fi
base_sha="$(git rev-parse -q --verify "$base^{commit}")" || die "base $base is not a commit"
# The branch the base names is never deleted, even when a worktree has it checked out.
protected="$base"
git show-ref -q --verify "refs/remotes/$base" && protected="${base#*/}"
here="$(git rev-parse --show-toplevel 2>/dev/null)" && here="$(cd "$here" && pwd -P)"

failed=0
consider() { # consider <path> <head> <branch> <skip>
  local path="$1" head="$2" branch="$3" real label
  [ "$4" -eq 0 ] && [ -n "$head" ] || return 0
  [ -n "$branch" ] && [ "$branch" = "$protected" ] && return 0
  real="$(cd "$path" 2>/dev/null && pwd -P)" || return 0
  [ "$real" != "$here" ] || return 0
  git merge-base --is-ancestor "$head" "$base_sha" 2>/dev/null || return 0
  [ -z "$(git -C "$path" status --porcelain --untracked-files=normal 2>/dev/null)" ] || return 0
  label="${branch:-detached}"
  if [ "$apply" -eq 0 ]; then
    printf 'would remove %s (%s)\n' "$path" "$label"
    return 0
  fi
  if ! git worktree remove "$path"; then failed=1; return 0; fi
  printf 'removed %s (%s)\n' "$path" "$label"
  [ -n "$branch" ] || return 0
  if git branch -q -d "$branch"; then printf 'deleted branch %s\n' "$branch"; else failed=1; fi
}

# Porcelain -z: one NUL-terminated field per line, an empty field ends a record.
first=1 path="" head="" branch="" skip=0
while IFS= read -r -d '' field; do
  case "$field" in
    "") if [ "$first" -eq 1 ]; then first=0; else consider "$path" "$head" "$branch" "$skip"; fi
        path="" head="" branch="" skip=0 ;;
    "worktree "*) path="${field#worktree }" ;;
    "HEAD "*) head="${field#HEAD }" ;;
    "branch refs/heads/"*) branch="${field#branch refs/heads/}" ;;
    bare|locked|"locked "*|prunable|"prunable "*) skip=1 ;;
  esac
done < <(git worktree list --porcelain -z)

[ "$apply" -eq 0 ] || git worktree prune
exit "$failed"
