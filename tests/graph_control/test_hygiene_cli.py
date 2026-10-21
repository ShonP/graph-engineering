"""hygiene: config defaults and errors, git scope, rule discovery, CLI modes and exit codes."""

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

from hygiene_fixture import commit_at, git, make_repo, stage, write_profile
from graph_control import cli
from graph_control.commands import hygiene as command
from graph_control.common import Invalid
from graph_control.hygiene import doctor_rows, iter_rules
from graph_control.hygiene.config import parse
from graph_control.hygiene.scope import ScopeFile, base, read_text, staged, tracked

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
ALL_MODES = '"staged", "base", "tracked", "run-end", "sweep", "text", "doctor"'
ALPHA = f'''from graph_control.hygiene import Finding
ID = "alpha"
MODES = frozenset({{{ALL_MODES}}})
QUICK = True
LEVELS = []
SEEN = []

def run(ctx):
    SEEN.append(ctx)
    return [Finding(level, ID, "stub " + level, "fix it", "a.txt", 3) for level in LEVELS]

def doctor(ctx):
    return [("warn", "alpha-doctor", "stub doctor", "fix it")]
'''
BETA = '''ID = "beta"
MODES = frozenset({"tracked", "doctor"})
QUICK = False
CALLS = []

def run(ctx):
    CALLS.append(ctx.mode)
    return []

def doctor(ctx):
    return [("info", "beta-doctor", "slow doctor", "none")]
'''

DEFAULTS = {
    "media": {"enabled": True, "max_kb": 500, "deny": [], "allow": []},
    "paths": {"home": "warn"},
    "privateNames": "warn",
    "literals": [],
    "docs": {"roots": [], "ignore": [], "ephemeral": [], "ephemeralDays": 14},
    "context": {"budgets": [], "warn_pct": 80, "builtin": True},
    "comments": {"mode": "any", "allow": []},
    "surfaces": {"roots": [], "idleDays": 30, "minCallers": 1},
    "runEnd": {"mainClean": True, "worktrees": True, "branchMerged": True, "strayFiles": True},
    "measure": {"paths": []},
    "docs_path": None,
    "ux_evidence": {"path": "docs/ux/changes", "store": False},
}

EVERY_KEY = """
docsPath: notes/specs
uxEvidence: {path: media/evidence, store: {push: "acme-widget push", pull: "acme-widget pull"}}
hygiene:
  media: {enabled: false, max_kb: 200, deny: ["**/*.log"], allow: ["assets/**"]}
  paths: {home: error}
  privateNames: off
  literals: [{id: app-host, pattern: "api\\\\.example\\\\.test", owner: ["src/config/**"], allow: ["docs/**"]}]
  docs: {roots: [docs], ignore: ["docs/vendor/**"], ephemeral: ["docs/research/**"], ephemeralDays: 7}
  context: {budgets: [{id: rules, globs: [".claude/rules/*.md"], max_bytes: 9000}], warn_pct: 90, builtin: false}
  comments: {mode: none, allow: ["^# noqa"]}
  surfaces: {roots: [src], idleDays: 60, minCallers: 2}
  runEnd: {mainClean: false, worktrees: false, branchMerged: false, strayFiles: false}
  measure: {paths: ["bench/**"]}
"""

SET = {
    "media": {"enabled": False, "max_kb": 200, "deny": ["**/*.log"], "allow": ["assets/**"]},
    "paths": {"home": "error"},
    "privateNames": "off",
    "literals": [{"id": "app-host", "pattern": "api\\.example\\.test", "owner": ["src/config/**"],
                  "allow": ["docs/**"]}],
    "docs": {"roots": ["docs"], "ignore": ["docs/vendor/**"], "ephemeral": ["docs/research/**"], "ephemeralDays": 7},
    "context": {"budgets": [{"id": "rules", "globs": [".claude/rules/*.md"], "max_bytes": 9000}],
                "warn_pct": 90, "builtin": False},
    "comments": {"mode": "none", "allow": ["^# noqa"]},
    "surfaces": {"roots": ["src"], "idleDays": 60, "minCallers": 2},
    "runEnd": {"mainClean": False, "worktrees": False, "branchMerged": False, "strayFiles": False},
    "measure": {"paths": ["bench/**"]},
    "docs_path": "notes/specs",
    "ux_evidence": {"path": "media/evidence", "store": True},
}


