"""Regression cases for scripts/check-agent-frontmatter.sh.

Each directory under fixtures/ is a plugin root with one defect (or none).
A failing root must fail with exactly one FAIL line that names the file, so
the case proves the check caught that defect and nothing else.
"""

from __future__ import annotations

import pathlib
import subprocess
import unittest

HERE = pathlib.Path(__file__).resolve().parent
CHECK = HERE.parent.parent / "scripts" / "check-agent-frontmatter.sh"
FIXTURES = HERE / "fixtures"

PASSING = ["good", "omit-claude-md", "graph-engine"]

# root -> (file the FAIL line names, phrase the FAIL line carries)
FAILING = {
    "bare-skill": ("agents/bare.md", "graph-engineering:alpha"),
    "unresolved-skill": ("agents/lost.md", "resolves to 0"),
    "model-haiku": ("agents/cheap.md", "model `haiku`"),
    "model-fable": ("agents/old.md", "model `fable`"),
    "permission-mode": ("agents/perm.md", "ignored for plugin agents"),
    "isolation": ("agents/iso.md", "not adopted: frontmatter isolation branches"),
    "max-turns-ten": ("agents/turns.md", "maxTurns"),
    "name-mismatch": ("agents/stem.md", "differs from file stem `stem`"),
    "missing-tools": ("agents/notools.md", "tools"),
    "graph-ghost": ("graphs/g.md", "ghost"),
}


def run(root: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(CHECK), str(FIXTURES / root)],
        capture_output=True,
        text=True,
        check=False,
    )


class CheckAgentFrontmatter(unittest.TestCase):
    def test_every_fixture_root_is_covered(self) -> None:
        roots = {p.name for p in FIXTURES.iterdir() if p.is_dir()}
        self.assertEqual(roots, set(PASSING) | set(FAILING))

    def test_passing_roots_exit_zero(self) -> None:
        for root in PASSING:
            with self.subTest(root=root):
                result = run(root)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("FAIL", result.stdout)

    def test_failing_roots_name_the_file_and_the_defect(self) -> None:
        for root, (rel, phrase) in FAILING.items():
            with self.subTest(root=root):
                result = run(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                fails = [ln for ln in result.stdout.splitlines() if ln.startswith("FAIL ")]
                self.assertEqual(len(fails), 1, result.stdout)
                self.assertTrue(fails[0].startswith(f"FAIL {rel}:"), fails[0])
                self.assertIn(phrase, fails[0])

    def test_missing_root_fails(self) -> None:
        result = run("no-such-root")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
