"""Contract tests for commands/graph-init.md: generic, upgrade-safe, proposals validated.

The command is prose an agent follows, so these tests pin what must be in it:
the --upgrade flow, the dependency table referenced (never copied), and every
proposed graph-checks.json argv accepted by the hooks' own loader.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMAND = ROOT / "commands" / "graph-init.md"
sys.path.insert(0, str(ROOT / "hooks" / "scripts"))

import checks_config  # noqa: E402

MANIFESTS = ["package.json", "pyproject.toml", "go.mod", "Cargo.toml", "Package.swift", ".xcodeproj",
             "build.gradle", "pom.xml", "Gemfile", "supabase/config.toml"]
DENY = ["Bash(docker system prune -a*)", "Bash(git filter-branch*)", "Bash(git filter-repo*)",
        "Bash(git push --force origin <default>*)", "Bash(git push -f origin <default>*)",
        "Bash(supabase db reset*)"]
SOCIAL = ["x.com", "twitter.com", "linkedin.com", "instagram.com", "facebook.com"]
# (block, argv) pairs the proposal table must contain; placeholders stay literal.
PROPOSED = {
    ("test", ("uv", "run", "test")), ("test", ("<pm>", "run", "test")), ("test", ("task", "test")),
    ("test", ("make", "<target>")), ("test", ("go", "test", "./...")), ("test", ("cargo", "test")),
    ("lint", ("uv", "run", "ruff", "check", "{file}")), ("lint", ("swiftlint", "lint", "{file}")),
    ("lint", ("pnpm", "exec", "eslint", "{file}")), ("precheck", ("docker", "info")),
    # the default runner of every stack the routing table claims: Python, Swift, Gradle, Maven
    ("test", ("uv", "run", "pytest")), ("test", ("poetry", "run", "pytest")), ("test", ("swift", "test")),
    ("test", ("./gradlew", "test")), ("test", ("./mvnw", "test")), ("test", ("mvn", "test")),
}


def text():
    return COMMAND.read_text()


def frontmatter():
    body = text().split("---\n")
    return body[1]


def section(title):
    """The text from a line containing `title` to the next numbered step or heading."""
    lines = text().split("\n")
    start = next(i for i, line in enumerate(lines) if title in line)
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^(\d+\. \*\*|#)", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def proposal_rows():
    """(block, argv, extensions) for every table row in the graph-checks proposal."""
    rows = []
    for line in section("**Propose `.claude/graph-checks.json`").split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
        if len(cells) >= 3 and cells[1] in ("test", "lint", "precheck"):
            argv = json.loads(cells[2].strip("`"))
            ext = json.loads(cells[3].strip("`")) if len(cells) > 3 and cells[3] else None
            rows.append((cells[1], argv, ext))
    return rows


class GraphInitCommandTests(unittest.TestCase):
    def test_frontmatter_keeps_owner_only_and_adds_upgrade(self):
        fm = frontmatter()
        self.assertIn("disable-model-invocation: true", fm)
        hint = re.search(r'argument-hint: "(.*)"', fm).group(1)
        self.assertIn("--force", hint)
        self.assertIn("--upgrade", hint)

    def test_no_consumer_specific_names_or_em_dashes(self):
        pattern = re.compile(r"apps/\*/web|forge|koach|fitness", re.IGNORECASE)
        hits = [n for n, line in enumerate(text().split("\n"), 1) if pattern.search(line)]
        self.assertEqual(hits, [])
        self.assertNotIn("\u2014", text())

    def test_upgrade_diffs_then_writes_only_on_approval(self):
        up = section("**Upgrade")
        for needle in ("templates/graph-profile.yaml", "missing", "`content`", "`gates.publication`",
                       "schema_version: 2", "unified diff", "approv", "comment"):
            self.assertIn(needle, up, needle)

    def test_routing_is_dependency_derived_from_the_single_table(self):
        routing = section("**Derive routing")
        for manifest in MANIFESTS:
            self.assertIn(manifest, routing, manifest)
        self.assertIn("templates/graph-profile.yaml", routing)
        self.assertIn("gap", routing)
        self.assertIn("rule packs", routing)
        self.assertNotRegex(text(), r'glob: "<dir>/|impl: \[react-rules')

    def test_graph_checks_table_covers_every_detection(self):
        got = {(block, tuple(argv)) for block, argv, _ in proposal_rows()}
        self.assertEqual(PROPOSED - got, set())

    def test_every_proposed_argv_passes_the_hooks_loader(self):
        rows = proposal_rows()
        self.assertTrue(rows)
        for block, argv, ext in rows:
            argv = [{"<pm>": "pnpm", "<target>": "test"}.get(a, a) for a in argv]
            config = {"version": 1, block: {"argv": argv, **({"extensions": ext} if ext else {})}}
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "graph-checks.json"
                path.write_text(json.dumps(config))
                with self.subTest(block=block, argv=argv):
                    checks_config.load(path)

    def test_pytest_is_detected_from_its_config_not_only_a_console_script(self):
        checks = section("**Propose `.claude/graph-checks.json`")
        for needle in ("[tool.pytest.ini_options]", "pytest.ini", "dependency group", "poetry.lock", "gradlew", "mvnw"):
            self.assertIn(needle, checks, needle)

    def test_npm_eslint_never_fetches_from_the_registry(self):
        checks = section("**Propose `.claude/graph-checks.json`")
        self.assertIn('["npm", "exec", "--no", "--", "eslint", "{file}"]', checks)
        self.assertNotIn('["npm", "exec", "eslint"', checks)

    def test_settings_proposal(self):
        settings = section("**Propose `.claude/settings.json`")
        self.assertIn('"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "2"', settings)
        self.assertIn('"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "8"', settings)
        for rule in DENY:
            self.assertIn(rule, settings, rule)
        for domain in SOCIAL:
            self.assertIn(f"WebFetch(domain:{domain})", settings, domain)
            self.assertIn(f"WebFetch(domain:*.{domain})", settings, domain)
        self.assertRegex(settings, r"supabase db reset.*only when.*supabase/")
        block = re.search(r"```json\n(.*?)```", settings, re.S).group(1)
        json.loads(block)

    def test_gitignore_line(self):
        self.assertIn("`.graph/`", section("**Propose the `.gitignore`"))

    def test_printed_notes(self):
        notes = section("**Print the notes")
        for needle in ("MEMORY.md", "4 KB", "subagents", "skillListingMaxDescChars",
                       "--disable-slash-commands", "skillOverrides", "plugin skills"):
            self.assertIn(needle, notes, needle)


if __name__ == "__main__":
    unittest.main()