def plain(profile):
    return json.loads(json.dumps(asdict(parse(profile))))


class Defaults(unittest.TestCase):
    def test_absent_block_yields_the_documented_defaults(self):
        for profile in ({}, {"hygiene": None}, None, {"hygiene": {}}):
            with self.subTest(profile=profile):
                self.assertEqual(plain(profile), DEFAULTS)

    def test_every_key_set_to_its_other_state(self):
        self.assertEqual(plain(yaml.safe_load(EVERY_KEY)), SET)

    def test_empty_store_is_not_set(self):
        profile = {"uxEvidence": {"store": {"push": "", "pull": ""}}}
        self.assertEqual(plain(profile)["ux_evidence"], {"path": "docs/ux/changes", "store": False})

    def test_literal_allow_defaults_to_empty(self):
        row = {"id": "app-host", "pattern": "x", "owner": ["src/**"]}
        self.assertEqual(plain({"hygiene": {"literals": [row]}})["literals"], [{**row, "allow": []}])


class Errors(unittest.TestCase):
    def assertNames(self, hygiene, key):
        with self.assertRaises(Invalid) as caught:
            parse({"hygiene": hygiene})
        self.assertIn(key, str(caught.exception))

    def test_unknown_keys_at_every_level_name_the_dotted_key(self):
        cases = [({"medai": {}}, "hygiene.medai"),
                 ({"media": {"maxkb": 1}}, "hygiene.media.maxkb"),
                 ({"literals": [{"id": "a", "pattern": "b", "owner": [], "extra": 1}]}, "hygiene.literals[0].extra"),
                 ({"context": {"budgets": [{"id": "a", "globs": [], "max_bytes": 1, "cap": 2}]}},
                  "hygiene.context.budgets[0].cap")]
        for hygiene, key in cases:
            with self.subTest(key=key):
                self.assertNames(hygiene, key)

    def test_wrong_types_name_the_dotted_key(self):
        cases = [({"media": {"max_kb": "x"}}, "hygiene.media.max_kb"),
                 ({"media": {"max_kb": True}}, "hygiene.media.max_kb"),
                 ({"media": {"max_kb": 0}}, "hygiene.media.max_kb"),
                 ({"media": {"enabled": "yes"}}, "hygiene.media.enabled"),
                 ({"media": {"deny": "**/*.png"}}, "hygiene.media.deny"),
                 ({"media": []}, "hygiene.media"),
                 ({"paths": {"home": "loud"}}, "hygiene.paths.home"),
                 ({"privateNames": True}, "hygiene.privateNames"),
                 ({"comments": {"mode": "some"}}, "hygiene.comments.mode"),
                 ({"comments": {"allow": [3]}}, "hygiene.comments.allow"),
                 ({"context": {"warn_pct": 101}}, "hygiene.context.warn_pct"),
                 ({"context": {"budgets": [{"id": "a", "globs": ["x"], "max_bytes": -1}]}},
                  "hygiene.context.budgets[0].max_bytes"),
                 ({"literals": [{"id": "a", "owner": ["x"]}]}, "hygiene.literals[0].pattern"),
                 ({"literals": {"id": "a"}}, "hygiene.literals"),
                 ({"runEnd": {"worktrees": None}}, "hygiene.runEnd.worktrees"),
                 ("on", "hygiene")]
        for hygiene, key in cases:
            with self.subTest(key=key, hygiene=hygiene):
                self.assertNames(hygiene, key)

    def test_globs_must_be_repo_relative(self):
        for glob in ("/etc/**", "~/notes/**", "../sibling/**", "docs/../../out/**", ""):
            for hygiene, key in (({"media": {"allow": [glob]}}, "hygiene.media.allow"),
                                 ({"measure": {"paths": [glob]}}, "hygiene.measure.paths"),
                                 ({"literals": [{"id": "a", "pattern": "b", "owner": [glob]}]},
                                  "hygiene.literals[0].owner")):
                with self.subTest(glob=glob, key=key):
                    self.assertNames(hygiene, key)


