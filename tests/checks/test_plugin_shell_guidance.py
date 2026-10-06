"""Shipped guidance never teaches a plugin-script call Claude Code cannot check.

Claude Code 2.1.288+ stops even a bypass-mode run on its inline-shell safety
prompt when a plugin script is called through a `$VAR/` command name or has its
argv wrapped in `bash -c`/`sh -c`. Agents copy the shapes our prompts, skills and
script headers show, so this scan keeps those shapes out of shipped text:

- S1: a line, or an inline backtick span on it, that the guard itself denies
  (`find_violation` from hooks/scripts/plugin_shell.py, never a second regex).
- S2: a plugin script's header comment showing `-- <shell> -<flags>c`.
- S3: an agent, engine doc or SKILL.md that writes `<plugin root>/.../<script>`
  without saying it is a literal absolute path, never a shell variable.

`bash <abs script>` (plan amendment D1) is allowed. The red control plants one
violation per rule in a tempdir, so the scan is proven able to fail. Stdlib only.
"""

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hooks/scripts"))

from plugin_shell import PLUGIN_SCRIPTS, SHELLS, find_violation, runs_c  # noqa: E402
from poll_loop import tokens  # noqa: E402

SCANNED = (
    "agents/**/*", "commands/**/*", "skills/**/*", "graphs/**/*", "templates/**/*",
    "workflows/**/*", "docs/engine/**/*", "docs/*.md", "hooks/README.md",
    "hooks/scripts/*.sh", "scripts/*.sh", "README.md",
)
SUFFIXES = frozenset({".md", ".sh", ".yaml", ".yml", ".js", ".json"})
EXCLUDED_PARTS = {
    "tests": "test data holds the bad shapes on purpose",
    "fixtures": "fixture data holds the bad shapes on purpose",
}
EXCLUDED_NAMES = {"CHANGELOG.md": "history that names the old shape"}
EXCLUDED_PREFIXES = {
    "docs/superpowers/": "dated research and specs, not guidance",
    "docs/ux/changes/": "maintainer evidence scripts (followups F3)",
    ".graph/": "run artifacts, not shipped",
}
PHRASE = "literal absolute path, never through a shell variable"
S3_SCOPE = re.compile(r"^(agents/|docs/engine/|skills/.+/SKILL\.md$)")
PLUGIN_ROOT_PATH = re.compile(r"<plugin[ -]root>(/[\w./-]+)")
BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")
MIN_SCANNED = 40


def excluded(rel: str) -> bool:
    parts = rel.split("/")
    return (any(part in EXCLUDED_PARTS for part in parts[:-1])
            or parts[-1] in EXCLUDED_NAMES
            or rel.startswith(tuple(EXCLUDED_PREFIXES)))


def scanned_files(root: Path) -> list[Path]:
    found = set()
    for pattern in SCANNED:
        for path in root.glob(pattern):
            rel = path.relative_to(root).as_posix()
            if path.is_file() and path.suffix in SUFFIXES and not excluded(rel):
                found.add(path)
    return sorted(found)


def candidates(line: str) -> list[str]:
    """The line, the line without a leading comment marker, and each backtick span."""
    texts = [line, line.lstrip().lstrip("#").strip()]
    return texts + BACKTICK_SPAN.findall(line)


def s1_hits(rel: str, lines: list[str]) -> list[str]:
    return [f"{rel}:{n} S1" for n, line in enumerate(lines, 1)
            if any(find_violation(text) for text in candidates(line))]


def header(lines: list[str]) -> list[tuple[int, str]]:
    """The leading `#` comment block, shebang included, with line numbers."""
    block = []
    for n, line in enumerate(lines, 1):
        if not line.startswith("#"):
            break
        block.append((n, line.lstrip("#")))
    return block


def shell_c_after_dashdash(text: str) -> bool:
    try:
        argv = tokens(text)
    except ValueError:
        argv = text.split()
    for at, word in enumerate(argv[:-1]):
        nxt = argv[at + 1]
        if word == "--" and nxt.rsplit("/", 1)[-1] in SHELLS and runs_c(argv[at + 2:]):
            return True
    return False


def s2_hits(rel: str, lines: list[str]) -> list[str]:
    if rel.rsplit("/", 1)[-1] not in PLUGIN_SCRIPTS:
        return []
    return [f"{rel}:{n} S2" for n, text in header(lines) if shell_c_after_dashdash(text)]


