"""doctor: profile and plugin health findings (AC-W2-DR-01..03) and the CLI command.

Witness for the installed-version check, read 2026-09-30 from
~/.claude/plugins/installed_plugins.json on the owner's machine (key names only,
no values): top level `version` (int) and `plugins`; `plugins` maps
`<plugin>@<marketplace>` (here `graph-engineering@graph-engineering`) to a list
of install records with the keys `gitCommitSha`, `installPath`, `installedAt`,
`lastUpdated`, `scope` and `version`. Fixtures write that shape under a temporary
CLAUDE_CONFIG_DIR; every value in them is synthetic.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli
from graph_control.commands import iter_commands
from graph_control.common import Invalid
from graph_control.depth import decide
from graph_control.doctor import Finding, diagnose
from graph_control.preflight import read_profile

PLUGIN = Path(__file__).resolve().parents[2]
VERSION = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())["version"]
RUNTIME = "runtime:\n  none: CLI verified through public commands\n"
LIST_ROW = '  - {id: db-schema, paths: ["migrations/**"]}\n'
MAP_ROW = '  db-schema: {paths: ["migrations/**"]}\n'
MEDIA = ("png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "mov")
IGNORED_MEDIA = ".graph/\n" + "".join(f"docs/ux/changes/**/*.{ext}\n" for ext in MEDIA)
STORE = 'uxEvidence:\n  path: "docs/ux/changes"\n  store: {push: "git evidence push", pull: "git evidence pull", link: ""}\n'
QUICK = {"no-profile", "profile-invalid", "schema-version", "stale-key", "checks-missing",
         "version-mismatch", "cannot-determine"}

CLEAN = """\
schema_version: 2
runtime:
  none: CLI verified through public commands
routing:
  always:
    impl: [graph-engineering:prior-art, graph-engineering:review-testing-rules]
    review: [graph-engineering:review-protocol]
  "src/**/*.py":
    impl: [house-style, superpowers:test-driven-development]
policy:
  roles: {implementer: opus, qa: sonnet}
  never: [haiku, fable]
  block_types: [general-purpose]
risk:
  - {id: db-schema, paths: ["migrations/**"]}
gates:
  plan: owner
  merge: owner
  auto_classes: [none]
  owner_classes: [db-schema]