class Temp(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name).resolve()

    def package(self, files):
        name = "stub_rules_" + uuid.uuid4().hex[:8]
        folder = self.tmp / "pkgs" / name
        folder.mkdir(parents=True)
        for filename, body in {"__init__.py": "", **files}.items():
            (folder / filename).write_text(body)
        sys.path.insert(0, str(folder.parent))
        self.addCleanup(sys.path.remove, str(folder.parent))
        return name


def row(path, status, data, binary=False, readable=True):
    return ScopeFile(path, status, len(data), binary, readable)


class Scope(Temp):
    def test_states_empty_staged_committed_modified(self):
        root = make_repo(self.tmp)
        self.assertEqual(staged(root), [])
        stage(root, "a.txt", "hello")
        self.assertEqual(staged(root), [row("a.txt", "A", "hello")])
        first = commit_at(root, "first", 3, NOW)
        self.assertEqual((staged(root), base(root, first)), ([], []))
        self.assertEqual(tracked(root), [row("a.txt", "A", "hello")])
        blob = b"\x00\x01\x02" * 40
        stage(root, "a.txt", "hello world")
        stage(root, "dir name/é b.bin", blob)
        self.assertEqual(staged(root), [row("a.txt", "M", "hello world"), row("dir name/é b.bin", "A", blob, True)])
        commit_at(root, "second", 1, NOW)
        expected = [row("a.txt", "M", "hello world"), row("dir name/é b.bin", "A", blob, True)]
        self.assertEqual(base(root, first), expected)
        self.assertEqual(tracked(root), [row("a.txt", "A", "hello world"), row("dir name/é b.bin", "A", blob, True)])

    def test_deletions_never_listed_and_rename_is_an_add(self):
        root = make_repo(self.tmp)
        stage(root, "a.txt", "alpha")
        stage(root, "b.txt", "bravo")
        first = commit_at(root, "first", 2, NOW)
        git(root, "rm", "-q", "a.txt")
        git(root, "mv", "b.txt", "c.txt")
        self.assertEqual(staged(root), [row("c.txt", "A", "bravo")])
        commit_at(root, "second", 1, NOW)
        self.assertEqual(base(root, first), [row("c.txt", "A", "bravo")])
        self.assertEqual(tracked(root), [row("c.txt", "A", "bravo")])

    def test_base_accepts_a_rev_that_is_not_an_ancestor(self):
        root = make_repo(self.tmp)
        stage(root, "a.txt", "alpha")
        commit_at(root, "first", 3, NOW)
        git(root, "checkout", "-q", "-b", "side")
        stage(root, "side.txt", "side")
        side = commit_at(root, "side", 2, NOW)
        git(root, "checkout", "-q", "main")
        stage(root, "main.txt", "main")
        commit_at(root, "main", 1, NOW)
        self.assertEqual(base(root, side), [row("main.txt", "A", "main")])

    def test_unknown_rev_is_invalid(self):
        root = make_repo(self.tmp)
        stage(root, "a.txt", "alpha")
        commit_at(root, "first", 1, NOW)
        for rev in ("nope", "--output=/tmp/x"):
            with self.subTest(rev=rev), self.assertRaisesRegex(Invalid, "nope|--output"):
                base(root, rev)

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_unreadable_file_is_listed_and_read_text_skips_it(self):
        root = make_repo(self.tmp)
        path = stage(root, "locked.txt", "secret")
        stage(root, "blob.bin", b"\x00" * 8)
        stage(root, "plain.txt", "plain")
        path.chmod(0)
        self.addCleanup(path.chmod, 0o644)
        files = {item.path: item for item in staged(root)}
        self.assertEqual(files["locked.txt"], row("locked.txt", "A", "secret", readable=False))
        self.assertEqual([read_text(root, files[name]) for name in ("locked.txt", "blob.bin", "plain.txt")],
                         [None, None, "plain"])


