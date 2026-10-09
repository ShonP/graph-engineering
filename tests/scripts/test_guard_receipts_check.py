"""guard-receipts-check.py: every added guard line has a killed mutation receipt.

Every case builds a SYNTHETIC throwaway repo: a base commit, then a task commit
whose diff is the fixture (a guard, a non-guard change, a test file, a doc),
and a receipts directory holding the JSON `mutate-witness.sh` writes
({file, lines, killed, head, ...}). Git runs with GIT_DIR and friends scrubbed,
as a hook running these tests from a linked worktree would leak its own repo.
Stdlib only.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts" / "guard-receipts-check.py"
GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
ENV = {key: value for key, value in os.environ.items() if key not in GIT_VARS}

BASE_SRC = "def load(path):\n    data = read(path)\n    return data\n"
GUARD_SRC = ("def load(path):\n    data = read(path)\n"
             "    if data is None:\n        raise ValueError('unreadable record')\n    return data\n")


def git(cwd, *args):
    result = subprocess.run(["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null", *args],
                            capture_output=True, text=True, env=ENV, check=False)
    if result.returncode:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result.stdout.strip()


class Repo(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.repo = self.tmp / "repo"
        self.receipts = self.tmp / "mutants"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Test")
        self.write("src/store.py", BASE_SRC)
        self.write("README.md", "# fixture\n")
        self.base = self.commit("base")

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def receipt(self, name, file, lines, killed=True, head=None):
        self.receipts.mkdir(exist_ok=True)
        body = {"file": file, "lines": lines, "find": "is None", "replace": "is not None", "killed": killed,
                "test_exit": 1 if killed else 0, "head": head or git(self.repo, "rev-parse", "HEAD"),
                "observed_at": "2026-10-09T00:00:00Z", "test": ["python3", "-m", "unittest"]}
        (self.receipts / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")

    def check(self, *extra, base=None):
        result = subprocess.run([sys.executable, str(CHECK), base or self.base, str(self.receipts),
                                 "--repo", str(self.repo), *extra],
                                capture_output=True, text=True, env=ENV, check=False)
        return result.returncode, result.stdout, result.stderr


class Coverage(Repo):
    def test_covered_guard_passes(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipt("store-none", "src/store.py", "3-4")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("2 guard lines, 1 receipt", out)

    def test_uncovered_guard_fails_naming_each_line(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("src/store.py:3: if data is None:", out)
        self.assertIn("src/store.py:4: raise ValueError('unreadable record')", out)
        self.assertIn("2 added guard lines have no killed receipt", out)

    def test_non_guard_change_passes_with_no_receipts(self):
        self.write("src/store.py", BASE_SRC.replace("data = read(path)", "data = read(path, encoding='utf-8')"))
        self.commit("read as utf-8")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 guard lines", out)

    def test_receipt_range_must_hold_the_line(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipt("store-none", "src/store.py", "3-3")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertNotIn("src/store.py:3:", out)
        self.assertIn("src/store.py:4:", out)

    def test_surviving_mutant_does_not_cover(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipt("store-none", "src/store.py", "3-4", killed=False)
        self.assertEqual(self.check()[0], 1)

    def test_receipt_for_another_file_does_not_cover(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipt("other", "src/other.py", "3-4")
        self.assertEqual(self.check()[0], 1)


class Scope(Repo):
    def test_tests_docs_and_comments_are_not_guards(self):
        self.write("tests/test_store.py", "def test_x():\n    if True:\n        assert load('x') is None\n")
        self.write("src/store_test.go", "func TestX(t *testing.T) {\n\tif x { t.Fatal() }\n}\n")
        self.write("README.md", "# fixture\n\nif the record is damaged, raise an error.\n")
        self.write("src/store.py", BASE_SRC + "# if the record is damaged we raise below\n")
        self.commit("tests, docs and a comment")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)

    def test_words_in_strings_and_the_main_block_are_not_guards(self):
        self.write("src/cli.py", '"""Exits nonzero: `raise`, `assert` and `if` are the guard words."""\n'
                                 'PATTERN = r"\\b(?:raise|throw)\\b"\n'
                                 "HELP = 'die if the record is unreadable'\n"
                                 'if __name__ == "__main__":\n    main()\n')
        self.commit("strings and a main block")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)

    def test_shell_and_branch_shapes_count_as_guards(self):
        self.write("bin/run.sh", '#!/usr/bin/env bash\n[ -n "$1" ] || die "no target"\nelif true; then :\n'
                                 'echo ok\nexit 2\n')
        self.commit("shell guards")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        flagged = sorted(line.split(":")[1] for line in out.splitlines() if line.startswith("bin/run.sh:"))
        self.assertEqual(flagged, ["2", "3", "5"])

    def test_exclude_glob_skips_a_path(self):
        self.write("generated/api.py", "if x:\n    raise ValueError()\n")
        self.commit("generated code")
        self.assertEqual(self.check()[0], 1)
        self.assertEqual(self.check("--exclude", "generated/*")[0], 0)


class Moves(Repo):
    def test_receipt_follows_lines_shifted_by_a_later_commit(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipt("store-none", "src/store.py", "3-4")
        self.write("src/store.py", "import os\nimport sys\n" + GUARD_SRC)
        self.commit("imports above the guard")
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)

    def test_receipt_is_stale_once_its_guard_is_edited(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipt("store-none", "src/store.py", "3-4")
        self.write("src/store.py", GUARD_SRC.replace("if data is None:", "if not data:"))
        self.commit("treat empty as unreadable")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("src/store.py:3: if not data:", out)


    def test_receipt_is_stale_once_a_line_lands_inside_its_range(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipt("store-none", "src/store.py", "3-4")
        self.write("src/store.py", GUARD_SRC.replace("        raise", "        log(path)\n        raise"))
        self.commit("log before refusing")
        self.assertEqual(self.check()[0], 1)


class Errors(Repo):
    def test_unknown_base_exits_2(self):
        code, _, err = self.check(base="no-such-ref")
        self.assertEqual(code, 2)
        self.assertIn("no-such-ref", err)

    def test_malformed_receipt_is_named_and_ignored(self):
        self.write("src/store.py", GUARD_SRC)
        self.commit("fail closed on an unreadable record")
        self.receipts.mkdir()
        (self.receipts / "broken.json").write_text("{not json", encoding="utf-8")
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("broken.json", err)


if __name__ == "__main__":
    unittest.main()