def s3_hits(rel: str, text: str) -> list[str]:
    if not S3_SCOPE.match(rel):
        return []
    names_script = any(path.rsplit("/", 1)[-1] in PLUGIN_SCRIPTS
                       for path in PLUGIN_ROOT_PATH.findall(text))
    has_phrase = PHRASE in " ".join(text.split())
    return [f"{rel} S3"] if names_script and not has_phrase else []


def scan(root: Path) -> list[str]:
    """Hits as `<rel path>:<line> S<n>` (S3: `<rel path> S3`), rule by rule."""
    texts = {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8", errors="replace")
             for path in scanned_files(root)}
    hits = []
    for rel, text in texts.items():
        hits += s1_hits(rel, text.splitlines())
    for rel, text in texts.items():
        hits += s2_hits(rel, text.splitlines())
    for rel, text in texts.items():
        hits += s3_hits(rel, text)
    return hits


# Synthetic red control (labelled): the observed trigger, from tasks/goal.md, with
# made-up concrete paths. Written to a tempdir as data; never executed.
TRIGGER = (
    "cd /work/tree && date -u +%s; P=/home/u/.claude/plugins/cache/graph-engineering/"
    "graph-engineering/0.16.0; L=/work/repo/.graph/r1/logs; $P/hooks/scripts/wait-run.sh "
    "--full --log $L/t.log -- bash -c 'set -o pipefail; tools/check --goldens'; "
    "echo wr=$?; tail -3 $L/t.log"
)
CLEAN_CALL = (
    "/home/u/.claude/plugins/cache/graph-engineering/graph-engineering/0.16.0/hooks/scripts/"
    "wait-run.sh --full --log /work/repo/.graph/r1/logs/t.log -- bash /work/repo/.graph/r1/check.sh"
)
PLANTED = {
    "agents/x.md": f"# X\n\nRun the suite:\n\n```bash\n{TRIGGER}\n```\n",
    "agents/x-clean.md": f"# X\n\nRun the suite:\n\n```bash\n{CLEAN_CALL}\n```\n",
    "skills/y/scripts/mutate-witness.sh":
        "#!/usr/bin/env bash\n# Witness.\n#   -- sh -c 'cd sub && make test'\nset -euo pipefail\n",
    "skills/w/scripts/mutate-witness.sh":
        "#!/usr/bin/env bash\n# Witness.\n#   -- bash /abs/run/witness-test.sh\nset -euo pipefail\n",
    "agents/z.md": "# Z\n\nStart it with `<plugin root>/hooks/scripts/wait-run.sh --log <path> -- <argv>`.\n",
    "agents/z-clean.md": (
        "# Z\n\nStart it with `<plugin root>/hooks/scripts/wait-run.sh --log <path> -- <argv>`.\n"
        f"`<plugin root>` is a {PHRASE}.\n"
    ),
}
PLANTED_HITS = [
    "agents/x.md:6 S1",
    "skills/y/scripts/mutate-witness.sh:3 S2",
    "agents/z.md S3",
]


def unreleased(changelog: str) -> str:
    return changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]


class GuidanceScan(unittest.TestCase):
    def test_shipped_guidance_is_clean(self):
        files = scanned_files(ROOT)
        self.assertGreaterEqual(len(files), MIN_SCANNED, "scan reached too few files to mean anything")
        self.assertEqual(scan(ROOT), [])

    def test_planted_violations_are_found_and_twins_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, body in PLANTED.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(body, encoding="utf-8")
            self.assertEqual(len(scanned_files(root)), len(PLANTED))
            self.assertEqual(scan(root), PLANTED_HITS)

    def test_exclusions_skip_test_data_and_history(self):
        for rel in ("skills/a/tests/x.md", "hooks/fixtures/y.json", "CHANGELOG.md",
                    "docs/superpowers/specs/a.md", "docs/ux/changes/w4/capture.sh", ".graph/r/a.md"):
            with self.subTest(rel=rel):
                self.assertTrue(excluded(rel))
        self.assertFalse(excluded("agents/implementer.md"))


class Changelog(unittest.TestCase):
    def test_unreleased_entry_names_the_guard_dispatch_line_and_signal(self):
        entry = unreleased((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        for needle in ("GRAPH_SHELL_GUARD=off", "plugin root:", "plugin_shell_calls.py",
                       "CLAUDE_CODE_DISABLE_INLINE_SHELL_RM_PROMPT", "guard-plugin-shell.sh"):
            with self.subTest(needle=needle):
                self.assertIn(needle, entry)


if __name__ == "__main__":
    unittest.main()
