import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import hygiene_fixture  # noqa: F401
from graph_control.hygiene import Context, doctor_rows, iter_rules
from graph_control.hygiene import context as rule
from graph_control.hygiene.config import parse

NOW = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)
SCOPED = "---\npaths:\n  - \"src/**\"\n---\n"
CORE = {"budgets": [{"id": "core", "globs": ["CLAUDE.md"], "max_bytes": 1000}]}


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def write(self, rel, size, head=""):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(head + "x" * (size - len(head.encode())), encoding="utf-8")
        return path

    def findings(self, context=None, mode="tracked"):
        profile = {"hygiene": {"context": context}} if context is not None else {}
        return rule.run(Context(root=self.root, config=parse(profile), mode=mode, now=NOW))


class Contract(Base):
    def test_contract(self):
        self.assertEqual((rule.ID, rule.QUICK), ("context", True))
        self.assertEqual(rule.MODES, frozenset({"staged", "base", "tracked", "doctor"}))
        self.assertIn("context", [module.ID for module in iter_rules()])


class Builtin(Base):  # AC-CTX-DEFAULT
    def test_total_over_cap_warns_naming_set_bytes_and_cap(self):
        self.write("CLAUDE.md", 25000)
        self.write(".claude/rules/a.md", 9000, SCOPED)
        found = self.findings()
        self.assertTrue(found)
        self.assertEqual({(item.level, item.id) for item in found}, {("warn", "context-budget")})
        [total] = [item for item in found if "always-on" in item.message and "24000" in item.message]
        self.assertIn("25000", total.message)
        self.assertIn("CLAUDE.md", total.message)
        self.assertTrue(total.fix)
        self.assertFalse([item for item in found if "a.md" in item.message])

    def test_per_file_cap_warns_for_that_file_alone(self):
        self.write("CLAUDE.md", 1000)
        self.write(".claude/rules/b.md", 9000)
        [finding] = self.findings()
        self.assertEqual((finding.level, finding.id, finding.path), ("warn", "context-budget", ".claude/rules/b.md"))
        self.assertIn("9000", finding.message)
        self.assertIn("8000", finding.message)

    def test_at_warn_pct_warns_and_under_gives_none(self):
        self.write("CLAUDE.md", 6000)
        self.write("AGENTS.md", 6000)
        self.write(".claude/rules/c.md", 6000)
        self.assertEqual(self.findings(), [])
        self.write(".claude/rules/d.md", 1200)
        [finding] = self.findings()
        self.assertIn("19200", finding.message)
        self.assertIn("always-on", finding.message)

    def test_off_and_never_error(self):
        self.write("CLAUDE.md", 90000)
        self.assertEqual(self.findings({"builtin": False}), [])
        self.assertEqual({item.level for item in self.findings()}, {"warn"})

    def test_scoped_rules_and_other_files_are_excluded(self):
        self.write(".claude/rules/a.md", 30000, SCOPED)
        self.write(".claude/rules/nested/e.md", 30000)
        self.write(".claude/rules/f.txt", 30000)
        self.write("README.md", 30000)
        self.assertEqual(self.findings(), [])

    def test_invalid_frontmatter_counts_as_unconditional(self):
        self.write(".claude/rules/g.md", 9000, "---\npaths: [unclosed\n---\n")
        [finding] = self.findings()
        self.assertEqual(finding.path, ".claude/rules/g.md")

    def test_unclosed_frontmatter_counts_as_unconditional(self):
        self.write(".claude/rules/j.md", 9000, "---\npaths: src\n# ")
        [finding] = self.findings()
        self.assertEqual(finding.path, ".claude/rules/j.md")

    def test_unreadable_rule_counts_as_unconditional(self):
        path = self.write(".claude/rules/i.md", 9000, SCOPED)
        path.chmod(0)
        self.addCleanup(path.chmod, 0o644)
        [finding] = self.findings()
        self.assertEqual(finding.path, ".claude/rules/i.md")

    def test_no_claude_md_is_no_finding(self):
        self.assertEqual(self.findings(), [])

    def test_symlink_counts_its_target_once(self):
        target = self.write("AGENTS.md", 13000)
        os.symlink(target, self.root / "CLAUDE.md")
        rules = self.root / ".claude" / "rules"
        rules.mkdir(parents=True)
        os.symlink(target, rules / "h.md")
        found = self.findings()
        self.assertFalse([item for item in found if "always-on" in item.message and "24000" in item.message])
        self.assertEqual(len(found), 1)
        self.assertIn("13000", found[0].message)


class Profile(Base):  # AC-CTX-PROFILE
    def test_at_warn_pct_warns_and_over_cap_errors(self):
        self.write("CLAUDE.md", 850)
        [warn] = self.findings({**CORE, "builtin": False})
        self.assertEqual((warn.level, warn.id), ("warn", "context-budget"))
        self.write("CLAUDE.md", 1100)
        [error] = self.findings({**CORE, "builtin": False})
        self.assertEqual((error.level, error.id), ("error", "context-budget"))
        for text in ("core", "1100", "1000", "CLAUDE.md"):
            self.assertIn(text, error.message)
        self.assertTrue(error.fix)

    def test_under_warn_pct_and_exact_cap(self):
        self.write("CLAUDE.md", 799)
        self.assertEqual(self.findings({**CORE, "builtin": False}), [])
        self.write("CLAUDE.md", 1000)
        [finding] = self.findings({**CORE, "builtin": False})
        self.assertEqual(finding.level, "warn")
        self.write("CLAUDE.md", 949)
        self.assertEqual(self.findings({**CORE, "builtin": False, "warn_pct": 95}), [])

    def test_globs_sum_every_match_and_name_the_largest(self):
        self.write("prompts/one.md", 400)
        self.write("prompts/deep/two.md", 700)
        budget = {"id": "prompts", "globs": ["prompts/**/*.md"], "max_bytes": 1000}
        [finding] = self.findings({"budgets": [budget], "builtin": False})
        self.assertEqual(finding.level, "error")
        self.assertIn("1100", finding.message)
        self.assertIn("prompts/deep/two.md", finding.message)

    def test_doctor_quick_returns_the_same_rows_without_a_process(self):
        self.write("CLAUDE.md", 1100)
        profile = {"hygiene": {"context": {**CORE, "builtin": False}}}
        expected = [(item.level, item.id, item.message, item.fix) for item in self.findings(profile["hygiene"]["context"])]
        self.assertEqual([row[0] for row in expected], ["error"])
        with mock.patch("subprocess.run", side_effect=AssertionError("process started")) as run, \
                mock.patch("subprocess.Popen", side_effect=AssertionError("process started")) as popen:
            rows = doctor_rows(profile, self.root, quick=True)
            direct = rule.doctor(Context(root=self.root, config=parse(profile), mode="doctor", now=NOW))
        self.assertEqual((run.call_count, popen.call_count), (0, 0))
        self.assertEqual([row for row in rows if row[1] == "context-budget"], expected)
        self.assertEqual(direct, expected)


if __name__ == "__main__":
    unittest.main()
