"""hygiene surfaces: the report-only sweep proposes idle, uncalled directories under surfaces.roots."""

import json
import re
import shutil
import tempfile
import unittest
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path

from hygiene_fixture import commit_at, git, make_repo, stage, write_profile
from graph_control.commands import hygiene as command

NOW = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)
SWEEP = ".graph/sweep-2026-01-15.md"
PROFILE = 'hygiene:\n  surfaces:\n    roots: ["tools/*"]\n    idleDays: 30\n'
DOCTOR = Path(__file__).resolve().parents[2] / "commands" / "graph-doctor.md"
HEADER = "| path | idle days | callers | lines | proposal |"


class Sweep(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = make_repo(self.tmp)
        self.profile = write_profile(self.root, PROFILE)
        stage(self.root, ".gitignore", ".graph/\n.claude/\n")
        commit_at(self.root, "ignore", 60, NOW)

    def add(self, days_ago, **files):
        for rel, text in files.items():
            stage(self.root, rel.replace("___", ".").replace("__", "/"), text)
        return commit_at(self.root, f"add {days_ago}", days_ago, NOW)

    def check(self, profile=None):
        if profile is not None:
            self.profile = write_profile(self.root, profile)
        parser = ArgumentParser()
        command.add_arguments(parser)
        args = parser.parse_args(["--root", str(self.root), "--profile", str(self.profile), "--sweep",
                                  "--only", "surfaces"])
        output = command.run(args, now=NOW)
        result = json.loads(output.text)
        self.assertEqual((output.exit_code, result["status"]), (0, "PASS"))
        return result["findings"]

    def rows(self, findings):
        sweep = next(f for f in findings if f["id"] == "sweep")
        self.assertEqual(sweep["message"], str(self.root / SWEEP))
        text = (self.root / SWEEP).read_text(encoding="utf-8")
        self.assertIn(HEADER, text)
        rows = [line for line in text.splitlines() if line.startswith("| ") and line != HEADER
                and not set(line) <= set("|- ")]
        small = re.findall(r"^small_files: (\d+)$", text, re.M)
        return rows, int(small[0]) if small else None

    def seed(self):
        self.add(40, tools__old__run___sh="echo acme-widget\nexit 0\n")
        self.add(35, tools__live__main___py="print('example-user')\n" * 5)
        self.add(10, tools__fresh__app___py="value = 1\n")
        self.add(5, scripts__run___sh="bash tools/live/main.py\n")

    def test_idle_uncalled_dir_is_proposed_and_the_tree_is_unchanged(self):
        self.seed()
        before = git(self.root, "status", "--porcelain", "--untracked-files=all")
        findings = self.check()
        self.assertEqual(git(self.root, "status", "--porcelain", "--untracked-files=all"), before)
        self.assertEqual(sorted(p.relative_to(self.root).as_posix() for p in (self.root / "tools").rglob("*")
                                if p.is_file()),
                         ["tools/fresh/app.py", "tools/live/main.py", "tools/old/run.sh"])
        self.assertEqual([(f["level"], f["id"]) for f in findings], [("info", "sweep")])
        rows, small = self.rows(findings)
        self.assertEqual(rows, ["| tools/old | 40 | 0 | 2 | delete |"])
        self.assertEqual(small, 2)

    def test_min_callers_raises_the_bar(self):
        self.seed()
        rows, _ = self.rows(self.check(PROFILE + "    minCallers: 2\n"))
        self.assertEqual(rows, ["| tools/live | 35 | 1 | 5 | delete |", "| tools/old | 40 | 0 | 2 | delete |"])

    def test_idle_days_bound_and_default(self):
        self.add(30, tools__at__a="x\n")
        self.add(29, tools__under__a="x\n")
        rows, _ = self.rows(self.check())
        self.assertEqual(rows, ["| tools/at | 30 | 0 | 1 | delete |"])
        rows, _ = self.rows(self.check('hygiene:\n  surfaces:\n    roots: ["tools/*"]\n    idleDays: 29\n'))
        self.assertEqual(rows, ["| tools/at | 30 | 0 | 1 | delete |", "| tools/under | 29 | 0 | 1 | delete |"])
        rows, _ = self.rows(self.check('hygiene:\n  surfaces:\n    roots: ["tools/*"]\n'))
        self.assertEqual(rows, ["| tools/at | 30 | 0 | 1 | delete |"])

    def test_last_commit_touching_the_dir_counts_deletions(self):
        self.add(50, tools__old__a="x\n", tools__old__b="y\n")
        git(self.root, "rm", "-q", "tools/old/b")
        commit_at(self.root, "drop b", 3, NOW)
        rows, _ = self.rows(self.check())
        self.assertEqual(rows, [])

    def test_a_sibling_sharing_a_prefix_ages_apart(self):
        self.add(40, tools__old__a="x\n")
        self.add(2, tools__older__a="tools/old\n")
        self.assertEqual(self.rows(self.check())[0], [])
        git(self.root, "rm", "-q", "tools/older/a")
        self.add(2, tools__older__b="y\n")
        self.assertEqual(self.rows(self.check())[0], ["| tools/old | 40 | 0 | 1 | delete |"])

    def test_a_root_glob_matching_a_file_is_skipped(self):
        self.add(90, tools__README___md="acme-widget notes\n")
        rows, small = self.rows(self.check())
        self.assertEqual((rows, small), ([], 0))

    def test_references_from_inside_the_dir_do_not_count(self):
        self.add(40, tools__old__a___sh="bash tools/old/b.sh\n", tools__old__b___sh="old\n")
        rows, _ = self.rows(self.check())
        self.assertEqual(rows, ["| tools/old | 40 | 0 | 2 | delete |"])

    def test_basename_counts_as_a_whole_word_only(self):
        self.add(40, tools__utils__a="x\n", tools__kit__a="y\n")
        self.add(40, README___md="shared utils live here\nsee the kitchen and toolkit_v2\n")
        rows, _ = self.rows(self.check())
        self.assertEqual(rows, ["| tools/kit | 40 | 0 | 1 | delete |"])

    def test_path_mention_counts(self):
        self.add(40, **{"tools/acme-widget/a": "x\n"})
        self.add(40, docs__guide___md="run tools/acme-widget/a\n")
        self.assertEqual(self.rows(self.check())[0], [])

    def test_uncommitted_and_untracked_files_are_ignored(self):
        self.add(40, tools__old__a="x\n")
        (self.root / "notes.md").write_text("tools/old\n", encoding="utf-8")
        stage(self.root, "tools/new/a", "x\n")
        rows, _ = self.rows(self.check())
        self.assertEqual(rows, ["| tools/old | 40 | 0 | 1 | delete |"])

    def test_small_files_count_text_files_of_three_lines_or_fewer(self):
        self.add(1, tools__fresh__empty="", tools__fresh__three="1\n2\n3", tools__fresh__four="1\n2\n3\n4\n",
                 tools__fresh__blob=b"\x00\x01\x02", outside__one="1\n")
        rows, small = self.rows(self.check())
        self.assertEqual((rows, small), ([], 2))

    def test_nested_dirs_under_a_globstar_root(self):
        self.add(40, tools__pack__inner__a="x\n", tools__pack__b="y\n")
        rows, _ = self.rows(self.check('hygiene:\n  surfaces:\n    roots: ["tools/**"]\n'))
        self.assertEqual(rows, ["| tools/pack | 40 | 0 | 2 | delete |", "| tools/pack/inner | 40 | 0 | 1 | delete |"])

    def test_no_roots(self):
        self.seed()
        findings = self.check("hygiene:\n  surfaces:\n    idleDays: 30\n")
        self.assertEqual(sorted((f["level"], f["id"]) for f in findings), [("info", "sweep"),
                                                                            ("info", "sweep-no-roots")])
        self.assertIn("hygiene.surfaces.roots", next(f for f in findings if f["id"] == "sweep-no-roots")["fix"])
        self.assertEqual(self.rows(findings), ([], 0))

    def test_other_modes_do_not_sweep(self):
        self.seed()
        parser = ArgumentParser()
        command.add_arguments(parser)
        args = parser.parse_args(["--root", str(self.root), "--profile", str(self.profile), "--tracked",
                                  "--only", "surfaces"])
        self.assertEqual(json.loads(command.run(args, now=NOW).text)["findings"], [])
        self.assertFalse((self.root / ".graph").exists())


class Doc(unittest.TestCase):
    def test_graph_doctor_documents_the_report_only_sweep(self):
        text = DOCTOR.read_text(encoding="utf-8")
        front, body = text.split("---\n")[1], " ".join(text.split("---\n", 2)[2].split())
        self.assertIn("hygiene findings", front)
        self.assertIn("--sweep", body)
        self.assertIn("scripts/graph-control.py hygiene --root", body)
        self.assertIn("never deletes", body)
        self.assertIn("report only", body.lower())
        self.assertNotIn(chr(0x2014), text)


if __name__ == "__main__":
    unittest.main()