class Rules(Temp):
    def test_discovery_skips_private_config_and_scope(self):
        name = self.package({"alpha.py": ALPHA, "beta.py": BETA, "_helper.py": "X = 1\n",
                             "config.py": "X = 1\n", "scope.py": "X = 1\n"})
        self.assertEqual([rule.ID for rule in iter_rules(name)], ["alpha", "beta"])

    def test_plugin_package_holds_only_rules(self):
        self.assertTrue(all(isinstance(rule.ID, str) for rule in iter_rules()))

    def test_contract_breaches_raise_type_error_naming_the_module(self):
        cases = {"no_id": ALPHA.replace('ID = "alpha"', ""),
                 "no_run": ALPHA.replace("def run(ctx)", "def other(ctx)"),
                 "set_modes": ALPHA.replace("MODES = frozenset(", "MODES = set("),
                 "bad_mode": ALPHA.replace('"sweep"', '"weekly"'),
                 "no_quick": ALPHA.replace("QUICK = True", ""),
                 "doctor_unlisted": ALPHA.replace(', "doctor"', ""),
                 "listed_no_doctor": BETA.replace("def doctor(ctx)", "def other(ctx)")}
        for module, body in cases.items():
            with self.subTest(module=module):
                name = self.package({f"{module}.py": body})
                with self.assertRaisesRegex(TypeError, module):
                    list(iter_rules(name))

    def test_doctor_rows_quick_subset_and_invalid_config(self):
        name = self.package({"alpha.py": ALPHA, "beta.py": BETA})
        full = doctor_rows({}, self.tmp, False, package=name)
        self.assertEqual(full, [("warn", "alpha-doctor", "stub doctor", "fix it"),
                                ("info", "beta-doctor", "slow doctor", "none")])
        self.assertEqual(doctor_rows({}, self.tmp, True, package=name), full[:1])
        [(level, ident, message, fix)] = doctor_rows({"hygiene": {"medai": {}}}, self.tmp, False, package=name)
        self.assertEqual((level, ident), ("error", "hygiene-invalid"))
        self.assertIn("hygiene.medai", message + fix)


