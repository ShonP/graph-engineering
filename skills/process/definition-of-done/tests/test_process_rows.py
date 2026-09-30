"""Golden checks for the definition-of-done matrix and the impact-map and
prior-art rows a planner stamps from it.

Stdlib only; run by scripts/check-skill-scripts.sh. Guards AC-W2-QA-03.
"""

import re
import unittest
from pathlib import Path

PROCESS = Path(__file__).resolve().parents[2]
COLUMNS = 8  # change type + 7 cells


def read(name):
    return (PROCESS / name / "SKILL.md").read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text)


def matrix_rows():
    rows = {}
    for line in read("definition-of-done").splitlines():
        if line.startswith("| **"):
            cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
            rows[re.match(r"\*\*(.+?)\*\*", cells[0]).group(1)] = cells
    return rows


class Matrix(unittest.TestCase):
    def setUp(self):
        self.rows = matrix_rows()

    def row(self, name):
        self.assertIn(name, self.rows, sorted(self.rows))
        return " | ".join(self.rows[name])

    def test_every_row_has_every_column(self):
        for name, cells in self.rows.items():
            self.assertEqual(len(cells), COLUMNS, name)

    def test_refactor_row(self):
        row = self.row("Refactor")
        for needle in ("behaviour contract", "characterization tests", "coverage gap"):
            self.assertIn(needle, row)

    def test_outbound_messaging_row(self):
        row = self.row("Outbound messaging")
        for needle in (
            "read-only dry run", "candidate count", "at most 5 masked ids",
            "kill switch", "NOT RUN counts as BLOCKED",
        ):
            self.assertIn(needle, row)

    def test_host_blast_radius_row(self):
        row = self.row("Host blast radius")
        for needle in ("free disk", "image and cache sizes", "background", "cleanup"):
            self.assertIn(needle, row)

    def test_env_parity_and_clean_checkout_cells(self):
        row = self.row("Config / feature flag / build")
        for needle in (
            "`ci.parity`", "auth, build or flag config", "CI green on the run branch",
            "`git archive $(git write-tree)`", ".gitignore, compose, build or generated paths",
        ):
            self.assertIn(needle, row)

    def test_background_job_cost_cell(self):
        row = self.row("Background job / queue consumer")
        for needle in ("cost per run times frequency", "kill switch", "Important"):
            self.assertIn(needle, row)


class Neighbours(unittest.TestCase):
    def test_impact_map_contracts_row(self):
        row = next(line for line in read("impact-map").splitlines() if line.startswith("| Contracts |"))
        for needle in ("outbound effects", "cron rows, notifiers, publishers", "producers and consumers", "new predicate reads"):
            self.assertIn(needle, row)

    def test_prior_art_memory_is_a_claim(self):
        text = flat(read("prior-art"))
        self.assertRegex(text, r"Memory files and earlier notes are claims \(rung 5\) until re-verified")


class Wording(unittest.TestCase):
    def test_no_em_dashes(self):
        for name in ("definition-of-done", "impact-map", "prior-art"):
            self.assertNotIn("\u2014", read(name), name)


if __name__ == "__main__":
    unittest.main()
