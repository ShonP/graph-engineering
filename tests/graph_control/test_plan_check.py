"""The `plan check` command over SYNTHETIC run and worktree directories.

Task ids, paths and brief bodies are invented shapes, not a real run's plan.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import dump, plan_data
from graph_control import cli
from graph_control.commands import iter_commands


class PlanCheck(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.run = base / "run"
        self.root = base / "worktree"
        (self.run / "tasks").mkdir(parents=True)
        (self.root / "src").mkdir(parents=True)
        (self.root / "src" / "app.py").write_text("".join(f"line {n}\n" for n in range(1, 11)))
        data = plan_data()
        template = data["tasks"][0]
        data["tasks"] = [
            {**template, "id": "T0", "produces": [], "writable_paths": ["lib/**"]},
            {**template, "id": "T1", "depends_on": ["T0"], "produces": [], "writable_paths": ["anc/**"]},
            {**template, "id": "T2", "depends_on": ["T1"], "produces": [], "writable_paths": ["new/**"]},
        ]
        dump(self.run / "plan.json", data)
        for key in ("T0", "T1", "T2"):
            self.write(key, "prose\n")

    def write(self, task, body):
        (self.run / "tasks" / f"{task}.md").write_text(body)

    def check(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["plan", "check", str(self.run), "--root", str(self.root)])
        return code, json.loads(out.getvalue())

    def test_registered_as_plugin(self):
        self.assertIn("plan", [module.NAME for module in iter_commands()])

    def test_ac_s8_missing_path_is_blocked(self):
        self.write("T1", "# T1\n\nEdit `src/gone.py` here.\n")
        self.assertEqual(self.check(), (1, {"status": "BLOCKED",
                                            "reason": "tasks/T1.md:3: `src/gone.py` does not exist"}))

    def test_ac_s8_eof_line_refs_past_end_are_blocked(self):
        self.write("T2", "See `src/app.py:500`.\nAnd `src/app.py:2-900` and `src/app.py:10`.\n")
        self.assertEqual(self.check(), (1, {"status": "BLOCKED", "reason": (
            "tasks/T2.md:1: `src/app.py:500` line 500 past end (10 lines); "
            "tasks/T2.md:2: `src/app.py:2-900` line 900 past end (10 lines)")}))

    def test_range_start_past_end_is_blocked(self):
        self.write("T2", "See `src/app.py:11-12` and `src/app.py:40-2`.\n")
        self.assertEqual(self.check(), (1, {"status": "BLOCKED", "reason": (
            "tasks/T2.md:1: `src/app.py:11-12` line 12 past end (10 lines); "
            "tasks/T2.md:1: `src/app.py:40-2` line 40 past end (10 lines)")}))

    def test_ac_s8_valid_refs_pass(self):
        self.write("T2", "\n".join([
            "Read `src/app.py:3` and `src/app.py:1-10`.",
            "Create `new/mod.py` and use `anc/x.py` and `lib/deep/y.py`.",
            "Not paths: `plan.json`, `graph-engineering:uv`, `https://example.com/a/b`, `.graph/<run>/x.md`.",
            "Also `<plugin root>/x`, `tests/*.py`, `-p/x`, `~/a/b`, `/abs/path`, `$P/x`, `a|b/c`, `{a,b}/c`.",
        ]) + "\n")
        self.assertEqual(self.check(), (0, {"status": "PASS", "briefs": 3, "refs": 5}))

    def test_sibling_writable_paths_do_not_excuse(self):
        self.write("T1", "Use `new/mod.py`.\n")
        self.assertEqual(self.check(), (1, {"status": "BLOCKED",
                                            "reason": "tasks/T1.md:1: `new/mod.py` does not exist"}))

    def test_ac_s8_fence_fenced_missing_path_passes(self):
        self.write("T1", "Prose.\n\n```bash\ncat src/gone.py `src/gone.py`\n```\n")
        self.assertEqual(self.check(), (0, {"status": "PASS", "briefs": 3, "refs": 0}))

    def test_missing_brief_is_skipped(self):
        (self.run / "tasks" / "T0.md").unlink()
        self.write("T1", "Edit `src/app.py`.\n")
        self.assertEqual(self.check(), (0, {"status": "PASS", "briefs": 2, "refs": 1}))


if __name__ == "__main__":
    unittest.main()
