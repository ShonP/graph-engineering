"""hygiene docs rule: backticked repo paths and path:line cites resolve against the tracked tree."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hygiene_fixture import commit_at, make_repo, stage, write_profile
from graph_control import cli

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
REAL = "".join(f"line {n}\n" for n in range(1, 11))
CITES = """# Guide

See `scripts/missing.py` for the old entry.
The limit lives at `scripts/real.py:999`.
The entry is `scripts/real.py:3` and `scripts/real.py:2-10`.
Skills: `skills/**/SKILL.md`, placeholder `<docsPath>/x.md`, url `https://x.test/a/b`.
Sources `src/{a,b}.ts`, generated `build/out.md`, dir `scripts/` and `scripts`.
"""


def finding_keys(result):
    return sorted((f["level"], f["id"], f["path"], f["line"]) for f in result["findings"])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = make_repo(self.tmp)
        stage(self.root, "scripts/real.py", REAL)
        stage(self.root, "skills/acme-widget/SKILL.md", "# acme-widget\n")
        stage(self.root, "src/a.ts", "export {}\n")
        stage(self.root, "notes/plan.md", "plan\n")

    def profile(self, roots='"docs/**/*.md"', ignore=""):
        write_profile(self.root, 'hygiene: {docs: {roots: [%s], ignore: [%s]}}\n' % (roots, ignore))

    def invoke(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["hygiene", "--root", str(self.root), "--only", "docs", *argv])
        return code, json.loads(out.getvalue())


class Paths(Base):
    def test_dead_path_and_line_past_the_end_are_errors_at_doc_line(self):
        self.profile(ignore='"build/**"')
        stage(self.root, "docs/guide.md", CITES)
        commit_at(self.root, "docs", 0, NOW)
        code, result = self.invoke("--tracked")
        self.assertEqual(code, 1)
        self.assertEqual(finding_keys(result), [("error", "doc-line", "docs/guide.md", 4),
                                                ("error", "doc-path", "docs/guide.md", 3)])
        by_id = {f["id"]: f for f in result["findings"]}
        self.assertIn("scripts/missing.py", by_id["doc-path"]["message"])
        self.assertIn("docs.ignore", by_id["doc-path"]["fix"])
        self.assertIn("999", by_id["doc-line"]["message"])
        self.assertIn("10", by_id["doc-line"]["message"])

    def test_ignore_unset_reports_the_generated_path(self):
        self.profile()
        stage(self.root, "docs/guide.md", CITES)
        commit_at(self.root, "docs", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertIn(("error", "doc-path", "docs/guide.md", 7), finding_keys(result))

    def test_ignored_doc_is_not_read(self):
        self.profile(ignore='"docs/old/**"')
        stage(self.root, "docs/old/audit.md", "Gone: `scripts/missing.py`.\n")
        commit_at(self.root, "docs", 0, NOW)
        self.assertEqual(self.invoke("--tracked"), (0, {"findings": [], "status": "PASS"}))

    def test_tokens_that_are_not_paths_are_skipped(self):
        self.profile()
        stage(self.root, "docs/skip.md", "\n".join([
            "Flags `-Ivendor/include` and `--out` and `graph-control hygiene --tracked`.",
            "Template `{{ver}}/x.md` and `$HOME/x.md` and `pr|push-main` and `fn(a/b)`.",
            "Absolute `/usr/local/bin` and version `0.18.0` and `a.b` word.",
            "```bash",
            "cat `scripts/fenced.py`",
            "```",
            "Glob that misses `nowhere/**/*.md` is an error.", ""]))
        commit_at(self.root, "docs", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertEqual(finding_keys(result), [("error", "doc-path", "docs/skip.md", 7)])

    def test_bare_file_name_resolves_by_basename(self):
        self.profile()
        stage(self.root, "docs/names.md", "Read `plan.md` and `real.py:10`, not `ghost.md` or `real.py:11`.\n"
                                          "Any `*.py` file, but no `*.rb` file.\n")
        commit_at(self.root, "docs", 0, NOW)
        _, result = self.invoke("--tracked")
        messages = sorted(f["message"] for f in result["findings"])
        self.assertEqual(len(messages), 3)
        self.assertIn("*.rb", messages[0])
        self.assertIn("ghost.md", messages[1])
        self.assertIn("real.py:11", messages[2])

    def test_line_cite_on_a_directory_or_missing_file_is_a_dead_path(self):
        self.profile()
        stage(self.root, "docs/dir.md", "Bad `skills/acme-widget:4` and `scripts/gone.py:1`.\n")
        commit_at(self.root, "docs", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertEqual([f["id"] for f in result["findings"]], ["doc-path", "doc-path"])


class Text(Base):
    def test_text_file_outside_the_repo_resolves_with_roots_empty(self):
        self.profile(roots="")
        commit_at(self.root, "base", 0, NOW)
        body = self.tmp / "run" / "merge.md"
        body.parent.mkdir()
        body.write_text("Changed `scripts/real.py:3`.\nRemoved `scripts/missing.py`.\n", encoding="utf-8")
        code, result = self.invoke("--text", str(body))
        self.assertEqual(code, 1)
        self.assertEqual(finding_keys(result), [("error", "doc-path", str(body), 2)])


class Scope(Base):
    def setUp(self):
        super().setUp()
        self.profile()
        stage(self.root, "docs/one.md", "Dead `scripts/one.py`.\n")
        stage(self.root, "docs/two.md", "Dead `scripts/two.py`.\n")
        self.rev = commit_at(self.root, "docs", 1, NOW)
        stage(self.root, "docs/two.md", "Still dead `scripts/two.py`.\n")
        commit_at(self.root, "edit", 0, NOW)

    def test_base_reports_only_the_changed_doc(self):
        _, result = self.invoke("--base", self.rev)
        self.assertEqual(finding_keys(result), [("error", "doc-path", "docs/two.md", 1)])

    def test_tracked_reports_both(self):
        _, result = self.invoke("--tracked")
        self.assertEqual(finding_keys(result), [("error", "doc-path", "docs/one.md", 1),
                                                ("error", "doc-path", "docs/two.md", 1)])

    def test_roots_empty_reports_nothing(self):
        self.profile(roots="")
        self.assertEqual(self.invoke("--tracked"), (0, {"findings": [], "status": "PASS"}))


if __name__ == "__main__":
    unittest.main()
