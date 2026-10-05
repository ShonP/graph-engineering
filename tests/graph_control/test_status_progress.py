"""graph_control.status slice 2: DONE since last look and NEXT from SYNTHETIC run artifacts.

The run dir holds an invented plan.json, run.json and receipts.json (ids, revisions and times are
made up); its ledger.md is a trap that must never be opened. Sessions come from test_status's fixture.
"""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import helpers
from graph_control.common import fingerprint
from test_status import EXPECTED_LINE, SCRIPTS, Workspace

RUN = "0192f3ac-0000-7000-8000-000000000002"
REV_A, REV_B = "a1b2c3d4" + "0" * 32, "b2c3d4e5" + "0" * 32
ZERO = "0" * 64
MANIFEST = {"schema_version": 1, "id": RUN, "plan": "plan.json"}  # status only fingerprints run.json
READS = {"plan.json", "run.json", "receipts.json", "decisions.md"}
DRIVER = ("import sys\nopened = []\n"
          "sys.addaudithook(lambda event, args: opened.append(str(args[0])) if event == 'open' else None)\n"
          "from graph_control.status import main\nmain([])\nsys.stderr.write('\\n'.join(opened))\n")


def plan(tasks):
    """A valid plan.json; `tasks` maps id -> depends_on, one case AC-<id> each."""
    data = helpers.plan_data()
    case, task = data["cases"][0], data["tasks"][0]
    data["cases"] = [dict(case, id=f"AC-{key}") for key in tasks]
    data["tasks"] = [dict(task, id=key, depends_on=deps, produces=[], writable_paths=[f"{key}/**"],
                          case_ids=[f"AC-{key}"]) for key, deps in tasks.items()]
    return data


def receipt(check, at, revision, cases, run=MANIFEST, important=0):
    return {"check_id": check, "actor": f"{check}-agent", "model": "host-model", "run_sha256": fingerprint(run),
            "candidate": {"sources": [{"repo": "app", "root": "/repo", "revision": revision, "dirty_sha256": ZERO}],
                          "runtime": None, "fixture_sha256": ZERO, "schema_sha256": ZERO},
            "argv": ["make", "test"], "cwd": "/repo", "status": "PASS" if all(cases.values()) else "FAIL",
            "exit_code": 0 if all(cases.values()) else 1, "executed": len(cases), "skipped": 0,
            "cases": [{"id": key, "status": "PASS" if ok else "FAIL"} for key, ok in cases.items()],
            "observed_at": at, "log_path": "/repo/log", "log_sha256": ZERO,
            "findings": {"blocking": 0, "important": important}}


DIAMOND = {"T1": [], "T2": ["T1"], "T3": ["T1"], "T4": ["T2", "T3"]}
RECEIPTS = [
    receipt("implement", "2026-09-30T10:00:00Z", REV_A, {"AC-T1": True, "AC-T2": False, "AC-T3": False, "AC-T4": False}),
    receipt("implement", "2026-09-30T11:00:00Z", REV_B, {"AC-T1": True, "AC-T2": True, "AC-T3": False, "AC-T4": False}),
    receipt("qa", "2026-09-30T11:30:00Z", REV_B, {"AC-T1": True, "AC-T2": True, "AC-T3": False, "AC-T4": False}),
    # an older run contract: never counts, whatever it says
    receipt("verify", "2026-09-30T12:00:00Z", REV_B, {"AC-T3": True, "AC-T4": True}, run={**MANIFEST, "id": "old"}),
]


