#!/usr/bin/env bash
# Ban plan, task, wave and ADR numbers in code comments:
#   lint-no-plan-numbers.sh [--base <ref>] [paths...]
#
# Why a ban and not a staleness check: a comment that points at a numbered
# plan, task, wave or ADR is true the day it is written and wrong after the
# next renumbering, and no script can tell which numbers are still current.
# So the numbers are banned from comments outright. The reference belongs in
# the commit message or the PR, where history keeps it next to the change; the
# comment says what the code does and why.
#
# Comments are found by file extension; prose (.md, .txt, anything unlisted)
# is never scanned:
#   #            .py .pyi .toml .rb .sh .bash .zsh .yaml .yml
#   // and /* */ .ts .tsx .js .jsx .mjs .cjs .mts .cts .go .swift .kt .kts
#                .java .rs and the c family (.c .h .cc .cpp .cxx .hh .hpp .cs .m .mm)
#   -- and /* */ .sql
# String literals are skipped, including triple quotes and backticks where the
# language has them. A quote that never closes (a one-line kind: not on its own
# line) is read as a plain character (an apostrophe, a Rust lifetime), so a
# comment after it is still seen. In shell and YAML a hash starts a comment
# only at the start of a word. The banned pattern, case-insensitive:
#   \b(plan|task|wave|adr)[ #-]?[0-9]+\b
#
# Paths mode scans the given files; a directory expands to its tracked files.
# --base <ref> scans only the lines added since the merge base of <ref> and
# HEAD, committed or not (`git diff --merge-base --unified=0 <ref>`; stage a
# new file so git sees it). Each file is still read whole, so a line added
# inside an existing block comment or string is judged in context. Paths given
# with --base narrow the diff. Renames are followed, so a moved file is not
# blamed for the lines it carried.
#
# Prints `<file>:<line>: stale reference: <match>` per hit, paths relative to
# the current directory. Exit 0 clean, 1 on any hit, 2 on a usage error, a
# missing path, no repository or an unknown ref.
set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

python3 - "$@" <<'PY'
import ast
import os
import re
import subprocess
import sys

BAN = re.compile(r"\b(?:plan|task|wave|adr)[ #-]?[0-9]+\b", re.I)
USAGE = "usage: lint-no-plan-numbers.sh [--base <ref>] [paths...]"


def lang(line, block=(), quotes=(), word_start=False):
    return {"line": line, "block": block, "quotes": quotes, "word_start": word_start}


# A quote is (opener, closer, may span lines, backslash escapes).
DQ, SQ = ('"', '"', False, True), ("'", "'", False, True)
TRIPLE = (('"""', '"""', True, True), ("'''", "'''", True, True))
C_BLOCK = (("/*", "*/"),)
LANGS = {}
for exts, spec in (
    ("py pyi toml", lang(("#",), quotes=TRIPLE + (DQ, SQ))),
    ("rb", lang(("#",), quotes=(DQ, SQ))),
    ("sh bash zsh", lang(("#",), quotes=(DQ, ("'", "'", False, False)), word_start=True)),
    ("yaml yml", lang(("#",), quotes=(DQ, ("'", "'", False, False)), word_start=True)),
    ("ts tsx js jsx mjs cjs mts cts", lang(("//",), C_BLOCK, (DQ, SQ, ("`", "`", True, True)))),
    ("go", lang(("//",), C_BLOCK, (DQ, SQ, ("`", "`", True, False)))),
    ("swift kt kts java", lang(("//",), C_BLOCK, (TRIPLE[0], DQ, SQ))),
    ("rs c h cc cpp cxx hh hpp cs m mm", lang(("//",), C_BLOCK, (DQ, SQ))),
    ("sql", lang(("--",), C_BLOCK, (("'", "'", True, False), ('"', '"', False, False)))),
):
    for ext in exts.split():
        LANGS["." + ext] = spec


def fail(message):
    print(f"lint-no-plan-numbers: {message}", file=sys.stderr)
    sys.exit(2)