class Cli(Temp):
    def setUp(self):
        super().setUp()
        self.rules = self.package({"alpha.py": ALPHA, "beta.py": BETA})
        self.alpha = importlib.import_module(f"{self.rules}.alpha")
        self.beta = importlib.import_module(f"{self.rules}.beta")
        self.root = make_repo(self.tmp)
        stage(self.root, "a.txt", "alpha")
        self.first = commit_at(self.root, "first", 1, NOW)
        module = SimpleNamespace(NAME=command.NAME, HELP=command.HELP, add_arguments=command.add_arguments,
                                 run=lambda args: command.run(args, package=self.rules, now=NOW))
        self.modules = [module]

    def invoke(self, *argv, root=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["hygiene", "--root", str(root or self.root), *argv], modules=self.modules)
        return code, json.loads(out.getvalue())

    def test_scope_flags_are_exactly_one(self):
        for argv in ([], ["--staged", "--tracked"], ["--text", "x.md", "--staged"], ["--sweep", "--base", "HEAD"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as caught:
                self.invoke(*argv)
            self.assertEqual(caught.exception.code, 2)

    def test_blocked_inputs(self):
        cases = [(["--staged", "--only", "nope"], "nope.*alpha, beta"),
                 (["--text", str(self.tmp / "missing.md")], "missing.md"),
                 (["--base", "no-such-rev"], "no-such-rev")]
        for argv, reason in cases:
            with self.subTest(argv=argv):
                code, out = self.invoke(*argv)
                self.assertEqual((code, out["status"]), (1, "BLOCKED"))
                self.assertRegex(out["reason"], reason)

    def test_error_finding_fails_with_exit_one(self):
        self.alpha.LEVELS[:] = ["error"]
        self.assertEqual(self.invoke("--staged"), (1, {"status": "FAIL", "findings": [
            {"level": "error", "id": "alpha", "message": "stub error", "fix": "fix it", "path": "a.txt", "line": 3}]}))

    def test_warn_only_and_no_findings_pass(self):
        self.alpha.LEVELS[:] = ["warn"]
        code, out = self.invoke("--tracked")
        self.assertEqual((code, out["status"], [f["level"] for f in out["findings"]]), (0, "PASS", ["warn"]))
        self.alpha.LEVELS[:] = []
        self.assertEqual(self.invoke("--tracked"), (0, {"status": "PASS", "findings": []}))

    def test_not_a_repo_and_profile_error_first(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        code, out = self.invoke("--staged", root=plain)
        self.assertEqual((code, out["status"]), (1, "BLOCKED"))
        self.assertIn("not a git repository", out["reason"])
        write_profile(plain, "hygiene: {medai: {}}\n")
        code, out = self.invoke("--staged", root=plain)
        self.assertIn("hygiene.medai", out["reason"])
        self.assertNotIn("not a git repository", out["reason"])

    def test_three_profiles_through_the_cli(self):
        for text, expected in (("schema_version: 2\n", None), ("hygiene: {medai: {}}\n", "hygiene.medai"),
                               ('hygiene: {media: {max_kb: "x"}}\n', "hygiene.media.max_kb")):
            with self.subTest(text=text):
                write_profile(self.root, text)
                code, out = self.invoke("--staged")
                if expected is None:
                    self.assertEqual((code, out["status"]), (0, "PASS"))
                    self.assertEqual(self.alpha.SEEN[-1].config, parse({}))
                else:
                    self.assertEqual((code, out["status"]), (1, "BLOCKED"))
                    self.assertIn(expected, out["reason"])

    def test_run_end_status_and_context(self):
        write_profile(self.root, "integration: push-main\n")
        self.alpha.LEVELS[:] = ["error", "info", "error"]
        code, out = self.invoke("--run-end", "run-1", "--branch", "feature/acme-widget")
        self.assertEqual((code, out["status"], out["run_end"]), (1, "FAIL", "DIRTY (2)"))
        ctx = self.alpha.SEEN[-1]
        self.assertEqual((ctx.mode, ctx.run_id, ctx.branch, ctx.integration, ctx.now, ctx.root),
                         ("run-end", "run-1", "feature/acme-widget", "push-main", NOW, self.root))
        self.assertTrue((ctx.plugin_root / "scripts" / "graph-control.py").is_file())
        self.alpha.LEVELS[:] = ["info"]
        code, out = self.invoke("--run-end", "run-1", "--integration", "pr")
        self.assertEqual((code, out["run_end"], self.alpha.SEEN[-1].integration), (0, "CLEAN", "pr"))

    def test_context_per_mode_and_mode_filter(self):
        note = self.tmp / "body.md"
        note.write_text("text")
        stage(self.root, "b.txt", "bravo")
        cases = [(["--staged"], "staged", ["b.txt"]), (["--base", self.first], "base", []),
                 (["--tracked"], "tracked", ["a.txt", "b.txt"]), (["--sweep"], "sweep", ["a.txt", "b.txt"]),
                 (["--text", str(note)], "text", [])]
        for argv, mode, paths in cases:
            with self.subTest(mode=mode):
                self.assertEqual(self.invoke(*argv)[0], 0)
                ctx = self.alpha.SEEN[-1]
                self.assertEqual((ctx.mode, [item.path for item in ctx.files]), (mode, paths))
        self.assertEqual(self.alpha.SEEN[-1].text, note)
        self.assertEqual(self.alpha.SEEN[1].base, self.first)
        self.assertEqual(self.beta.CALLS, ["tracked"])
        self.invoke("--tracked", "--only", "beta")
        self.assertEqual((len(self.alpha.SEEN), self.beta.CALLS), (5, ["tracked", "tracked"]))

    def test_only_git_is_started(self):
        calls = []
        real = subprocess.run

        def recorder(argv, *args, **kwargs):
            calls.append(argv)
            return real(argv, *args, **kwargs)

        note = self.tmp / "body.md"
        note.write_text("text")
        write_profile(self.root, "gates: {quick: \"touch should-not-exist\"}\n")
        with mock.patch("subprocess.run", recorder):
            for argv in (["--staged"], ["--base", self.first], ["--tracked"], ["--run-end", "run-1"],
                         ["--sweep"], ["--text", str(note)]):
                self.assertEqual(self.invoke(*argv)[0], 0)
            doctor_rows({}, self.root, False)
        self.assertTrue(calls)
        self.assertEqual({argv[0] for argv in calls}, {"git"})
        self.assertFalse((self.root / "should-not-exist").exists())


if __name__ == "__main__":
    unittest.main()
