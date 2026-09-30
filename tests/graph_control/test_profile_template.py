"""Contract tests for the generic profile template and the routing fallback doc.

The template must be right for any repo (TS, Python, Swift, Kotlin, Go, infra):
framework skills come only from the dependency-derived block that /graph-init
applies, never from a static row that fires on a bare file extension.
"""
import importlib.util
import re
import unittest
from pathlib import Path

import yaml

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.preflight import UniqueLoader

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "graph-profile.yaml"
FALLBACK_DOC = ROOT / "docs" / "competency-routing.md"
TITLE = "Dependency-derived rows (applied by /graph-init)"
HAS_WCMATCH = importlib.util.find_spec("wcmatch") is not None

FRAMEWORK = {"react-rules", "tailwind", "forms-i18n", "fastapi", "pydantic", "supabase", "swiftui-pro"}
FRAMEWORK_PREFIXES = ("tanstack-", "compose-")

POLICY = {
    "roles": {"planner": "opus", "ux-designer": "opus", "implementer": "opus", "reviewer": "opus",
              "implementer-simple": "sonnet", "researcher": "sonnet", "qa": "sonnet", "retro": "sonnet"},
    "never": ["haiku", "fable"],
    "block_types": ["general-purpose"],
}

REACT = "<dir>/**/*.{ts,tsx,js,jsx}"
PY = "<dir>/**/*.py"
UI = ["react-rules", "frontend-rules", "ux-evidence"]
FASTAPI = ["fastapi", "backend-rules", "architecture-resilience-rules"]
TEMPORAL = ["temporal-developer", "architecture-resilience-rules"]
MAF = ["microsoft-agent-framework", "agent-workflow-rules"]
PAI = ["building-pydantic-ai-agents", "agent-workflow-rules"]
SUPA = ["supabase", "supabase-postgres-best-practices"]
# (glob, impl, review, qa) for every row the brief names; `when` and `gap` are prose.
DERIVED = [
    (REACT, UI, UI, ["ux-evidence"]),
    (REACT, ["tanstack-query-rules"], ["tanstack-query-rules"], []),
    (REACT, ["tanstack-router"], [], []),
    (REACT, ["tailwind"], ["tailwind"], []),
    ("<dir>/**/*.css", ["tailwind"], ["tailwind"], []),
    (REACT, ["forms-i18n"], ["forms-i18n"], []),
    ("<dir>/**/*.{ts,js}", ["backend-rules"], ["backend-rules"], []),
    ("{**/turbo.json,pnpm-workspace.yaml,**/package.json}", ["turborepo"], ["turborepo"], []),
    (PY, ["pydantic", "pydantic-house-rules"], ["pydantic", "pydantic-house-rules"], []),
    (PY, FASTAPI, FASTAPI, []),
    ("<dir>/**/{models,db,migrations}/**/*.py", ["sqlalchemy"], ["sqlalchemy"], []),
    ("<dir>/**/alembic/**", ["sqlalchemy"], ["sqlalchemy"], []),
    ("<dir>/**/{workflows,activities}/**/*.py", TEMPORAL, TEMPORAL, []),
    ("<dir>/**/agents/**/*.py", MAF, MAF, []),
    ("<dir>/**/agents/**/*.py", PAI, PAI, []),
    ("<dir>/**/logging*.py", ["loguru"], ["loguru"], []),
    ("<dir>/**/{bus,events,messaging}/**", ["nats", "architecture-resilience-rules"],
     ["nats", "architecture-resilience-rules", "security-review"], []),
    ("<dir>/**/*.swift", ["swiftui-pro", "ux-evidence"], ["swiftui-pro", "ux-evidence"], ["ux-evidence"]),
    ("<dir>/**/*.{kt,kts}", ["compose-state", "compose-ui", "ux-evidence"],
     ["compose-performance", "compose-state", "ux-evidence"], ["compose-build-and-test", "ux-evidence"]),
    ("<dir>/supabase/**", SUPA, SUPA, []),
    ("<dir>/**", ["backend-rules"], ["backend-rules"], []),
]


def is_framework(skill):
    return skill in FRAMEWORK or skill.startswith(FRAMEWORK_PREFIXES)


def load_template():
    return yaml.load(TEMPLATE.read_text(), Loader=UniqueLoader)


def routing_lines():
    lines = TEMPLATE.read_text().split("\n")
    start = lines.index("routing:")
    end = next(i for i in range(start + 1, len(lines)) if re.match(r"^[A-Za-z_]", lines[i]))
    return lines[start + 1:end]


def derived_rows():
    """The YAML payload of the commented block: comment lines after `# derived:`."""
    lines = routing_lines()
    body = [line.strip() for line in lines]
    assert any(TITLE in line for line in body), "derived block title missing from routing"
    start = body.index("# derived:")
    payload = []
    for raw in lines[start:]:
        if not raw.strip().startswith("#"):
            break
        payload.append(re.sub(r"^\s*# ?", "", raw))
    return yaml.load("\n".join(payload), Loader=UniqueLoader)["derived"]


