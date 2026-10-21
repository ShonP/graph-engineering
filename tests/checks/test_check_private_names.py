"""Regression cases for scripts/check-private-names.py.

The plugin is public: tracked text names stacks and tools, never a consumer
product, person or private repo. The banned names live OUTSIDE the repo (a
local file or an env var), so the list itself never leaks. Every case builds a
throwaway git repo and points the check at a list it controls. The names used
here are synthetic placeholders.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts" / "check-private-names.py"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class PrivateNames(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        self.xdg = self.tmp / "xdg"
        self.xdg.mkdir()

    def track(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git(self.repo, "add", rel)

    def names_file(self, text):
        path = self.xdg / "graph-engineering" / "private-names.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_check(self, env_names=None, flags=()):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GRAPH_PRIVATE_NAMES")}
        env["XDG_CONFIG_HOME"] = str(self.xdg)
        if env_names is not None:
            env["GRAPH_PRIVATE_NAMES"] = env_names
        return subprocess.run(
            ["python3", str(CHECK), *flags, str(self.repo)], env=env, capture_output=True, text=True
        )

    def test_no_list_configured_skips_with_a_reason(self):
        self.track("a.md", "acmecorp everywhere\n")
        out = self.run_check()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertRegex(out.stdout, r"(?m)^SKIP check-private-names: no list configured")

    def test_no_list_output_is_byte_identical_without_require(self):
        out = self.run_check()
        listed = self.xdg / "graph-engineering" / "private-names.txt"
        self.assertEqual(out.stdout, f"SKIP check-private-names: no list configured "
                                     f"(set GRAPH_PRIVATE_NAMES or create {listed})\n")
        self.assertEqual((out.returncode, out.stderr), (0, ""))

    def test_require_fails_when_no_list_is_configured(self):
        self.track("a.md", "clean\n")
        listed = self.xdg / "graph-engineering" / "private-names.txt"
        out = self.run_check(flags=("--require",))
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertEqual(out.stdout, f"FAIL check-private-names: no list configured "
                                     f"(set GRAPH_PRIVATE_NAMES or create {listed})\n")

    def test_require_treats_a_comment_only_list_as_unconfigured(self):
        self.names_file("# only a comment\n\n")
        out = self.run_check(flags=("--require",))
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertRegex(out.stdout, r"^FAIL check-private-names: no list configured")
        self.assertEqual(self.run_check(env_names="# none", flags=("--require",)).returncode, 1)

    def test_require_with_a_list_checks_as_usual(self):
        self.track("a.md", "clean\n")
        self.names_file("acmecorp\n")
        out = self.run_check(flags=("--require",))
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertRegex(out.stdout, r"^ok check-private-names: 1 name\(s\), 1 tracked file")
        self.track("b.md", "acmecorp\n")
        out = self.run_check(flags=("--require",))
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("FAIL b.md:1: names a private consumer", out.stdout)

    def test_scan_takes_a_file_list_and_returns_path_and_line_hits(self):
        spec = importlib.util.spec_from_file_location("check_private_names", CHECK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.track("acmecorp/a.md", "clean\nan acmecorp line\n")
        self.track("b.md", "acmecorp\n")
        self.track("c.md", "acmecorp\n")
        (self.repo / "blob.bin").write_bytes(b"\x00acmecorp")
        entries = module.parse(["acmecorp allow=c.md"])
        hits = module.scan(self.repo, ["acmecorp/a.md", "c.md", "blob.bin", "gone.md"], entries)
        self.assertEqual(hits, [("acmecorp/a.md", None), ("acmecorp/a.md", 2)])
        self.assertEqual(module.scan(self.repo, ["b.md"], []), [])

    def test_a_tracked_name_fails_case_insensitively_and_names_the_line(self):
        self.track("docs/a.md", "line one\nShipped for AcmeCorp last week\n")
        self.names_file("acmecorp\n")
        out = self.run_check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("docs/a.md:2", out.stdout)

    def test_word_boundaries_hold(self):
        self.track("a.md", "acmecorps and myacmecorp are other words\n")
        self.names_file("acmecorp\n")
        self.assertEqual(self.run_check().returncode, 0)
        self.track("b.md", "see acmecorp-platform for it\n")
        out = self.run_check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("b.md:1", out.stdout)
        self.assertNotIn("a.md:1", out.stdout)

    def test_compound_identifiers_are_caught(self):
        self.names_file("acmecorp\n")
        shapes = ["AcmecorpKit", "acmecorp_sdk", "AcmecorpSettings", "acmecorp2",
                  "myAcmecorp", "ACMECORP_TOKEN", "_acmecorp"]
        for number, shape in enumerate(shapes):
            with self.subTest(shape=shape):
                self.track(f"c{number}.md", f"x {shape} y\n")
                out = self.run_check()
                self.assertEqual(out.returncode, 1, out.stdout)
                self.assertIn(f"c{number}.md:1", out.stdout)
                git(self.repo, "rm", "-q", "--cached", f"c{number}.md")

    def test_a_longer_word_that_starts_with_a_name_is_not_caught(self):
        self.names_file("equiv\n")
        self.track("a.md", "an equivalent, Equivalents, EQUIVALENT, equivalentKit, unequiv\n")
        out = self.run_check()
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_tracked_paths_are_scanned_and_reported_without_the_name(self):
        self.track("notes/acmecorp-notes.md", "clean\n")
        self.track("AcmecorpKit/a.md", "clean\n")
        self.names_file("acmecorp\n")
        out = self.run_check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("FAIL notes/acmecorp-notes.md: path names a private consumer", out.stdout)
        self.assertIn("FAIL AcmecorpKit/a.md: path names a private consumer", out.stdout)
        self.assertEqual(out.stdout.count("acmecorp-notes"), 1)

    def test_allow_globs_exempt_matching_paths_by_name_too(self):
        self.track("acmecorp/plugin.json", "{}\n")
        self.names_file("acmecorp allow=acmecorp/*\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_untracked_files_are_not_scanned(self):
        self.track("a.md", "clean\n")
        (self.repo / "scratch.md").write_text("acmecorp\n")
        self.names_file("acmecorp\n")
        out = self.run_check()
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertRegex(out.stdout, r"(?m)^ok check-private-names: 1 name\(s\), \d+ tracked file")

    def test_env_list_overrides_the_file_and_ignores_comments(self):
        self.track("a.md", "globex inside\n- a list item\n")
        self.names_file("# a comment\n\n   \nacmecorp\n")
        self.assertEqual(self.run_check().returncode, 0)
        self.assertEqual(self.run_check(env_names="initech; globex").returncode, 1)
        self.assertEqual(self.run_check(env_names="initech\nglobex").returncode, 1)

    def test_env_entries_keep_their_comma_separated_allow_globs(self):
        self.track("x/plugin.json", "globex\n")
        self.track("y/plugin.json", "globex\n")
        self.track("README.md", "globex\n")
        out = self.run_check(env_names="initech; globex allow=x/*,y/*")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("README.md:1", out.stdout)
        self.assertNotIn("plugin.json", out.stdout)

    def test_allow_globs_exempt_only_their_paths(self):
        self.track(".meta/plugin.json", '{"author": "Jane Acmecorp"}\n')
        self.track("README.md", "by Jane Acmecorp\n")
        self.names_file("acmecorp allow=.meta/*.json\n")
        out = self.run_check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("README.md:1", out.stdout)
        self.assertNotIn("plugin.json", out.stdout)

    def test_binary_files_are_skipped(self):
        path = self.repo / "blob.bin"
        path.write_bytes(b"\x00\x01acmecorp\x00")
        git(self.repo, "add", "blob.bin")
        self.names_file("acmecorp\n")
        self.assertEqual(self.run_check().returncode, 0)


class ReadmeGenericity(unittest.TestCase):
    def test_paragraph_names_every_place_the_check_runs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        start = readme.index("**Genericity:**")
        paragraph = " ".join(readme[start:readme.index("\n## ", start)].split())
        for needle in ("`private-names` hygiene rule", "commit guard", "repo gate", "doctor", "`--require`",
                       "`hygiene.privateNames`"):
            self.assertIn(needle, paragraph)

    def test_hooks_section_points_at_the_hygiene_command(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        start = readme.index("## Hooks")
        section = " ".join(readme[start:readme.index("\n## ", start + 1)].split())
        self.assertRegex(section, r"commit guard runs `graph-control hygiene`[^;]*;[^\[]*\[[^\]]*\]\(docs/graph-controls\.md\)")


if __name__ == "__main__":
    unittest.main()
