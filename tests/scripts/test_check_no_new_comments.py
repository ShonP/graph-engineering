"""check-no-new-comments.py fails on added comment lines, never on directives, strings or old lines.

Every case builds a SYNTHETIC throwaway git repo with GIT_DIR and friends scrubbed.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts" / "check-no-new-comments.py"
GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
ENV = {key: value for key, value in os.environ.items() if key not in GIT_VARS}

COMMENTED = {
    "a.dart": "var a = 1;\n// why\n",
    "b.ts": "const a = 1;\n/* why */\n",
    "c.py": "a = 1\n# why\n",
    "d.sh": "a=1\n# why\n",
    "e.swift": "let a = 1\n/// why\n",
    "f.kt": "val a = 1\n// why\n",
    "g.go": "var a = 1\n// why\n",
    "h.cs": "var a = 1;\n// why\n",
    "i.py": "a = 1  # trailing\n",
}
ALLOWED = {
    "a.dart": "var a = 1; // ignore: unused_local_variable\n",
    "b.ts": "// eslint-disable-next-line no-console\n// @ts-expect-error\nconst s = '// not a comment';\n",
    "c.py": "#!/usr/bin/env python3\nx = 1  # noqa: E501\ny = 2  # type: ignore\ns = '# not a comment'\n",
    "d.sh": "#!/usr/bin/env bash\n# shellcheck disable=SC2086\necho \"${#a}\" $#\n",
    "e.swift": "// swiftlint:disable force_cast\nlet s = \"// no\"\n",
    "g.go": "// SPDX-License-Identifier: MIT\n//go:generate stringer\n",
    "h.cs": "// Copyright 2026 Someone\nvar u = \"http://x\";\n",
}


def run(*args, cwd):
    return subprocess.run(["python3", str(CHECK), *args], cwd=cwd, env=ENV, capture_output=True, text=True)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True)


class CheckNoNewComments(unittest.TestCase):
    def repo(self, base_files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        git(tmp.name, "init", "-q")
        git(tmp.name, "config", "user.email", "t@example.com")
        git(tmp.name, "config", "user.name", "t")
        self.write(tmp.name, base_files)
        git(tmp.name, "add", "-A")
        git(tmp.name, "commit", "-q", "-m", "base")
        return tmp.name

    def write(self, cwd, files):
        for name, text in files.items():
            Path(cwd, name).write_text(text)

    def test_added_comment_in_every_language_fails(self):
        cwd = self.repo({name: text.split("  #")[0].split("\n")[0] + "\n" for name, text in COMMENTED.items()})
        self.write(cwd, COMMENTED)
        result = run("--base", "HEAD", cwd=cwd)
        self.assertEqual(result.returncode, 1, result.stdout)
        for name in COMMENTED:
            self.assertIn(f"{name}:", result.stdout)

    def test_directives_licences_and_strings_pass(self):
        cwd = self.repo({name: "" for name in ALLOWED})
        self.write(cwd, ALLOWED)
        result = run("--base", "HEAD", cwd=cwd)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_untouched_old_comment_passes(self):
        cwd = self.repo({"a.py": "# old\nx = 1\n"})
        Path(cwd, "a.py").write_text("# old\nx = 2\n")
        self.assertEqual(run("--base", "HEAD", cwd=cwd).returncode, 0)

    def test_new_untracked_file_is_scanned(self):
        cwd = self.repo({"keep.txt": "x\n"})
        Path(cwd, "new.py").write_text("x = 1\n# why\n")
        result = run("--base", "HEAD", cwd=cwd)
        self.assertEqual(result.returncode, 1)
        self.assertIn("new.py:2:", result.stdout)

    def test_paths_with_base_narrow_the_diff(self):
        cwd = self.repo({"a.py": "x = 1\n", "b.py": "y = 1\n"})
        self.write(cwd, {"a.py": "x = 1\n# why\n", "b.py": "y = 1\n# why\n"})
        result = run("--base", "HEAD", "a.py", cwd=cwd)
        self.assertEqual((result.returncode, result.stdout), (1, "a.py:2: added code comment\n"))

    def test_unknown_ref_is_a_usage_failure(self):
        cwd = self.repo({"a.py": "x = 1\n"})
        self.assertNotIn(run("--base", "nope", cwd=cwd).returncode, (0, 1))


if __name__ == "__main__":
    unittest.main()
