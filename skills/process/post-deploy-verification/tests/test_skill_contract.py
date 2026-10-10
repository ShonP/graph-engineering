"""Golden checks for the post-deploy skill's signal sources and success baseline.

Stdlib only; run by scripts/check-skill-scripts.sh. Guards AC-W4-MS-06: the
skill names every deploy.checks source kind, how a non-Prometheus source is
read, where baseline.json comes from, and when a bug run re-probes. The
rejection wording is read from scripts/measure_signals.py, so the skill and the
script cannot drift apart.
"""

import importlib.util
import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
TEXT = re.sub(r"\s+", " ", (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"))

spec = importlib.util.spec_from_file_location("measure_signals", ROOT / "scripts" / "measure_signals.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class SignalSources(unittest.TestCase):
    def test_every_source_kind_and_the_default(self):
        self.assertIn("`source: prometheus | sentry | sql-readonly | command`", TEXT)
        self.assertIn("default `prometheus`", TEXT)

    def test_non_prometheus_sources_run_argv_and_read_one_aggregate(self):
        for needle in ("`command` argv", "no shell", '`{"value": <number>}`', "`GRAPH_MEASURE_AT`",
                       f"`{measure.REJECTED}`", "read-only"):
            self.assertIn(needle, TEXT)


class SuccessBaseline(unittest.TestCase):
    def test_baseline_json_is_recorded_at_deployed_at_by_the_script(self):
        for needle in ("`post-deploy/baseline.json`", "`success_signals`", "<plugin-root>/scripts/measure_signals.py",
                       "--baseline --now <deployedAt>", "`no data (no baseline)`"):
            self.assertIn(needle, TEXT)

    def test_late_windows_go_to_the_measure_script(self):
        self.assertIn("`measure.md`", TEXT)
        self.assertIn("success measure(s) due", TEXT)


class BugReprobe(unittest.TestCase):
    def test_reproduce_probe_reruns_only_when_vet_smoke_accepts_it(self):
        match = re.search(r"\*\*Bug runs\*\*[^*]*", TEXT)
        self.assertIsNotNone(match, "a **Bug runs** paragraph")
        for needle in ("`reproduce`", "vet_smoke.py", "`RUN`", "read-only"):
            self.assertIn(needle, match.group(0))


class Generic(unittest.TestCase):
    def test_dash_free_and_names_no_consumer(self):
        body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(chr(0x2014), body)
        # Consumer names: scripts/check-private-names.py, from a list outside the repo.


if __name__ == "__main__":
    unittest.main()