def string_end(text, i, closer, multiline, escapes):
    """Index just past the closing quote; None when it never closes (a one-line string: on its line)."""
    while i < len(text):
        if escapes and text[i] == "\\":
            i += 2
            continue
        if text.startswith(closer, i):
            return i + len(closer)
        if text[i] == "\n" and not multiline:
            return None
        i += 1
    return None


def token(text, i, spec):
    """(kind, end) for what starts at text[i]: a comment, a string, or None for one plain character."""
    for mark in spec["line"]:
        if text.startswith(mark, i) and (not spec["word_start"] or i == 0 or text[i - 1] in " \t\n"):
            end = text.find("\n", i)
            return "comment", len(text) if end < 0 else end
    for opener, closer in spec["block"]:
        if text.startswith(opener, i):
            end = text.find(closer, i + len(opener))
            return "comment", len(text) if end < 0 else end + len(closer)
    for opener, closer, multiline, escapes in spec["quotes"]:
        if text.startswith(opener, i):
            end = string_end(text, i + len(opener), closer, multiline, escapes)
            return ("string", end) if end is not None else (None, i + 1)
    return None, i + 1


def hits(path, spec):
    """(line, match) for every banned reference inside a comment of the file."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    found, i, line = [], 0, 1
    while i < len(text):
        kind, end = token(text, i, spec)
        if kind == "comment":
            for offset, piece in enumerate(text[i:end].split("\n")):
                found += [(line + offset, m.group(0)) for m in BAN.finditer(piece)]
        line += text.count("\n", i, end)
        i = end
    return found


def git(*args):
    result = subprocess.run(["git", "-c", "core.quotePath=false", *args], capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr.strip()


def expand(paths):
    """The given files, with each directory replaced by its tracked files."""
    files = []
    for path in paths:
        if os.path.isdir(path):
            code, out, err = git("-C", path, "ls-files", "-z")
            if code:
                fail(f"cannot list tracked files under {path}: {err}")
            files += [os.path.join(path, name) for name in out.split("\0") if name]
        elif os.path.isfile(path):
            files.append(path)
        else:
            fail(f"no such file: {path}")
    return [(path, None) for path in files]


def added_since(base, paths):
    """(path relative to cwd, added line numbers) for each file the diff since <base> adds lines to."""
    code, top, err = git("rev-parse", "--show-toplevel")
    if code:
        fail(f"--base needs a git repository: {err}")
    if git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")[0]:
        fail(f"unknown ref: {base}")
    code, out, err = git("diff", "--merge-base", "--unified=0", "--no-color", "--no-ext-diff", "--find-renames",
                         "--src-prefix=a/", "--dst-prefix=b/", base, "--", *paths)
    if code:
        fail(f"git diff failed: {err}")
    files, current = [], None
    for raw in out.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:]
            target = ast.literal_eval(target) if target.startswith('"') else target
            current = None if target == "/dev/null" else set()
            if current is not None:
                files.append((os.path.relpath(os.path.join(top.strip(), target[2:])), current))
        elif raw.startswith("@@") and current is not None:
            m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", raw)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            current.update(range(start, start + count))
    return files


def main(argv):
    base, paths = None, []
    while argv:
        arg = argv.pop(0)
        if arg == "--base" and argv:
            base = argv.pop(0)
        elif arg == "--":
            paths += argv
            break
        elif arg.startswith("-"):
            fail(USAGE)
        else:
            paths.append(arg)
    if base is None and not paths:
        fail(USAGE)
    targets = added_since(base, paths) if base is not None else expand(paths)
    status = 0
    for path, lines in targets:
        spec = LANGS.get(os.path.splitext(path)[1].lower())
        if spec is None or not os.path.isfile(path):
            continue
        for line, match in hits(path, spec):
            if lines is None or line in lines:
                print(f"{path}:{line}: stale reference: {match}")
                status = 1
    return status


sys.exit(main(sys.argv[1:]))
PY
