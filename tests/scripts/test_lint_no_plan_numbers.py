"""lint-no-plan-numbers.sh bans plan, task, wave and ADR numbers in code comments.

AC-W4-RG-02 comments are found by extension and string literals and prose are
skipped; AC-W4-RG-03 --base reports only lines added since the ref;
AC-W4-RG-04 exit 1 with `file:line: stale reference: <match>` lines on hits,
exit 0 and no output when clean. Every case builds a SYNTHETIC throwaway git
repo with GIT_DIR and friends scrubbed, as a hook running these tests from a
linked worktree would otherwise leak its own repo.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINT = ROOT / "scripts" / "lint-no-plan-numbers.sh"
GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
ENV = {key: value for key, value in os.environ.items() if key not in GIT_VARS}

# The four comment styles AC-W4-RG-02 names, each followed by the same text in a string literal.
FLAGGED = {
    "a.py": "x = 1\n# see plan 4 task 12\ny = \"see plan 4 task 12\"\nz = '''\n# plan 4\n'''\n",
    "b.ts": "const a = 1;\n// wave 3\nconst s = \"// wave 3\";\nconst t = `wave 3\n// wave 3`;\n",
    "c.sql": "SELECT 1;\n-- ADR 7\nSELECT '-- ADR 7';\n",
    "d.go": "package d\n/* task 5 */\nvar s = \"/* task 5 */\"\nvar r = `// task 5`\n",
}
EXPECTED = [
    "a.py:2: stale reference: plan 4",
    "a.py:2: stale reference: task 12",
    "b.ts:2: stale reference: wave 3",
    "c.sql:2: stale reference: ADR 7",
    "d.go:2: stale reference: task 5",
]


def git(cwd, *args):
    result = subprocess.run(["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null", *args],
                            capture_output=True, text=True, env=ENV, check=False)
    if result.returncode:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result.stdout


class Repo(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve() / "repo"
        git(self.repo.parent, "init", "-q", "-b", "main", str(self.repo))
        for key, value in (("user.email", "test@example.invalid"), ("user.name", "Test"), ("commit.gpgsign", "false")):
            git(self.repo, "config", key, value)

    def write(self, files):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def commit(self, files, message="change"):
        self.write(files)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", message)

    def lint(self, *args):
        result = subprocess.run(["bash", str(LINT), *args], cwd=self.repo, env=ENV,
                                capture_output=True, text=True, check=False)
        return result.returncode, result.stdout.splitlines(), result.stderr


class CommentsByExtension(Repo):
    def test_flags_each_comment_style_and_skips_string_literals_ac_w4_rg_02(self):
        self.write(FLAGGED)
        code, out, err = self.lint(*FLAGGED)
        self.assertEqual((code, out), (1, EXPECTED), err)

    def test_skips_markdown_and_other_prose_ac_w4_rg_02(self):
        prose = "# see plan 4 task 12\n// wave 3\n-- ADR 7\n/* task 5 */\n"
        self.write({"notes.md": prose, "notes.txt": prose})
        self.assertEqual(self.lint("notes.md", "notes.txt")[:2], (0, []))

    def test_block_comment_spanning_lines_reports_the_inner_line(self):
        self.write({"e.rs": "fn main() {}\n/*\n  wave 9 cleanup\n*/\n"})
        self.assertEqual(self.lint("e.rs")[:2], (1, ["e.rs:3: stale reference: wave 9"]))

    def test_hash_languages_need_a_comment_not_a_quoted_or_expanded_hash(self):
        self.write({
            "f.yaml": "a: \"x # task 3\"\nb: 1 # task 3\n",
            "g.sh": "echo \"$# task 3\" $# task 3 '# plan 2'\necho ok # plan 2\n",
        })
        code, out, err = self.lint("f.yaml", "g.sh")
        self.assertEqual((code, out), (1, ["f.yaml:2: stale reference: task 3", "g.sh:2: stale reference: plan 2"]), err)

    def test_matches_are_case_insensitive_with_optional_separator(self):
        self.write({"h.kt": "// Task#4, adr-12, WAVE2\n// tasks 5 and plan b stay\n"})
        code, out, _ = self.lint("h.kt")
        self.assertEqual((code, out), (1, [
            "h.kt:1: stale reference: Task#4",
            "h.kt:1: stale reference: adr-12",
            "h.kt:1: stale reference: WAVE2",
        ]))

    def test_directory_expands_to_its_tracked_files(self):
        self.commit({"src/" + name: text for name, text in FLAGGED.items()})
        self.write({"src/untracked.py": "# plan 1\n"})
        code, out, _ = self.lint("src")
        self.assertEqual((code, out), (1, ["src/" + line for line in EXPECTED]))


class ExitAndFormat(Repo):
    def test_clean_files_exit_0_with_no_output_ac_w4_rg_04(self):
        self.write({"clean.py": "# see the plan in the docs\nx = 'task 12'\n", "clean.go": "// wave of requests\n"})
        self.assertEqual(self.lint("clean.py", "clean.go")[:2], (0, []))

    def test_hits_exit_1_in_the_file_line_format_ac_w4_rg_04(self):
        self.write({"src/a.py": "\n\n# per ADR 7\n"})
        self.assertEqual(self.lint("src/a.py")[:2], (1, ["src/a.py:3: stale reference: ADR 7"]))

    def test_a_missing_path_or_an_unknown_ref_exits_2(self):
        self.commit({"a.py": "x = 1\n"})
        self.assertEqual(self.lint("missing.py")[0], 2)
        self.assertEqual(self.lint("--base", "no-such-ref")[0], 2)
        self.assertEqual(self.lint("--bogus")[0], 2)
        self.assertEqual(self.lint()[0], 2, "no paths and no --base is a usage error")

    def test_the_lint_and_its_tests_pass_their_own_ban(self):
        code, out, err = self.lint(str(LINT), __file__)
        self.assertEqual((code, out), (0, []), err)


class BaseMode(Repo):
    def test_reports_only_lines_added_since_the_ref_ac_w4_rg_03(self):
        self.commit({"a.py": "# plan 1\nx = 1\n", "b.go": "/*\n  old\n*/\n"}, "base")
        git(self.repo, "checkout", "-qb", "topic")
        self.commit({"a.py": "# plan 1\nx = 1\n# wave 2\ny = 2\n", "b.go": "/*\n  old\n  task 8\n*/\n"})
        self.write({"c.ts": "// task 9\n"})
        git(self.repo, "add", "c.ts")
        code, out, err = self.lint("--base", "main")
        self.assertEqual((code, out), (1, [
            "a.py:3: stale reference: wave 2",
            "b.go:3: stale reference: task 8",
            "c.ts:1: stale reference: task 9",
        ]), err)

    def test_base_that_moved_on_does_not_blame_the_branch_ac_w4_rg_03(self):
        self.commit({"a.py": "# plan 1\nx = 1\n"}, "base")
        git(self.repo, "checkout", "-qb", "topic")
        self.commit({"a.py": "# plan 1\nx = 1\n# wave 2\n"})
        git(self.repo, "checkout", "-q", "main")
        self.commit({"a.py": "x = 1\n"}, "main drops the old reference")
        git(self.repo, "checkout", "-q", "topic")
        self.assertEqual(self.lint("--base", "main")[:2], (1, ["a.py:3: stale reference: wave 2"]))

    def test_paths_narrow_the_base_diff_and_clean_diff_exits_0(self):
        self.commit({"a.py": "x = 1\n", "b.py": "y = 1\n"}, "base")
        git(self.repo, "checkout", "-qb", "topic")
        self.commit({"a.py": "x = 1\n# task 3\n", "b.py": "y = 2\n"})
        self.assertEqual(self.lint("--base", "main", "b.py")[:2], (0, []))
        self.assertEqual(self.lint("--base", "main", "a.py")[:2], (1, ["a.py:2: stale reference: task 3"]))


if __name__ == "__main__":
    unittest.main()
