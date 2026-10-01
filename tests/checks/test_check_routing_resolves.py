"""Regression cases for scripts/check-routing-resolves.sh on SYNTHETIC plugin roots.

A routing name is written qualified, `graph-engineering:<name>`: a bare name can
resolve to a host built-in of the same name, and the skill receipt counts only
the identical qualified name. Another plugin's name cannot be resolved here.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile
import unittest

CHECK = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "check-routing-resolves.sh"
TEMPLATE = """\
schema_version: 2
routing:
  # derived:
  #   - when: synthetic
  #     impl: [{derived}]
  "**/*.py":
    impl: [graph-engineering:alpha, superpowers:test-driven-development]
  always:
    review: [{always}]
risk: []
"""


def run(always: str, derived: str = "graph-engineering:alpha") -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        (root / "skills" / "process" / "alpha").mkdir(parents=True)
        (root / "skills" / "process" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n")
        (root / "templates").mkdir()
        (root / "templates" / "graph-profile.yaml").write_text(TEMPLATE.format(always=always, derived=derived))
        return subprocess.run(["bash", str(CHECK), str(root)], capture_output=True, text=True, check=False)


class CheckRoutingResolves(unittest.TestCase):
    def test_qualified_names_resolve_and_another_plugins_name_is_skipped(self):
        result = run("graph-engineering:alpha")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)

    def test_a_bare_plugin_skill_fails_naming_the_qualified_form(self):
        for always, derived in (("alpha", "graph-engineering:alpha"), ("graph-engineering:alpha", "alpha")):
            with self.subTest(always=always, derived=derived):
                result = run(always, derived)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("FAIL alpha: bare", result.stdout)
                self.assertIn("graph-engineering:alpha", result.stdout)

    def test_an_unknown_name_fails_bare_or_qualified(self):
        for name in ("ghost", "graph-engineering:ghost"):
            with self.subTest(name=name):
                result = run(f"graph-engineering:alpha, {name}")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("no skills/*/ghost/SKILL.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
