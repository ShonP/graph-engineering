"""decision apply: a changed decision literal leaves no stale copy in the run's artifacts.

Every fixture here is synthetic: `old.example` and `new.example` stand for any
decided literal, and the run directory is a temp directory.
"""

import contextlib
import io
import json
import os
import re
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli

OLD, NEW = "old.example", "new.example"
LEDGER_LINE = re.compile(r'^- \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00) decision-apply '
                         r'"old\.example" -> "new\.example" 4 files$')


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, out.getvalue()


class DecisionApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name) / "run"
        (self.run_dir / "tasks").mkdir(parents=True)
        (self.run_dir / "design").mkdir()
        plan = {"schema_version": 1, "cases": [{"id": "AC-1", "then": f"the host is {OLD}"}]}
        self.files = {
            "plan.json": json.dumps(plan, indent=2) + "\n",
            "plan.md": f"# Plan\n\nThe host is {OLD}.\n",
            "tasks/T1.md": f"# T1\n\nline two\nPoint the client at {OLD} now.\n",
            "design/experience.md": f"{OLD} is shown in the header.\n",
        }
        for name, body in self.files.items():
            (self.run_dir / name).write_text(body, encoding="utf-8")
        self.ledger = self.run_dir / "ledger.md"
        self.ledger.write_text("# Ledger\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self):
        return {path.relative_to(self.run_dir).as_posix(): path.read_bytes()
                for path in sorted(self.run_dir.rglob("*")) if path.is_file()}

    def apply(self, old=OLD, new=NEW, write=False):
        argv = ["decision", "apply", str(self.run_dir), "--old", old, "--new", new]
        return invoke(argv + (["--write"] if write else []))

    def assertBlocked(self, code, out):
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["status"], "BLOCKED")

    def test_detect_lists_every_stale_copy_and_changes_nothing(self):
        before = self.snapshot()
        code, out = self.apply()
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(lines[-1], "decision apply: 4 stale copies of the old literal")
        self.assertEqual(sorted(lines[:-1]), sorted([
            f'plan.json:6: "then": "the host is {OLD}"',
            f"plan.md:3: The host is {OLD}.",
            f"tasks/T1.md:4: Point the client at {OLD} now.",
            f"design/experience.md:1: {OLD} is shown in the header.",
        ]))
        self.assertEqual(self.snapshot(), before)

    def test_detect_trims_a_long_line_to_160_characters(self):
        (self.run_dir / "plan.md").write_text(f"{OLD} " + "x" * 300 + "\n", encoding="utf-8")
        code, out = self.apply()
        self.assertEqual(code, 1)
        hit = next(line for line in out.splitlines() if line.startswith("plan.md:"))
        self.assertEqual(len(hit.split(": ", 1)[1]), 160)

    def test_no_hits_passes(self):
        code, out = self.apply(old="absent.example")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"status": "PASS", "hits": 0})

    def test_write_rewrites_every_copy_and_appends_one_ledger_line(self):
        code, out = self.apply(write=True)
        self.assertEqual(code, 0, out)
        result = json.loads(out)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(sorted(result["rewritten"]), sorted(self.files))
        self.assertEqual(result["ledger_lines"], 1)
        for name in self.files:
            self.assertNotIn(OLD, (self.run_dir / name).read_text(encoding="utf-8"))
        plan = json.loads((self.run_dir / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["cases"][0]["then"], f"the host is {NEW}")
        added = self.ledger.read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual(len(added), 1)
        self.assertRegex(added[0], LEDGER_LINE)
        self.assertEqual(self.apply()[0], 0)

        before = self.snapshot()
        code, out = self.apply(write=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out), {"status": "PASS", "rewritten": [], "ledger_lines": 0})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 2)

    def assertRefusedLiterals(self, old, new):
        before = self.snapshot()
        for write in (False, True):
            with self.subTest(write=write):
                code, out = self.apply(old=old, new=new, write=write)
                self.assertBlocked(code, out)
                self.assertIn("--old", json.loads(out)["reason"])
        self.assertEqual(self.snapshot(), before)

    def test_new_containing_old_is_blocked(self):
        self.assertRefusedLiterals(OLD, f"{OLD}.v2")

    def test_old_equal_to_new_is_blocked(self):
        self.assertRefusedLiterals(OLD, OLD)

    def test_empty_old_is_blocked(self):
        self.assertRefusedLiterals("", NEW)

    def test_rewrite_that_would_leave_the_old_literal_writes_nothing(self):
        (self.run_dir / "plan.md").write_text("old.old.exampleexample\n", encoding="utf-8")
        before = self.snapshot()
        code, out = self.apply(new="", write=True)
        self.assertBlocked(code, out)
        self.assertIn("plan.md", json.loads(out)["reason"])
        self.assertEqual(self.snapshot(), before)

    def test_rewrite_that_breaks_plan_json_writes_nothing(self):
        before = self.snapshot()
        code, out = self.apply(old='"then"', new="then", write=True)
        self.assertBlocked(code, out)
        self.assertIn("plan.json", json.loads(out)["reason"])
        self.assertEqual(self.snapshot(), before)

    def test_write_is_all_or_nothing_when_staging_a_file_fails(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        before = self.snapshot()
        tasks = self.run_dir / "tasks"
        tasks.chmod(0o555)
        try:
            code, out = self.apply(write=True)
        finally:
            tasks.chmod(0o755)
        self.assertBlocked(code, out)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([p.name for p in self.run_dir.rglob(".*")], [])

    def test_write_restores_every_file_when_a_replace_fails_midway(self):
        before = self.snapshot()
        real = os.replace
        calls = []

        def flaky(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError("disk went away")
            return real(source, target)

        with mock.patch("graph_control.commands.decision.os.replace", flaky):
            code, out = self.apply(write=True)
        self.assertBlocked(code, out)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([p.name for p in self.run_dir.rglob(".*")], [])

    def test_write_keeps_the_file_mode(self):
        target = self.run_dir / "plan.md"
        target.chmod(0o644)
        code, out = self.apply(write=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def quoted_plan(self):
        plan = {"schema_version": 1, "cases": [{"id": "AC-1", "then": 'merge_auto: "off" stays'}]}
        (self.run_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        (self.run_dir / "plan.md").write_text('merge_auto: "off" stays\n', encoding="utf-8")

    def test_detect_finds_a_literal_that_plan_json_stores_escaped(self):
        self.quoted_plan()
        code, out = self.apply(old='merge_auto: "off"', new='merge_auto: "when-green"')
        self.assertEqual(code, 1)
        self.assertTrue(any(line.startswith("plan.json:") for line in out.splitlines()), out)

    def test_write_rewrites_a_literal_that_plan_json_stores_escaped(self):
        self.quoted_plan()
        code, out = self.apply(old='merge_auto: "off"', new='merge_auto: "when-green"', write=True)
        self.assertEqual(code, 0, out)
        plan = json.loads((self.run_dir / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["cases"][0]["then"], 'merge_auto: "when-green" stays')
        self.assertEqual(self.apply(old='merge_auto: "off"', new='merge_auto: "when-green"')[0], 0)

    def test_write_rewrites_a_non_ascii_literal_that_plan_json_stores_escaped(self):
        plan = {"schema_version": 1, "cases": [{"id": "AC-1", "then": "café open"}]}
        (self.run_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        code, out = self.apply(old="café", new="tea", write=True)
        self.assertEqual(code, 0, out)
        stored = json.loads((self.run_dir / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["cases"][0]["then"], "tea open")


if __name__ == "__main__":
    unittest.main()