class Progress(unittest.TestCase):
    def setUp(self):
        self.build()

    def build(self, extra_agents=0):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.space = Workspace(temp.name, extra_agents)
        self.run_dir = self.space.repo / ".graph" / RUN
        (self.run_dir / "ledger.md").write_text("- [ ] LEDGER-TRAP decision\nDONE LEDGER-TRAP T4\n")
        self.write(DIAMOND, RECEIPTS)
        digest = hashlib.sha256(str(self.space.repo).encode()).hexdigest()[:16]
        self.seen = self.space.cache / f"graph-engineering-status-seen-{digest}"

    def write(self, tasks, receipts):
        (self.run_dir / "plan.json").write_text(json.dumps(plan(tasks)))
        (self.run_dir / "run.json").write_text(json.dumps(MANIFEST))
        (self.run_dir / "receipts.json").write_text(json.dumps({"schema_version": 1, "receipts": receipts}))

    def section(self, lines, prefix):
        start = next(index for index, line in enumerate(lines) if line.startswith(prefix))
        end = next((index for index in range(start + 1, len(lines)) if not lines[index].startswith("  ")), len(lines))
        return lines[start:end]

    def test_done_and_next_from_run_artifacts(self):  # AC-W4-ST2-01
        first = self.space.run()
        self.assertEqual(first.returncode, 0, first.stderr)
        lines = first.stdout.splitlines()
        self.assertEqual(self.section(lines, "DONE"), ["DONE since last look (2)", f"  0192f3ac: T1 at {REV_A[:8]}",
                                                       f"  0192f3ac: T2 at {REV_B[:8]}"])
        self.assertEqual(self.section(lines, "NEXT"), ["NEXT (1)", "  0192f3ac: ready: T3"])
        self.assertEqual([line for line in lines if not line.startswith("  ")],
                         [lines[0], "RUNNING (3)", "DONE since last look (2)", "NEEDS YOU (2)", "NEXT (1)", "COST"])
        self.assertNotIn("LEDGER-TRAP", first.stdout)
        second = self.space.run().stdout.splitlines()
        self.assertEqual(self.section(second, "DONE"), ["DONE since last look (0)", "  none"])
        self.assertEqual(self.section(second, "NEXT"), ["NEXT (1)", "  0192f3ac: ready: T3"])

    def test_done_lists_only_tasks_passing_since_the_stored_time(self):
        self.seen.write_text(str(datetime.fromisoformat("2026-09-30T10:30:00+00:00").timestamp()))
        lines = self.space.run().stdout.splitlines()
        self.assertEqual(self.section(lines, "DONE"), ["DONE since last look (1)", f"  0192f3ac: T2 at {REV_B[:8]}"])
        self.assertGreater(float(self.seen.read_text()), 1.79e9, "the look is stored for the next one")

    def test_a_failing_later_receipt_or_open_findings_undo_done(self):
        receipts = copy.deepcopy(RECEIPTS[:3])
        receipts.append(receipt("qa", "2026-09-30T12:00:00Z", REV_B, {"AC-T1": True, "AC-T2": False,
                                                                      "AC-T3": False, "AC-T4": False}))
        receipts.append(receipt("review", "2026-09-30T12:30:00Z", REV_B, {"AC-T1": True}, important=1))
        self.write(DIAMOND, receipts)
        lines = self.space.run().stdout.splitlines()
        self.assertEqual(self.section(lines, "DONE"), ["DONE since last look (0)", "  none"])
        self.assertEqual(self.section(lines, "NEXT"), ["NEXT (1)", "  0192f3ac: ready: T1"])

    def test_no_receipts_yet_and_every_task_passing(self):
        (self.run_dir / "receipts.json").unlink()
        lines = self.space.run().stdout.splitlines()
        self.assertEqual(self.section(lines, "NEXT"), ["NEXT (1)", "  0192f3ac: ready: T1"])
        self.write(DIAMOND, [receipt("implement", "2026-09-30T10:00:00Z", REV_A, {f"AC-{k}": True for k in DIAMOND})])
        lines = self.space.run().stdout.splitlines()
        self.assertEqual(self.section(lines, "NEXT"), ["NEXT (0)", "  none"])
        self.assertEqual(self.section(lines, "DONE")[0], "DONE since last look (0)", "seen by the call before")

    def test_ledger_is_never_opened(self):  # AC-W4-ST2-01
        env = {**os.environ, **self.space.env, "PYTHONPATH": str(SCRIPTS)}
        result = subprocess.run([sys.executable, "-c", DRIVER], cwd=self.space.repo, env=env,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        graph = [Path(path) for path in result.stderr.splitlines() if "/.graph/" in path]
        self.assertTrue(READS <= {path.name for path in graph}, "the audit hook saw the reads")
        self.assertEqual({path.name for path in graph} - READS, set(), "only run artifacts and decisions.md")
        self.assertIn("NEXT (1)", result.stdout)

    def test_line_is_unchanged_and_writes_no_seen_file(self):  # AC-W4-ST2-02
        result = self.space.run("--line")
        self.assertEqual((result.returncode, result.stdout), (0, EXPECTED_LINE + "\n"))
        self.assertFalse(self.seen.exists())

    def test_full_view_stays_within_40_lines_with_every_section(self):
        self.build(extra_agents=27)  # 30 live agents
        tasks = {f"T{index:02d}": [] for index in range(20)}
        self.write(tasks, [receipt("implement", "2026-09-30T10:00:00Z", REV_A,
                                   {f"AC-{key}": index % 2 == 0 for index, key in enumerate(tasks)})])
        lines = self.space.run().stdout.splitlines()
        self.assertLessEqual(len(lines), 40)
        for title in ("RUNNING (30)", "DONE since last look (10)", "NEEDS YOU (2)", "NEXT (1)", "COST"):
            self.assertIn(title, lines)
        self.assertEqual(lines[-1].split()[0], "graph-engineering:qa", "COST is never cut off")


if __name__ == "__main__":
    unittest.main()