def anchor(glob, directory):
    return glob.replace("<dir>/", "") if directory == "" else glob.replace("<dir>", directory)


def matched(rows, path):
    from wcmatch import glob as wglob
    flags = wglob.GLOBSTAR | wglob.BRACE | wglob.DOTGLOB
    return {key: row for key, row in rows.items() if wglob.globmatch(path, key, flags=flags)}


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_template()
        self.static = {k: v for k, v in self.profile["routing"].items() if k != "always"}

    def test_loads_with_unique_loader(self):
        self.assertIsInstance(self.profile, dict)
        self.assertIn("routing", self.profile)

    def test_stacks_ship_empty(self):
        self.assertEqual(self.profile["stacks"], {})

    def test_no_consumer_specific_names(self):
        pattern = re.compile(r"apps/\*/web|forge|koach|fitness", re.IGNORECASE)
        files = [p for p in (ROOT / "templates").rglob("*") if p.is_file()] + [FALLBACK_DOC]
        hits = [f"{p.relative_to(ROOT)}:{n}" for p in files
                for n, line in enumerate(p.read_text().split("\n"), 1) if pattern.search(line)]
        self.assertEqual(hits, [])

    def test_static_rows_route_no_framework_skill(self):
        hits = [(key, role, skill) for key, row in self.static.items()
                for role, skills in row.items() for skill in skills if is_framework(skill)]
        self.assertEqual(hits, [])

    def test_policy_block_is_the_contract(self):
        self.assertEqual(self.profile["policy"], POLICY)

    def test_always_names_stay_bare(self):
        names = [n for skills in self.profile["routing"]["always"].values() for n in skills]
        self.assertTrue(names)
        self.assertEqual([n for n in names if ":" in n], [])

    def test_derived_block_lists_every_row(self):
        rows = derived_rows()
        for row in rows:
            self.assertTrue(row.get("when"), row)
        got = sorted((r["glob"], r.get("impl", []), r.get("review", []), r.get("qa", [])) for r in rows)
        self.assertEqual(got, sorted(DERIVED))
        gaps = [r for r in rows if r.get("gap")]
        self.assertEqual([r["glob"] for r in gaps], ["<dir>/**"])
        for language in ("Go", "Rust", "Ruby", "Java"):
            self.assertIn(language, gaps[0]["gap"])


@unittest.skipUnless(HAS_WCMATCH, "needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")
class SyntheticLayoutTests(unittest.TestCase):
    """Synthetic paths (labelled: no real repo) matched with the template's own dialect."""

    def setUp(self):
        routing = load_template()["routing"]
        self.static = {k: v for k, v in routing.items() if k != "always"}
        self.derived = derived_rows()

    def skills(self, rows, path):
        return {s for row in matched(rows, path).values() for skills in row.values() for s in skills}

    def applied(self, when_word, directory):
        rows = {}
        for row in self.derived:
            if when_word in row["when"]:
                entry = rows.setdefault(anchor(row["glob"], directory), {})
                for role in ("impl", "review", "qa"):
                    entry[role] = sorted(set(entry.get(role, [])) | set(row.get(role, [])))
        return rows

    def test_go_cli_routes_no_framework_skill(self):
        paths = ["go.mod", "cmd/x/main.go", "internal/y.go"]
        self.assertEqual({p: sorted(matched(self.static, p)) for p in paths}, {p: [] for p in paths})
        derived = self.applied("go.mod", "")
        self.assertEqual({s for p in paths for s in self.skills(derived, p)}, {"backend-rules"})

    def test_web_notification_file_skips_push_notifications(self):
        path = "web/src/NotificationBell.tsx"
        self.assertNotIn("push-notifications", self.skills(self.static, path))
        self.assertIn("push-notifications", self.skills(self.static, "ios/App/PushNotificationHandler.swift"))

    def test_python_api_gets_toolchain_only_from_static_rows(self):
        self.assertEqual(self.skills(self.static, "api/app/main.py"), {"uv", "ruff"})
        derived = self.applied("fastapi", "api")
        self.assertIn("fastapi", self.skills(derived, "api/app/main.py"))
        self.assertEqual(self.skills(derived, "web/src/main.py"), set())


class FallbackDocTests(unittest.TestCase):
    """Framework skills in the no-profile tables name the evidence that routes them."""

    EVIDENCE = [
        (re.compile(r"\breact-rules\b"), "depends on react"),
        (re.compile(r"\bsupabase\b(?!-)"), "supabase/config.toml"),
        (re.compile(r"\b(fastapi|pydantic|temporal-developer|microsoft-agent-framework)\b"), "import"),
        (re.compile(r"\bswiftui-pro\b"), "SwiftUI"),
        (re.compile(r"\bcompose-(state|ui|performance)\b"), "Compose"),
    ]

    def test_framework_rows_name_their_evidence(self):
        rows = [line for line in FALLBACK_DOC.read_text().split("\n") if line.startswith("| ")]
        misses = [(row, phrase) for row in rows for skill, phrase in self.EVIDENCE
                  if skill.search(row) and phrase not in row]
        self.assertEqual(misses, [])


if __name__ == "__main__":
    unittest.main()
