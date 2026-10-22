#!/usr/bin/env bash
file="$1"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
status=0
case "$file" in
  *.py) command -v ruff >/dev/null 2>&1 && { ruff check "$file" || status=1; } ;;
esac
python3 "$here/check-no-new-comments.py" --base HEAD "$file" || status=1
exit "$status"
