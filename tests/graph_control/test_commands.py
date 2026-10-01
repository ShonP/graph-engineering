"""Plug-in command registry: discovery contract and CLI dispatch rules."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from helpers import dump, plan_data
from graph_control import cli
from graph_control.commands import Output, iter_commands
from graph_control.common import Invalid

CLI = Path(__file__).resolve().parents[2] / "scripts" / "graph-control.py"
COMPLETE = ('NAME = "{name}"\nHELP = "fixture"\n\ndef add_arguments(parser):\n    pass\n\n'
            'def run(args):\n    return {{}}\n')


def fake(name, result=None, error=None):
    """A synthetic command module; `run` returns `result` or raises `error`."""
    def run(args):
        if error is not None:
            raise error
        return result
    return SimpleNamespace(NAME=name, HELP="fixture command",
                           add_arguments=lambda parser: parser.add_argument("--flag"), run=run)


def invoke(argv, modules):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv, modules=modules)
    return code, out.getvalue()


class Discovery(unittest.TestCase):
    def package(self, files):
        """Write a throwaway package on sys.path; a unique name defeats the module cache."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        name = "fixture_cmds_" + uuid.uuid4().hex[:8]
        root = Path(directory.name) / name
        root.mkdir()
        (root / "__init__.py").write_text("")
        for filename, body in files.items():
            (root / filename).write_text(body)
        sys.path.insert(0, directory.name)
        self.addCleanup(sys.path.remove, directory.name)
        return name

    def test_complete_module_is_discovered(self):
        name = self.package({"alpha.py": COMPLETE.format(name="alpha")})
        self.assertEqual([module.NAME for module in iter_commands(name)], ["alpha"])

    def test_module_missing_run_raises(self):
        body = COMPLETE.format(name="broken").split("def run")[0]
        name = self.package({"broken.py": body})
        with self.assertRaisesRegex(TypeError, r"broken.*run"):
            list(iter_commands(name))

    def test_private_helper_module_is_skipped(self):
        name = self.package({"alpha.py": COMPLETE.format(name="alpha"), "_shared.py": "VALUE = 1\n"})
        self.assertEqual([module.NAME for module in iter_commands(name)], ["alpha"])

    def test_plugin_package_ships_guard_agent(self):
        self.assertIn("guard-agent", [module.NAME for module in iter_commands()])


class Registration(unittest.TestCase):
    def test_name_colliding_with_builtin_subcommand_raises(self):
        with self.assertRaisesRegex(ValueError, "verify"):
            cli.parser([fake("verify", {})])

    def test_duplicate_plugin_names_raise(self):
        with self.assertRaisesRegex(ValueError, "twin"):
            cli.parser([fake("twin", {}), fake("twin", {})])


class Dispatch(unittest.TestCase):
    def test_dict_result_prints_pass_json(self):
        code, out = invoke(["demo", "--flag", "x"], [fake("demo", {"b": 2, "a": 1})])
        self.assertEqual((code, out), (0, '{"a": 1, "b": 2, "status": "PASS"}\n'))

    def test_output_result_is_printed_verbatim_with_its_exit_code(self):
        code, out = invoke(["demo"], [fake("demo", Output("raw text", 3))])
        self.assertEqual((code, out), (3, "raw text"))

    def test_known_errors_print_blocked_json(self):
        for error in (Invalid("bad artifact"), ValueError("bad value"), OSError("no disk")):
            with self.subTest(error=type(error).__name__):
                code, out = invoke(["demo"], [fake("demo", error=error)])
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(out), {"status": "BLOCKED", "reason": str(error)})

    def test_builtin_subcommand_output_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = dump(Path(directory) / "plan.json", plan_data())
            result = subprocess.run([sys.executable, str(CLI), "validate-plan", plan], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, '{"cases": 1, "status": "PASS", "tasks": 1}\n'))


class Help(unittest.TestCase):
    """argparse %-formats every help string, so a bare % in a HELP or argument help crashes --help."""

    def test_top_level_help_lists_every_command_module(self):
        text = cli.parser().format_help()
        for module in iter_commands():
            with self.subTest(command=module.NAME):
                self.assertIn(module.NAME, text)

    def test_every_subcommand_help_renders(self):
        commands = next(action for action in cli.parser()._actions if action.choices)
        for name, sub in commands.choices.items():
            with self.subTest(command=name):
                self.assertIn("usage:", sub.format_help())

    def test_entry_point_help_exits_zero(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                result = subprocess.run([sys.executable, str(CLI), flag], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("validate-briefs", result.stdout)


if __name__ == "__main__":
    unittest.main()
