"""Profile blocks for wave 4: `pulse` (the investigate lane's signal command) and
`digest` (what the change digest leaves out of LOC). Acceptance rows AC-W4-RP-05.

Generic by construction: every assertion holds for a Python API, a Go CLI, a TS
monorepo or a JVM service, and names no consumer. The paths below are synthetic
(labelled: no real repo).
"""
import importlib.util
import subprocess
import unittest

from test_profile_template import ROOT, TEMPLATE, load_template
from test_profile_v2 import comment_before

HAS_WCMATCH = importlib.util.find_spec("wcmatch") is not None
BRIEF_EXCLUDES = ["**/*.test.*", "**/tests/**", "**/*.stories.*", "**/generated/**"]
CONSUMER_WORDS = ("koach", "fitness", "supabase", "swiftui", "nestjs", "apps/")


class PulseAndDigestBlocks(unittest.TestCase):
    def setUp(self):
        self.profile = load_template()

    def test_pulse_ships_empty(self):
        self.assertEqual(self.profile["pulse"], {"command": ""})

    def test_pulse_comment_says_aggregates_masked_investigate(self):
        text = comment_before("pulse:")
        for needle in ("aggregates-only", "masked", "investigate lane", "signals"):
            self.assertIn(needle, text)

    def test_digest_excludes_start_with_the_generic_four(self):
        exclude = self.profile["digest"]["exclude"]
        self.assertEqual(set(self.profile["digest"]), {"exclude"})
        self.assertEqual(exclude[:4], BRIEF_EXCLUDES)
        self.assertTrue(all(isinstance(g, str) and "{" not in g for g in exclude), exclude)

    def test_digest_comment_says_excluded_from_loc(self):
        text = comment_before("digest:")
        for needle in ("change digest", "LOC", "excluded"):
            self.assertIn(needle, text)

    def test_new_blocks_are_generic(self):
        for key in ("pulse:", "digest:"):
            low = comment_before(key).lower()
            for word in CONSUMER_WORDS:
                self.assertNotIn(word, low, f"{key} names {word!r}")

    def test_routing_still_resolves(self):
        done = subprocess.run(["bash", str(ROOT / "scripts" / "check-routing-resolves.sh"), str(ROOT)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


@unittest.skipUnless(HAS_WCMATCH, "needs wcmatch: uv run --with PyYAML==6.0.2 --with wcmatch==11.0.1")
class SyntheticDigestExcludes(unittest.TestCase):
    """Synthetic paths, matched with the routing glob dialect the comment names."""

    def excluded(self, path):
        from wcmatch import glob
        flags = glob.GLOBSTAR | glob.BRACE | glob.DOTGLOB
        return any(glob.globmatch(path, g, flags=flags) for g in load_template()["digest"]["exclude"])

    def test_test_code_across_stacks_is_excluded(self):
        for path in ("web/src/Button.test.tsx", "web/src/Button.spec.ts", "web/src/Button.stories.tsx",
                     "cmd/cli/main_test.go", "api/tests/test_users.py", "api/app/test_users.py",
                     "svc/src/test/java/FooTest.java", "app/src/androidTest/kotlin/LoginTest.kt",
                     "ios/AppTests/LoginTests.swift", "api/generated/client.py"):
            self.assertTrue(self.excluded(path), path)

    def test_product_code_counts(self):
        for path in ("web/src/Button.tsx", "cmd/cli/main.go", "api/app/users.py",
                     "svc/src/main/java/Foo.java", "ios/App/LoginView.swift", "README.md"):
            self.assertFalse(self.excluded(path), path)


if __name__ == "__main__":
    unittest.main()
