"""Profile schema v2: the risk table, gate classes and the blocks /graph-init --upgrade adds.

Everything here must hold for any repo (a Python API, a Go CLI, a TS monorepo),
so the assertions are about shape and generic defaults, never a consumer's paths.
"""
import importlib.util
import re
import unittest

from test_profile_template import TEMPLATE, anchor, derived_rows, load_template, matched

HAS_WCMATCH = importlib.util.find_spec("wcmatch") is not None

API_GLOBS = [
    "**/{routers,controllers,endpoints}/**/*.{py,go,java,kt,rb,ts,js}",
    "**/{routes,handlers}/**/*.{py,go,java,kt,rb}",
    "{**/*.controller.{ts,js},**/app/api/**/route.{ts,js},**/pages/api/**/*.{ts,js}}",
    "**/{openapi,asyncapi,swagger}*.{yaml,yml,json}",
]
RISK = [
    ("db-schema", ["**/migrations/**", "**/*.sql", "**/alembic/**"], ["DROP TABLE", "ALTER TABLE"]),
    ("api-surface", API_GLOBS, []),
    ("auth", ["**/{auth,authz,authentication,permissions,rbac}/**"], []),
    ("infra", ["argocd/**", "manifests/**", "**/Chart.yaml", "**/*.tf", ".github/workflows/**"], []),
    ("public-copy", [], []),
    ("outbound-messaging", ["**/{email,emails,mailers,notifications,notifier*}/**"], []),
    ("spend", ["**/{billing,payments}/**"], ["stripe.", "Stripe("]),
    ("destructive", [], ["DROP TABLE", "DROP DATABASE", "DROP SCHEMA", "TRUNCATE TABLE", "DELETE FROM"]),
    ("credentials-and-access", [".sops.yaml", "**/*.enc.{yaml,yml}", "**/.env*"], []),
    ("outside-the-run", [], []),
]
OWNER_CLASSES = ["destructive", "credentials-and-access", "spend", "outbound-messaging"]


def comment_before(key_line):
    """The comment lines directly above (and on) the first line starting with `key_line`."""
    lines = TEMPLATE.read_text().split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith(key_line))
    block = [lines[at]]
    for line in reversed(lines[:at]):
        if not line.lstrip().startswith("#"):
            break
        block.append(line)
    return "\n".join(block)


class SchemaV2Tests(unittest.TestCase):
    def setUp(self):
        self.profile = load_template()

    def test_schema_version_is_the_first_key(self):
        self.assertEqual(self.profile["schema_version"], 2)
        first = next(line for line in TEMPLATE.read_text().split("\n") if line and not line.startswith("#"))
        self.assertEqual(first, "schema_version: 2")

    def test_risk_table_is_exact_and_generic(self):
        rows = self.profile["risk"]
        self.assertEqual([sorted(r) for r in rows], [["id", "keywords", "paths"]] * len(rows))
        self.assertEqual([(r["id"], r["paths"], r["keywords"]) for r in rows], RISK)

    def test_api_surface_is_the_routing_api_rows(self):
        routing = self.profile["routing"]
        api_rows = [k for k, v in routing.items() if k != "always"
                    and "schemathesis" in v.get("impl", [])]
        self.assertEqual(api_rows, API_GLOBS)

    def test_gate_classes_name_risk_ids_or_none(self):
        gates = self.profile["gates"]
        ids = {r["id"] for r in self.profile["risk"]} | {"none"}
        named = gates["owner_classes"] + gates["auto_classes"]
        self.assertEqual([c for c in named if c not in ids], [])

    def test_gate_defaults_keep_the_owner_in_the_loop(self):
        self.assertEqual(self.profile["gates"], {"plan": "owner", "merge": "owner",
                                                 "owner_classes": OWNER_CLASSES, "auto_classes": []})
        text = comment_before("gates:")
        self.assertIn("none", text)
        self.assertIn("full green", text)

    def test_gates_document_only_what_the_engine_honours(self):
        text = comment_before("gates:")
        self.assertNotRegex(text, r"`owner` or `auto`")
        self.assertIn("auto_classes", text)
        self.assertIn("agent-control", text)
        self.assertIn("--auto-merge", text)

    def test_risk_comment_names_the_built_in_control_plane_row(self):
        text = comment_before("risk:")
        for token in ("agent-control", ".claude/**", "CLAUDE.md", "AGENTS.md", ".mcp.json", ".github/**",
                      "instructionPaths", "reserved", "case-insensitive"):
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertNotIn("case-sensitive", text)
        self.assertNotIn("agent-control", [r["id"] for r in self.profile["risk"]])

    def test_host_floor_is_a_profile_key(self):
        self.assertEqual(self.profile["host"], {"min_free_gb": 20})
        text = comment_before("host:")
        self.assertIn("host-check", text)
        self.assertIn("runtime.none", text)

    def test_new_blocks_ship_generic_defaults(self):
        p = self.profile
        self.assertEqual(p["integration"], "pr")
        self.assertEqual(p["localLanes"], {})
        self.assertEqual(p["instructionPaths"], ["CLAUDE.md", "**/CLAUDE.md", "AGENTS.md", ".claude/**"])
        self.assertEqual(p["review"], {"panel_lines": 2000, "seams": []})
        self.assertEqual(p["ownerAccess"], "")
        self.assertEqual(p["ci"], {"parity": ""})

    def test_stale_keys_are_gone(self):
        self.assertNotIn("content", self.profile)
        self.assertNotIn("publication", self.profile["gates"])

    def test_empty_risk_rows_say_who_fills_them(self):
        text = TEMPLATE.read_text()
        self.assertRegex(text, r"- id: public-copy.*\n(\s*#.*\n)*?.*#.*public pages")
        self.assertRegex(text, r"- id: outside-the-run.*\n(\s*#.*\n)*?.*#.*writable_paths")
        self.assertRegex(text, r"- id: outside-the-run.*\n(\s*#.*\n)*?.*#.*graph-control depth --plan")
        self.assertIn("tune", comment_before("risk:"))

    def test_no_em_dashes(self):
        self.assertNotIn("\u2014", TEMPLATE.read_text())


