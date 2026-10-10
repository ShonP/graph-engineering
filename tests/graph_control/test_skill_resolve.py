"""`skill_resolve.resolves` over SYNTHETIC plugin and repo trees, and the receipt's bare-name rule.

Skill names such as `local-baseline` and `plugin-skill` are invented shapes.
"""

import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from graph_control.skill_resolve import resolves
from graph_control.skills import missing


class Resolves(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.plugin, self.repo = Path(temp.name) / "plugin", Path(temp.name) / "repo"
        self.skill(self.plugin / "skills" / "process" / "plugin-skill")
        self.skill(self.repo / ".claude" / "skills" / "local-baseline")

    @staticmethod
    def skill(directory):
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("---\nname: synthetic\n---\n")

    def resolve(self, name):
        return resolves(name, self.plugin, self.repo)

    def test_a_plugin_skill_resolves_qualified_and_bare(self):
        self.assertIs(self.resolve("graph-engineering:plugin-skill"), True)
        self.assertIs(self.resolve("plugin-skill"), True)

    def test_a_repo_local_skill_resolves(self):
        self.assertIs(self.resolve("local-baseline"), True)
        self.assertIs(self.resolve("graph-engineering:local-baseline"), True)

    def test_a_name_found_nowhere_is_false(self):
        self.assertIs(self.resolve("graph-engineering:absent-skill"), False)
        self.assertIs(self.resolve("absent-skill"), False)

    def test_a_skill_dir_without_skill_md_is_false(self):
        (self.plugin / "skills" / "process" / "hollow").mkdir()
        self.assertIs(self.resolve("graph-engineering:hollow"), False)

    def test_another_plugins_name_is_not_checkable(self):
        self.assertIsNone(self.resolve("superpowers:plugin-skill"))
        self.assertIsNone(self.resolve("superpowers:absent-skill"))

    def test_the_plugin_name_is_a_parameter(self):
        self.assertIs(resolves("other:plugin-skill", self.plugin, self.repo, plugin="other"), True)
        self.assertIsNone(resolves("graph-engineering:plugin-skill", self.plugin, self.repo, plugin="other"))

    def test_an_invalid_name_is_false(self):
        for name in ("graph-engineering:", "graph-engineering:*", "graph-engineering:../plugin-skill", "-x", ""):
            with self.subTest(name=name):
                self.assertIs(self.resolve(name), False)


class ReceiptBareName(unittest.TestCase):  # AC-LOCAL-RECEIPT: pins skills.missing as it is
    def test_a_bare_repo_local_name_is_proven_only_by_the_same_bare_name(self):
        required = ("local-baseline",)
        self.assertEqual(missing(required, ("local-baseline",)), [])
        self.assertEqual(missing(required, ("other:local-baseline",)), ["local-baseline"])
        self.assertEqual(missing(required, ()), ["local-baseline"])


if __name__ == "__main__":
    unittest.main()
