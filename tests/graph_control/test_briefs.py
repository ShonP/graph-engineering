"""The `validate-briefs` command over SYNTHETIC run directories.

Task ids and brief bodies are invented shapes, not a real run's plan.
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


def brief(lines=10, fenced=0, fence="```"):
    """`lines` lines in total, `fenced` of them inside one fenced block (fences included)."""
    body = [fence, *["code"] * (fenced - 2), fence] if fenced else []
    return "\n".join(body + ["prose"] * (lines - len(body))) + "\n"


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


class ValidateBriefs(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.run = self.repo / ".graph" / "run-1"
        (self.run / "tasks").mkdir(parents=True)
        data = plan_data()
        template = data["tasks"][0]
        data["tasks"] = [{**template, "id": key, "produces": [], "writable_paths": [f"app/{key.lower()}/**"]}
                         for key in ("T1", "T2")]
        self.plan = data
        dump(self.run / "plan.json", data)
        for key in ("T1", "T2"):
            self.write(key, brief())

    def write(self, task, body):
        (self.run / "tasks" / f"{task}.md").write_text(body)

    def check(self):
        return invoke(["validate-briefs", str(self.run)])

    def blocked(self, reason):
        self.assertEqual(self.check(), (1, {"status": "BLOCKED", "reason": reason}))

    def test_registered_as_plugin(self):
        self.assertIn("validate-briefs", [module.NAME for module in iter_commands()])

    def test_good_run_dir_passes(self):  # AC-W4-SS-04
        self.assertEqual(self.check(), (0, {"status": "PASS", "briefs": 2}))

    def test_missing_brief_blocked(self):  # AC-W4-SS-04
        (self.run / "tasks" / "T2.md").unlink()
        self.blocked("T2: tasks/T2.md is missing")

    def test_line_limit(self):  # AC-W4-SS-04
        self.write("T1", brief(300))
        self.assertEqual(self.check()[0], 0)
        self.write("T1", brief(301))
        self.blocked("T1: tasks/T1.md has 301 lines (limit 300)")

    def test_fenced_share_limit(self):  # AC-W4-SS-04
        self.write("T2", brief(20, fenced=7))
        self.assertEqual(self.check()[0], 0)
        self.write("T2", brief(20, fenced=8))
        self.blocked("T2: tasks/T2.md has 8 of 20 lines fenced (limit 35%)")

    def test_tilde_fences_count(self):
        self.write("T1", brief(10, fenced=4, fence="~~~"))
        self.blocked("T1: tasks/T1.md has 4 of 10 lines fenced (limit 35%)")

    def test_unclosed_fence_runs_to_the_end(self):
        self.write("T1", "prose\n" * 6 + "```python\n" + "code\n" * 3)
        self.blocked("T1: tasks/T1.md has 4 of 10 lines fenced (limit 35%)")

    def test_closing_fence_must_match(self):
        body = "````md\n```\ninner\n```\n````\n" + "prose\n" * 5
        self.write("T1", body)
        self.blocked("T1: tasks/T1.md has 5 of 10 lines fenced (limit 35%)")

    def test_inline_backticks_and_trailing_text_are_not_fences(self):
        self.write("T1", "```make``` runs first.\n" + "prose\n" * 9)
        self.assertEqual(self.check()[0], 0)
        self.write("T1", "```\n``` not a close\ncode\n```\n" + "prose\n" * 6)
        self.blocked("T1: tasks/T1.md has 4 of 10 lines fenced (limit 35%)")

    def test_empty_brief_blocked(self):
        self.write("T1", "\n \n")
        self.blocked("T1: tasks/T1.md is empty")

    def test_every_failure_named_in_plan_order(self):
        self.write("T1", brief(301))
        (self.run / "tasks" / "T2.md").unlink()
        self.blocked("T1: tasks/T1.md has 301 lines (limit 300); T2: tasks/T2.md is missing")

    def test_task_id_cannot_escape_tasks_dir(self):
        self.plan["tasks"][1]["id"] = "../T2"
        dump(self.run / "plan.json", self.plan)
        (self.run / "T2.md").write_text(brief())
        self.blocked("../T2: task id is not a file name under tasks/")

    def unknown(self, task, name):
        return f"{task}: tasks/{task}.md names {name}, which this plugin does not ship"

    def test_a_required_plugin_skill_the_plugin_does_not_ship_is_blocked(self):  # AC-BRIEF-UNKNOWN
        self.write("T1", "REQUIRED skills: graph-engineering:prior-art, graph-engineering:accessibility-review, "
                         "superpowers:test-driven-development\nDispatch graph-engineering:implementer for it.\n")
        self.blocked(self.unknown("T1", "graph-engineering:accessibility-review"))

    def test_bare_names_are_never_checked(self):  # AC-BRIEF-BARE
        self.write("T1", "REQUIRED skills: workflow-authoring, local-baseline, graph-engineering:prior-art\n")
        self.assertEqual(self.check(), (0, {"status": "PASS", "briefs": 2}))

    def test_an_agent_type_on_a_required_line_is_flagged_because_required_lines_name_skills(self):
        self.write("T1", "REQUIRED skills: graph-engineering:implementer\n")
        self.blocked(self.unknown("T1", "graph-engineering:implementer"))

    def test_lowercase_required_is_prose_and_not_scanned(self):
        self.write("T1", "The required reading is graph-engineering:absent-skill.\n")
        self.assertEqual(self.check()[0], 0)

    def test_a_required_line_without_names_passes(self):
        self.write("T1", "REQUIRED skills: none.\nREQUIRED skills: graph-engineering:\n")
        self.assertEqual(self.check()[0], 0)

    def test_punctuation_backticks_and_annotations_around_names(self):
        self.write("T1", "REQUIRED: `graph-engineering:prior-art` (preloaded), graph-engineering:uv; "
                         "(graph-engineering:absent-skill).\n")
        self.blocked(self.unknown("T1", "graph-engineering:absent-skill"))

    def test_each_unknown_named_once_per_task_in_plan_order(self):
        self.write("T2", "REQUIRED skills: graph-engineering:absent-b\n")
        self.write("T1", "REQUIRED skills: graph-engineering:absent-a, graph-engineering:absent-c\n"
                         "REQUIRED again: graph-engineering:absent-a\n")
        self.blocked("; ".join([self.unknown("T1", "graph-engineering:absent-a"),
                                self.unknown("T1", "graph-engineering:absent-c"),
                                self.unknown("T2", "graph-engineering:absent-b")]))

    def test_a_size_problem_and_an_unknown_name_are_both_named(self):
        self.write("T1", "REQUIRED skills: graph-engineering:absent-skill\n" + "prose\n" * 300)
        self.blocked("T1: tasks/T1.md has 301 lines (limit 300); " + self.unknown("T1", "graph-engineering:absent-skill"))

    def test_a_repo_local_skill_resolves_from_a_relative_run_dir(self):
        local = self.repo / ".claude" / "skills" / "local-baseline"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text("---\nname: local-baseline\n---\n")
        self.write("T1", "REQUIRED skills: graph-engineering:local-baseline\n")
        with contextlib.chdir(self.repo):
            self.assertEqual(invoke(["validate-briefs", ".graph/run-1"]), (0, {"status": "PASS", "briefs": 2}))
        local.joinpath("SKILL.md").unlink()
        self.blocked(self.unknown("T1", "graph-engineering:local-baseline"))

    def test_invalid_or_missing_plan_blocked(self):
        self.plan["tasks"][0]["depends_on"] = ["T1"]
        dump(self.run / "plan.json", self.plan)
        self.blocked("cyclic or unknown task dependency")
        (self.run / "plan.json").unlink()
        code, result = self.check()
        self.assertEqual((code, result["status"]), (1, "BLOCKED"))


if __name__ == "__main__":
    unittest.main()