@unittest.skipUnless(HAS_WCMATCH, "needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")
class SyntheticRiskAndRoutingTests(unittest.TestCase):
    """Synthetic layouts (labelled: no real repo), matched with the template's own glob dialect."""

    def setUp(self):
        self.profile = load_template()
        self.derived = derived_rows()

    def classes(self, path):
        rows = {glob: r["id"] for r in self.profile["risk"] for glob in r["paths"]}
        return {rows[k] for k in matched({k: None for k in rows}, path)}

    def test_synthetic_paths_classify(self):
        expected = {
            "api/migrations/0001_init.py": {"db-schema"},
            "db/schema.sql": {"db-schema"},
            "api/app/routers/users.py": {"api-surface"},
            "svc/internal/auth/token.go": {"auth"},
            ".github/workflows/ci.yml": {"infra"},
            "infra/main.tf": {"infra"},
            "web/src/emails/welcome.tsx": {"outbound-messaging"},
            "svc/notifier_slack/send.py": {"outbound-messaging"},
            "svc/billing/invoice.go": {"spend"},
            ".env.local": {"credentials-and-access"},
            "deploy/secrets.enc.yaml": {"credentials-and-access"},
            "README.md": set(),
            "cmd/x/main.go": set(),
        }
        self.assertEqual({p: self.classes(p) for p in expected}, expected)

    def apply(self, when, directory):
        rows = {}
        for row in self.derived:
            if when(row["when"]):
                entry = rows.setdefault(anchor(row["glob"], directory), {})
                for role in ("impl", "review", "qa"):
                    entry[role] = sorted(set(entry.get(role, [])) | set(row.get(role, [])))
        return rows

    def skills(self, rows, path):
        return {s for row in matched(rows, path).values() for skills in row.values() for s in skills}

    def test_synthetic_go_cli_gets_rule_packs_and_a_gap_only(self):
        rows = [r for r in self.derived if "go.mod" in r["when"]]
        self.assertEqual(len(rows), 1)
        self.assertIn("Go", rows[0]["gap"])
        applied = self.apply(lambda w: "go.mod" in w, "")
        self.assertEqual(self.skills(applied, "cmd/x/main.go"), {"backend-rules"})

    def test_synthetic_monorepo_anchors_rows_at_each_manifest(self):
        web = self.apply(lambda w: w.startswith("package.json in <dir> depends on react"), "web")
        api = self.apply(lambda w: re.search(r"depends on (fastapi|pydantic)(\s|$)", w), "api")
        rows = {**web, **api}
        self.assertEqual(sorted(rows), ["api/**/*.py", "web/**/*.{ts,tsx,js,jsx}"])
        self.assertIn("react-rules", self.skills(rows, "web/src/App.tsx"))
        self.assertNotIn("fastapi", self.skills(rows, "web/src/App.tsx"))
        self.assertIn("fastapi", self.skills(rows, "api/app/main.py"))
        self.assertNotIn("react-rules", self.skills(rows, "api/app/main.py"))
        self.assertEqual(self.skills(rows, "api/scripts/build.ts"), set())
        self.assertEqual(self.skills(rows, "web/tools/gen.py"), set())


if __name__ == "__main__":
    unittest.main()