"""


def installed(version=VERSION, key="graph-engineering@graph-engineering"):
    stamp = "2026-09-30T00:00:00Z"
    return {"version": 2, "plugins": {key: [{"scope": "user", "installPath": "/synthetic/cache", "version": version,
                                             "installedAt": stamp, "lastUpdated": stamp, "gitCommitSha": "0" * 40}]}}


class Fixture:
    """A clean git repo plus an isolated git and Claude config; each case mutates one thing."""

    def __init__(self, case: unittest.TestCase):
        base = Path(case.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root, self.config = base / "repo", base / "claude"
        (self.root / ".claude" / "skills" / "house-style").mkdir(parents=True)
        (self.config / "plugins").mkdir(parents=True)
        env = {"CLAUDE_CONFIG_DIR": str(self.config), "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": str(base / "xdg")}
        case.enterContext(mock.patch.dict(os.environ, env))
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text(".graph/\n")
        (self.root / ".claude" / "skills" / "house-style" / "SKILL.md").write_text("---\nname: house-style\n---\n")
        self.profile(CLEAN)
        self.checks('{"version": 1}')
        self.installed(installed())

    def profile(self, text: str) -> None:
        (self.root / ".claude" / "graph-profile.yaml").write_text(text)

    def store(self, block: str) -> None:
        """A profile with this uxEvidence block, and every media type ignored under its path."""
        self.profile(CLEAN + block)
        (self.root / ".gitignore").write_text(IGNORED_MEDIA)

    def checks(self, text: str | None) -> None:
        _write(self.root / ".claude" / "graph-checks.json", text)

    def installed(self, data: dict | None) -> None:
        _write(self.config / "plugins" / "installed_plugins.json", None if data is None else json.dumps(data))


def _write(path: Path, text: str | None) -> None:
    path.unlink(missing_ok=True) if text is None else path.write_text(text)


def ids(findings: list[Finding]) -> set[tuple[str, str]]:
    return {(finding.level, finding.id) for finding in findings}


def swap(old, new):
    return lambda f: f.profile(CLEAN.replace(old, new))


# name -> (mutation on the clean fixture, the only findings expected afterwards)
CASES = {
    "no profile": (lambda f: (f.root / ".claude" / "graph-profile.yaml").unlink(), {("info", "no-profile")}),
    "profile is not YAML": (lambda f: f.profile("routing: [\n"), {("error", "profile-invalid")}),
    "schema_version missing": (swap("schema_version: 2\n", ""), {("warn", "schema-version")}),
    "schema_version 1": (swap("schema_version: 2", "schema_version: 1"), {("warn", "schema-version")}),
    "stale content key": (lambda f: f.profile(CLEAN + "content:\n  voice: plain\n"), {("warn", "stale-key")}),
    "stale gates.publication": (lambda f: f.profile(CLEAN + "  publication: owner\n"), {("warn", "stale-key")}),
    "runtime missing": (swap(RUNTIME, ""), {("error", "runtime-missing")}),
    "graph-checks.json missing": (lambda f: f.checks(None), {("warn", "checks-missing")}),
    "graph-checks.json invalid": (lambda f: f.checks('{"version": 1, "tests": {}}'), {("error", "checks-invalid")}),
    "graph-checks.json not JSON": (lambda f: f.checks("{"), {("error", "checks-invalid")}),
    "policy role on haiku": (swap("qa: sonnet", "qa: haiku"), {("warn", "policy-model")}),
    "policy role on fable": (swap("implementer: opus", "implementer: fable"), {("warn", "policy-model")}),
    "policy never without haiku": (swap("never: [haiku, fable]", "never: [fable]"), {("warn", "policy-never")}),
    "auto class names a missing risk id": (swap("auto_classes: [none]", "auto_classes: [none, spend]"),
                                           {("error", "gates-risk")}),
    "owner class names a missing risk id": (swap("owner_classes: [db-schema]", "owner_classes: [auth]"),
                                            {("error", "gates-risk")}),
    "plan gate set to auto": (swap("plan: owner", "plan: auto"), {("warn", "gates-value")}),
    "merge gate set to auto": (swap("merge: owner", "merge: auto"), {("warn", "gates-value")}),
    "quick gate is a list": (swap("merge: owner", "merge: owner\n  quick: [make, check]"), {("warn", "gates-quick")}),
    "quick gate is a number": (swap("merge: owner", "merge: owner\n  quick: 1"), {("warn", "gates-quick")}),
    "auto class lists agent-control": (swap("auto_classes: [none]", "auto_classes: [none, agent-control]"),
                                       {("warn", "gates-control")}),
    "risk table redefines agent-control": (swap(LIST_ROW, LIST_ROW + "  - {id: agent-control, paths: []}\n"),
                                           {("error", "risk-reserved")}),
    "risk table as a mapping": (swap(LIST_ROW, MAP_ROW), {("error", "risk-shape")}),
    "risk rows as bare ids": (swap(LIST_ROW, "  - db-schema\n"), {("error", "risk-shape")}),
    "routing names an unknown skill": (swap("review: [graph-engineering:review-protocol]",
                                            "review: [graph-engineering:review-protocol, no-such-skill]"),
                                       {("warn", "routing-skill")}),
    "routing names a plugin skill bare": (swap("review: [graph-engineering:review-protocol]", "review: [review-protocol]"),
                                          {("warn", "routing-bare")}),
    "risk keyword is an invalid regex": (swap(LIST_ROW, '  - {id: db-schema, paths: ["migrations/**"], keywords: ["re:("]}\n'),
                                         {("error", "risk-keyword")}),
    "risk keyword nests quantifiers": (swap(LIST_ROW, '  - {id: db-schema, paths: ["migrations/**"], keywords: ["re:(a+)+$"]}\n'),
                                       {("warn", "risk-nested")}),
    ".graph not ignored": (lambda f: (f.root / ".gitignore").write_text("node_modules/\n"), {("warn", "graph-not-ignored")}),
    "evidence store with media not ignored": (lambda f: f.profile(CLEAN + STORE), {("warn", "ux-store-unignored")}),
    "evidence store command not on PATH": (lambda f: f.store(STORE.replace("git evidence pull", "no-such-evidence-cli pull")),
                                           {("warn", "ux-store-command")}),
    "evidence store without pull": (lambda f: f.store(STORE.replace("git evidence pull", "")), {("warn", "ux-store-shape")}),
    "evidence store as one string": (lambda f: f.store('uxEvidence:\n  store: "git evidence"\n'),
                                     {("warn", "ux-store-shape")}),
    "installed version differs": (lambda f: f.installed(installed("0.0.1")), {("warn", "version-mismatch")}),
    "installed_plugins.json absent": (lambda f: f.installed(None), {("info", "cannot-determine")}),
    "plugin not in installed_plugins.json": (lambda f: f.installed(installed(key="other@market")),
                                             {("info", "cannot-determine")}),
}


class Checks(unittest.TestCase):
    def test_clean_fixture_is_silent(self):
        fixture = Fixture(self)
        self.assertEqual(diagnose(fixture.root, PLUGIN, quick=False), [])

    def test_each_check_fires_alone_on_its_fixture(self):  # AC-W2-DR-01
        for name, (mutate, expected) in CASES.items():
            with self.subTest(name):
                fixture = Fixture(self)
                mutate(fixture)
                findings = diagnose(fixture.root, PLUGIN, quick=False)
                self.assertEqual(ids(findings), expected)
                for finding in findings:
                    self.assertTrue(finding.message.strip() and finding.fix.strip(), finding)

    def test_a_quick_gate_command_or_an_empty_one_is_silent(self):
        for value in ('"bash scripts/quick-gate.sh"', '""'):
            with self.subTest(value=value):
                fixture = Fixture(self)
                fixture.profile(CLEAN.replace("merge: owner", f"merge: owner\n  quick: {value}"))
                self.assertEqual(diagnose(fixture.root, PLUGIN, quick=False), [])

    def test_a_mapping_risk_table_gets_the_message_depth_blocks_with(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace(LIST_ROW, MAP_ROW))
        [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        with self.assertRaises(Invalid) as caught:
            decide(fixture.root, "HEAD", read_profile(fixture.root / ".claude" / "graph-profile.yaml"))
        self.assertEqual((finding.level, finding.id, finding.message), ("error", "risk-shape", str(caught.exception)))
        self.assertIn("templates/graph-profile.yaml", finding.fix)

    def test_an_invalid_keyword_regex_gets_the_message_depth_blocks_with(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace(LIST_ROW, '  - {id: db-schema, keywords: ["re:a)"]}\n'))
        [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        with self.assertRaises(Invalid) as caught:
            decide(fixture.root, "HEAD", read_profile(fixture.root / ".claude" / "graph-profile.yaml"))
        self.assertEqual((finding.level, finding.id, finding.message), ("error", "risk-keyword", str(caught.exception)))
        self.assertIn("re:", finding.fix)

    def test_a_bare_plugin_skill_names_the_qualified_form(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace("impl: [graph-engineering:prior-art,", "impl: [prior-art,"))
        [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        self.assertEqual(finding.id, "routing-bare")
        self.assertIn("prior-art", finding.message)
        self.assertIn("graph-engineering:prior-art", finding.fix)
        self.assertNotIn("house-style", finding.message + finding.fix)  # a repo skill stays bare

    def test_messages_name_the_versions(self):
        fixture = Fixture(self)
        fixture.installed(installed("0.0.1"))
        [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        self.assertIn(VERSION, finding.message)
        self.assertIn("0.0.1", finding.message)
        self.assertIn("restart", finding.fix)


class EvidenceStore(unittest.TestCase):
    def test_empty_store_is_todays_behaviour_and_silent(self):
        for block in ('uxEvidence:\n  path: "docs/ux/changes"\n  store: {push: "", pull: "", link: ""}\n',
                      'uxEvidence:\n  path: "docs/ux/changes"\n'):
            with self.subTest(block=block):
                fixture = Fixture(self)
                fixture.profile(CLEAN + block)
                self.assertEqual(diagnose(fixture.root, PLUGIN, quick=False), [])

    def test_a_working_store_with_media_ignored_is_silent(self):
        fixture = Fixture(self)
        fixture.store(STORE)
        self.assertEqual(diagnose(fixture.root, PLUGIN, quick=False), [])

    def test_a_repo_relative_script_resolves(self):
        fixture = Fixture(self)
        (fixture.root / "scripts").mkdir()
        (fixture.root / "scripts" / "evidence.sh").write_text("#!/usr/bin/env bash\n")
        fixture.store(STORE.replace("git evidence pull", "scripts/evidence.sh pull"))
        self.assertEqual(diagnose(fixture.root, PLUGIN, quick=False), [])

    def test_unignored_finding_names_the_extensions_and_the_path(self):
        fixture = Fixture(self)
        fixture.store(STORE)
        (fixture.root / ".gitignore").write_text(IGNORED_MEDIA.replace("docs/ux/changes/**/*.mp4\n", ""))
        [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        self.assertEqual((finding.level, finding.id), ("warn", "ux-store-unignored"))
        self.assertIn(".mp4", finding.message)
        self.assertNotIn(".png", finding.message)
        self.assertIn("docs/ux/changes", finding.fix)

    def test_command_finding_names_the_key_and_runs_nothing(self):
        fixture = Fixture(self)
        fixture.store(STORE.replace('link: ""', 'link: "no-such-evidence-cli link"'))
        calls = []
        real = subprocess.run

        def spy(argv, *args, **kwargs):
            calls.append(argv[0])
            return real(argv, *args, **kwargs)

        with mock.patch("subprocess.run", side_effect=spy):
            [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        self.assertEqual(finding.id, "ux-store-command")
        self.assertIn("uxEvidence.store.link", finding.message)
        self.assertIn("no-such-evidence-cli", finding.message)
        self.assertEqual(set(calls), {"git"})  # doctor never runs a configured command

    def test_quick_mode_skips_the_store_checks(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN + STORE.replace("git evidence pull", "no-such-evidence-cli pull"))
        with mock.patch("subprocess.run", side_effect=AssertionError("quick mode spawned a process")):
            self.assertEqual(diagnose(fixture.root, PLUGIN, quick=True), [])


class Gates(unittest.TestCase):  # AC-W2-DR-03
    def test_missing_risk_id_is_an_error_naming_it(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace("auto_classes: [none]", "auto_classes: [spend]"))
        [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        self.assertEqual((finding.level, finding.id), ("error", "gates-risk"))
        self.assertIn("spend", finding.message)

    def test_agent_control_is_a_known_owner_class_without_a_risk_row(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace("owner_classes: [db-schema]", "owner_classes: [db-schema, agent-control]"))
        self.assertEqual(diagnose(fixture.root, PLUGIN, quick=False), [])

    def test_auto_gate_message_names_the_class_lists(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace("merge: owner", "merge: auto"))
        [finding] = diagnose(fixture.root, PLUGIN, quick=False)
        self.assertIn("gates.merge", finding.message)
        self.assertIn("auto_classes", finding.fix)

    def test_full_mode_needs_no_wcmatch(self):
        """doctor runs where only PyYAML is installed: wcmatch is the glob matcher's pin, not doctor's."""
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace("auto_classes: [none]", "auto_classes: [none, agent-control]"))
        probe = ("import sys; sys.modules['wcmatch'] = None; sys.path.insert(0, sys.argv[1]); "
                 "from pathlib import Path; from graph_control.doctor import diagnose; "
                 "print(sorted(f.id for f in diagnose(Path(sys.argv[2]), Path(sys.argv[3]), quick=False)))")
        result = subprocess.run([sys.executable, "-c", probe, str(PLUGIN / "scripts"), str(fixture.root), str(PLUGIN)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gates-control", result.stdout)

    def test_none_is_accepted_without_any_risk_table(self):
        fixture = Fixture(self)
        body = CLEAN.replace("risk:\n" + LIST_ROW, "")
        fixture.profile(body.replace("owner_classes: [db-schema]", "owner_classes: [none]"))
        self.assertEqual(diagnose(fixture.root, PLUGIN, quick=False), [])


class Quick(unittest.TestCase):  # AC-W2-DR-02
    def broken(self) -> Fixture:
        """Trips every check at once, quick or not."""
        fixture = Fixture(self)
        fixture.checks(None)
        fixture.installed(installed("0.0.1"))
        (fixture.root / ".gitignore").write_text("")
        body = CLEAN.replace("schema_version: 2\n", "").replace(RUNTIME, "")
        body = body.replace("qa: sonnet", "qa: haiku").replace("auto_classes: [none]", "auto_classes: [spend]")
        fixture.profile(body.replace("review: [graph-engineering:review-protocol]", "review: [no-such-skill]")
                        + "content: {}\n")
        return fixture

    def test_quick_runs_no_subprocess_and_only_the_quick_checks(self):
        fixture = self.broken()
        with mock.patch("subprocess.run", side_effect=AssertionError("quick mode spawned a process")), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("quick mode spawned a process")):
            found = {finding.id for finding in diagnose(fixture.root, PLUGIN, quick=True)}
        self.assertEqual(found, {"schema-version", "stale-key", "checks-missing", "version-mismatch"})
        self.assertLessEqual(found, QUICK)

    def test_full_mode_reports_what_quick_skips_errors_first(self):
        findings = diagnose(self.broken().root, PLUGIN, quick=False)
        levels = [finding.level for finding in findings]
        self.assertEqual(levels, sorted(levels, key=["error", "warn", "info"].index))
        found = {finding.id for finding in findings}
        self.assertGreaterEqual(found - QUICK, {"runtime-missing", "policy-model", "gates-risk",
                                                "routing-skill", "graph-not-ignored"})

    def test_quick_reports_no_profile(self):
        fixture = Fixture(self)
        (fixture.root / ".claude" / "graph-profile.yaml").unlink()
        with mock.patch("subprocess.run", side_effect=AssertionError("spawned")):
            self.assertEqual(ids(diagnose(fixture.root, PLUGIN, quick=True)), {("info", "no-profile")})


class Command(unittest.TestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(argv)
        return code, json.loads(out.getvalue())

    def test_registered_and_prints_findings_json(self):
        self.assertIn("doctor", [module.NAME for module in iter_commands()])
        fixture = Fixture(self)
        fixture.checks(None)
        code, data = self.run_cli(["doctor", "--root", str(fixture.root)])
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual([(f["level"], f["id"]) for f in data["findings"]], [("warn", "checks-missing")])
        self.assertEqual(set(data["findings"][0]), {"level", "id", "message", "fix"})

    def test_root_must_be_a_directory(self):
        code, data = self.run_cli(["doctor", "--root", "/nonexistent/graph-doctor-root"])
        self.assertEqual((code, data["status"]), (1, "BLOCKED"))

    def test_quick_flag_skips_full_checks(self):
        fixture = Fixture(self)
        fixture.profile(CLEAN.replace(RUNTIME, ""))
        self.assertEqual(self.run_cli(["doctor", "--root", str(fixture.root), "--quick"])[1]["findings"], [])
        self.assertEqual([f["id"] for f in self.run_cli(["doctor", "--root", str(fixture.root)])[1]["findings"]],
                         ["runtime-missing"])

    @unittest.skipUnless(shutil.which("uv"), "uv not installed")
    def test_entry_point_runs_under_uv(self):
        fixture = Fixture(self)
        result = subprocess.run(["uv", "run", "--quiet", "--script", str(PLUGIN / "scripts" / "graph-control.py"),
                                 "doctor", "--root", str(fixture.root), "--quick"],
                                capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"status": "PASS", "findings": []})


if __name__ == "__main__":
    unittest.main()
