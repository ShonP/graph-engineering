"""hygiene docs rule: backticked repo paths and path:line cites resolve against the tracked tree."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hygiene_fixture import commit_at, git, make_repo, stage, write_profile
from graph_control import cli

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
REAL = "".join(f"line {n}\n" for n in range(1, 11))
CITES = """# Guide

See `scripts/missing.py` for the old entry.
The limit lives at `scripts/real.py:999`.
The entry is `scripts/real.py:3` and `scripts/real.py:2-10`.
Skills: `skills/**/SKILL.md`, placeholder `<docsPath>/x.md`, url `https://x.test/a/b`.
Sources `src/{a,b}.ts`, generated `scripts/generated/out.md`, dir `scripts/` and `scripts`.
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
        stage(self.root, "README.md", "# acme-widget\nread me\n")

    def profile(self, roots='"docs/**/*.md"', ignore=""):
        write_profile(self.root, 'hygiene: {docs: {roots: [%s], ignore: [%s]}}\n' % (roots, ignore))

    def invoke(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["hygiene", "--root", str(self.root), "--only", "docs", *argv])
        return code, json.loads(out.getvalue())


class Paths(Base):
    def test_dead_path_and_line_past_the_end_are_errors_at_doc_line(self):
        self.profile(ignore='"scripts/generated/**"')
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
            "Template `{{ver}}/x.md` and `scripts/{{name}}.py` and `$HOME/x.md` and `pr|push-main` and `fn(a/b)`.",
            "Absolute `/usr/local/bin` and version `0.18.0` and `a.b` word.",
            "```bash",
            "cat `scripts/fenced.py`",
            "```",
            "Glob that misses `skills/**/*.zz` is an error.", ""]))
        commit_at(self.root, "docs", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertEqual(finding_keys(result), [("error", "doc-path", "docs/skip.md", 7)])

    def test_only_tokens_under_a_tracked_top_level_entry_are_claims(self):
        self.profile()
        stage(self.root, "docs/names.md", "\n".join([
            "Run files `plan.md`, `ghost.md`, `real.py:11`, `*.rb`, `research/prior-art.md`.",
            "Consumer paths `argocd/**`, `Cargo.toml`, `manifests/app.yaml:9`.",
            "Top level `README.md` and `README.md:2` exist, `README.md:3` does not.",
            "Under a tracked dir `scripts/real.py:12` is past the end.", ""]))
        commit_at(self.root, "docs", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertEqual(finding_keys(result), [("error", "doc-line", "docs/names.md", 3),
                                                ("error", "doc-line", "docs/names.md", 4)])

    def test_a_moved_file_is_still_flagged(self):
        self.profile()
        stage(self.root, "scripts/old.py", "old\n")
        commit_at(self.root, "old", 1, NOW)
        git(self.root, "mv", "scripts/old.py", "scripts/new.py")
        stage(self.root, "docs/moved.md", "Was `scripts/old.py`, now `scripts/new.py:1`.\n")
        commit_at(self.root, "move", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertEqual(finding_keys(result), [("error", "doc-path", "docs/moved.md", 1)])
        self.assertIn("scripts/old.py", result["findings"][0]["message"])

    def test_line_cite_on_a_directory_missing_file_or_past_a_range_end(self):
        self.profile()
        stage(self.root, "docs/dir.md", "Bad `skills/acme-widget:4` and `scripts/gone.py:1`.\n"
                                        "Range `scripts/real.py:3-11` runs past the end.\n")
        commit_at(self.root, "docs", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertEqual([(f["id"], f["line"]) for f in result["findings"]],
                         [("doc-path", 1), ("doc-path", 1), ("doc-line", 2)])

    def test_cites_resolve_against_the_citing_docs_directory_too(self):
        self.profile(roots='"**/*.md"')
        stage(self.root, "packages/foo/src/index.ts", "export {}\nexport {}\n")
        stage(self.root, "packages/foo/README.md", "\n".join([
            "Entry `./src/index.ts`, `src/index.ts:2` and root `src/a.ts`.",
            "Dead `./src/gone.ts`.",
            "Past the end `src/index.ts:9`.", ""]))
        commit_at(self.root, "monorepo", 0, NOW)
        _, result = self.invoke("--tracked")
        self.assertEqual(finding_keys(result), [("error", "doc-line", "packages/foo/README.md", 3),
                                                ("error", "doc-path", "packages/foo/README.md", 2)])
        self.assertIn("packages/foo/src/index.ts has 2 lines",
                      next(f["message"] for f in result["findings"] if f["id"] == "doc-line"))


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
        self.assertNotIn(f"add {body}", result["findings"][0]["fix"])
        self.assertIn("hygiene.docs.ignore", result["findings"][0]["fix"])

    def test_text_file_inside_the_repo_resolves_from_its_own_directory(self):
        self.profile(roots="")
        stage(self.root, "packages/foo/src/index.ts", "export {}\n")
        commit_at(self.root, "base", 0, NOW)
        body = self.root / "packages" / "foo" / "body.md"
        body.write_text("Entry `src/index.ts`, dead `src/gone.ts`.\n", encoding="utf-8")
        _, result = self.invoke("--text", str(body))
        self.assertEqual([f["message"] for f in result["findings"]], ["`src/gone.ts` does not exist in the tracked tree"])

    def test_text_accepts_paths_the_history_deleted(self):
        self.profile(roots="")
        stage(self.root, "scripts/old.py", "old\n")
        stage(self.root, "scripts/olddir/a.png", "a\n")
        commit_at(self.root, "base", 1, NOW)
        git(self.root, "rm", "-q", "-r", "--", "scripts/old.py", "scripts/olddir")
        commit_at(self.root, "delete", 0, NOW)
        body = self.tmp / "merge.md"
        body.write_text("Deletes `scripts/old.py`, `scripts/old.py:1` and `scripts/olddir`.\n"
                        "Dead `scripts/never.py`.\n", encoding="utf-8")
        _, result = self.invoke("--text", str(body))
        self.assertEqual(finding_keys(result), [("error", "doc-path", str(body), 2)])
        stage(self.root, "docs/old.md", "Was `scripts/old.py`.\n")
        commit_at(self.root, "doc", 0, NOW)
        self.profile()
        _, result = self.invoke("--tracked")
        self.assertEqual(finding_keys(result), [("error", "doc-path", "docs/old.md", 1)])


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
