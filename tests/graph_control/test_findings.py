"""findings.json v1: schema validation, open-finding counts and the `findings` command.

Every fixture here is synthetic: invented paths, scenarios and shas that stand
for the shape a reviewer or qa agent writes, not a real review.
"""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import dump
from graph_control import cli
from graph_control.commands import iter_commands
from graph_control.common import Invalid
from graph_control.findings import Findings, counts

CLI = Path(__file__).resolve().parents[2] / "scripts" / "graph-control.py"
BASE, HEAD = "a" * 40, "b" * 40


def finding(**overrides):
    row = {"id": "F1", "severity": "blocking", "file": "src/orders/total.py", "line": 42,
           "scenario": "with qty 0 the total divides by zero and the endpoint returns 500",
           "rule": "review-protocol: Blocking, wrong behavior", "confidence": 0.9,
           "route": "patch", "needs_author_context": False, "status": "open"}
    return {**row, **overrides}


def document(verdict="CHANGES-REQUESTED", findings=None, **overrides):
    return {"schema_version": 1, "verdict": verdict, "reviewed": {"base": BASE, "head": HEAD},
            "findings": [finding()] if findings is None else findings, **overrides}


def invoke(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, json.loads(out.getvalue())


class Schema(unittest.TestCase):
    """AC-W2-FD-01"""

    def test_valid_fixture_parses(self):
        parsed = Findings.parse(document(findings=[
            finding(), finding(id="F2", severity="nit", confidence=0.5, route="defer", line=0)]))
        self.assertEqual((parsed.verdict, parsed.base, parsed.head), ("CHANGES-REQUESTED", BASE, HEAD))
        self.assertEqual([item.id for item in parsed.findings], ["F1", "F2"])

    def test_qa_fail_verdict_and_integer_confidence_parse(self):
        parsed = Findings.parse(document("FAIL", [finding(severity="important", confidence=1)]))
        self.assertEqual(parsed.verdict, "FAIL")

    def test_pass_allows_fixed_and_refuted_blockers_and_open_nits(self):
        parsed = Findings.parse(document("PASS", [
            finding(status="fixed"), finding(id="F2", severity="important", status="refuted"),
            finding(id="F3", severity="nit", route="defer")]))
        self.assertEqual(parsed.verdict, "PASS")

    def test_invalid_documents_raise(self):
        cases = {
            "unknown top-level key": document(extra=True),
            "unknown finding key": document(findings=[finding(category="sql")]),
            "missing finding key": document(findings=[{k: v for k, v in finding().items() if k != "route"}]),
            "duplicate id": document(findings=[finding(), finding(severity="important")]),
            "bad route": document(findings=[finding(route="rewrite")]),
            "blocking below 0.8": document(findings=[finding(confidence=0.5)]),
            "important below 0.8": document(findings=[finding(severity="important", confidence=0.79)]),
            "PASS with open blocking": document("PASS"),
            "PASS with open important": document("PASS", [finding(severity="important")]),
            "unknown verdict": document("LGTM"),
            "schema version 2": document(schema_version=2),
            "id not F<n>": document(findings=[finding(id="B1")]),
            "id F0": document(findings=[finding(id="F0")]),
            "confidence above 1": document(findings=[finding(confidence=1.5)]),
            "confidence boolean": document(findings=[finding(confidence=True)]),
            "negative line": document(findings=[finding(line=-1)]),
            "string line": document(findings=[finding(line="42")]),
            "bad severity": document(findings=[finding(severity="critical")]),
            "bad status": document(findings=[finding(status="wontfix")]),
            "author context not boolean": document(findings=[finding(needs_author_context="no")]),
            "empty scenario": document(findings=[finding(scenario=" ")]),
            "short sha": document(reviewed={"base": "abc1234", "head": HEAD}),
            "uppercase sha": document(reviewed={"base": BASE.upper(), "head": HEAD}),
            "reviewed extra key": document(reviewed={"base": BASE, "head": HEAD, "branch": "x"}),
            "nit routed to the fix loop": document(findings=[finding(severity="nit", route="patch")]),
            "findings not an array": document(findings={}),
        }
        for label, data in cases.items():
            with self.subTest(label), self.assertRaises(Invalid):
                Findings.parse(data)

    def test_error_names_the_offending_finding(self):
        with self.assertRaisesRegex(Invalid, r"findings\[1\].*0\.8"):
            Findings.parse(document(findings=[finding(), finding(id="F2", confidence=0.5)]))


class Counts(unittest.TestCase):
    """AC-W2-FD-02 and AC-W2-FD-03"""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.review = Path(dump(self.root / "findings.json", document(findings=[
            finding(), finding(id="F2", status="fixed"), finding(id="F3", severity="important"),
            finding(id="F4", severity="important", status="refuted"),
            finding(id="F5", severity="nit", route="defer")])))
        self.qa = Path(dump(self.root / "qa-findings.json", document("FAIL", [
            finding(severity="important", route="bad_plan"),
            finding(id="F2", severity="nit", route="defer", status="fixed")])))

    def test_counts_sum_open_findings_across_files(self):
        self.assertEqual(counts([self.review, self.qa]), {"blocking": 1, "important": 2, "nit": 1})

    def test_cli_counts_flag(self):
        code, out = invoke(["findings", str(self.review), str(self.qa), "--counts"])
        self.assertEqual((code, out), (0, {"blocking": 1, "important": 2, "nit": 1, "status": "PASS"}))

    def test_cli_without_counts_reports_verdict_and_open_routes_per_file(self):
        code, out = invoke(["findings", str(self.review), str(self.qa)])
        self.assertEqual(code, 0)
        self.assertEqual(out["files"], [
            {"path": str(self.review), "verdict": "CHANGES-REQUESTED",
             "open": {"blocking": 1, "important": 1, "nit": 1},
             "routes": {"defer": ["F5"], "patch": ["F1", "F3"]}},
            {"path": str(self.qa), "verdict": "FAIL", "open": {"blocking": 0, "important": 1, "nit": 0},
             "routes": {"bad_plan": ["F1"]}}])

    def test_same_file_twice_is_rejected_not_double_counted(self):
        (self.root / "sub").mkdir()
        with self.assertRaisesRegex(Invalid, "twice"):
            counts([self.review, self.root / "sub" / ".." / "findings.json"])

    def test_invalid_file_blocks_and_names_the_path(self):
        broken = Path(dump(self.root / "broken.json", document(findings=[finding(route="rewrite")])))
        code, out = invoke(["findings", str(self.review), str(broken), "--counts"])
        self.assertEqual((code, out["status"]), (1, "BLOCKED"))
        self.assertIn(str(broken), out["reason"])

    def test_missing_file_blocks_with_exit_1(self):
        missing = self.root / "qa-findings.r2.json"
        result = subprocess.run([sys.executable, str(CLI), "findings", str(self.review), str(missing), "--counts"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        out = json.loads(result.stdout)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertIn("absent findings file is not zero findings", out["reason"])
        self.assertIn(str(missing), out["reason"])

    def test_malformed_json_blocks(self):
        garbled = self.root / "garbled.json"
        garbled.write_text("{not json")
        code, out = invoke(["findings", str(garbled)])
        self.assertEqual((code, out["status"]), (1, "BLOCKED"))
        self.assertIn(str(garbled), out["reason"])


class Registry(unittest.TestCase):
    def test_plugin_package_ships_findings_command(self):
        self.assertIn("findings", [module.NAME for module in iter_commands()])


if __name__ == "__main__":
    unittest.main()
