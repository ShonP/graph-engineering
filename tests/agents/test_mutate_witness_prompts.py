"""The mutation witness runs through one script and leaves a receipt (AC-W4-MW-06).

Golden greps over prompt text: review-protocol and both implementer agents name
the script and its receipt, and no instruction under agents/ or skills/process
teaches an in-place `sed -i` mutation. The script's behaviour is covered by
skills/process/review-protocol/tests/test_mutate_witness.sh. Stdlib only.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "skills/process/review-protocol/SKILL.md"
SCRIPT = ROOT / "skills/process/review-protocol/scripts/mutate-witness.sh"
IMPLEMENTERS = (ROOT / "agents/implementer.md", ROOT / "agents/implementer-simple.md")
# App names and stack tools that would tie the witness to one consumer repo.
CONSUMER_SPECIFIC = ("koach", "fitness", "supabase", "pnpm", "xcodebuild", "swiftui", "nestjs", "fastapi")
EM_DASH = chr(0x2014)


def flat(text):
    """Prose with its line wrapping removed, so a check does not depend on where a line breaks."""
    return " ".join(text.split())


class MutationWitness(unittest.TestCase):
    def test_review_protocol_reads_the_receipt(self):
        body = flat(PROTOCOL.read_text(encoding="utf-8"))
        for needle in ("mutate-witness.sh", "receipt", "`killed: false`", "no receipt", "Important"):
            with self.subTest(needle=needle):
                self.assertTrue(needle in body, f"review-protocol lacks {needle!r}")
        self.assertTrue(re.search(r"surviving mutant[^.]*Important", body), "a surviving mutant is not Important")

    def test_implementers_run_the_script_and_report_receipts(self):
        for path in IMPLEMENTERS:
            body = flat(path.read_text(encoding="utf-8"))
            for needle in ("scripts/mutate-witness.sh", "--receipt", "receipt path",
                           "each new guard or validation", "never mutate files in the shared worktree"):
                with self.subTest(agent=path.stem, needle=needle):
                    self.assertTrue(needle in body, f"{path.stem} lacks {needle!r}")

    def test_implementers_run_the_receipt_coverage_gate_before_done(self):
        for path in IMPLEMENTERS:
            body = flat(path.read_text(encoding="utf-8"))
            for needle in ("python3 <plugin root>/scripts/guard-receipts-check.py", "before reporting `DONE`",
                           ".graph/<run>/mutants", "--repo", "give `--lines` the branch and its refusal"):
                with self.subTest(agent=path.stem, needle=needle):
                    self.assertTrue(needle in body, f"{path.stem} lacks {needle!r}")
        protocol = flat(PROTOCOL.read_text(encoding="utf-8"))
        self.assertTrue(re.search(r"guard-receipts-check\.py.{0,400}neither covers nor names.{0,80}Important", protocol),
                        "review-protocol does not make an unnamed uncovered guard line Important")

    def test_no_in_place_sed_mutation_guidance(self):
        hits = []
        for base in (ROOT / "agents", ROOT / "skills/process"):
            for path in sorted(base.rglob("*")):
                if not path.is_file() or path.suffix not in (".md", ".sh", ".py"):
                    continue
                for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if "sed -i" in line and re.search(r"mutat|witness", line, re.I):
                        hits.append(f"{path.relative_to(ROOT)}:{n}")
        self.assertEqual(hits, [])

    def test_script_names_the_heavier_alternatives(self):
        header = SCRIPT.read_text(encoding="utf-8").split("\nset ", 1)[0]
        for needle in ("Stryker", "mutmut", "--receipt", "exit"):
            with self.subTest(needle=needle):
                self.assertTrue(needle in header, f"script header lacks {needle!r}")

    def test_script_file_example_runs_through_its_interpreter(self):
        # A Write-tool file is 0644, so a bare path exits 127 and the baseline is refused.
        header = SCRIPT.read_text(encoding="utf-8").split("\nset ", 1)[0]
        self.assertIn("-- bash /abs/run/witness-test.sh", header)
        self.assertNotRegex(header, r"-- /abs/run/")

    def test_new_text_is_generic_and_plain(self):
        for path in (SCRIPT, PROTOCOL, *IMPLEMENTERS):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertFalse(EM_DASH in text, f"{path.name} has an em dash")
        body = SCRIPT.read_text(encoding="utf-8").lower()
        for word in CONSUMER_SPECIFIC:
            with self.subTest(word=word):
                self.assertFalse(word in body, f"script names {word!r}")


if __name__ == "__main__":
    unittest.main()
