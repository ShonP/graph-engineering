"""graph_control.status: zero-token status line and full status over SYNTHETIC session fixtures.

The fixtures under fixtures/sessions/ are synthetic (see its README): invented
values shaped like the witnessed transcript and meta.json keys.
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control import cli, status
from graph_control.commands import status as status_command

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sessions"
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SENTINELS = ("SENTINEL-PROMPT-7f3a", "SENTINEL-RESPONSE-9c1e")
EXPECTED_LINE = "ge 0192f3ab: 3 live · reviewer(opus) 12m! implementer(opus) 2m qa(sonnet) 0m · out 48k"
SESSION = "synthetic-session/subagents"


def slug(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


class Workspace:
    """A temp repo, config dir and TMPDIR holding a copy of the synthetic fixture with applied ages."""

    def __init__(self, tmp: str, extra_agents: int = 0):
        base = Path(tmp).resolve()
        self.repo = base / "repo"
        shutil.copytree(FIXTURE / "repo" / "graph", self.repo / ".graph")
        self.config = base / "claude"
        self.project = self.config / "projects" / slug(self.repo)
        shutil.copytree(FIXTURE / "project", self.project)
        self.cache = base / "cache"
        self.cache.mkdir()
        ages = json.loads((FIXTURE / "ages.json").read_text())
        source = self.project / SESSION / "agent-asyn0001"
        for index in range(extra_agents):
            for suffix in (".jsonl", ".meta.json"):
                shutil.copy(source.with_suffix(suffix), self.project / SESSION / f"agent-aperf{index:03d}{suffix}")
            ages[f"{SESSION}/agent-aperf{index:03d}.jsonl"] = index % 15
        self.ages = ages
        self.touch()
        self.env = {"CLAUDE_CONFIG_DIR": str(self.config), "TMPDIR": str(self.cache)}

    def touch(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        for relative, minutes in self.ages.items():
            stamp = now - minutes * 60
            os.utime(self.project / relative, (stamp, stamp))

    def run(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        """Stdin is what a status line gets from the host; empty by default, never the runner's own."""
        env = {**os.environ, **self.env, "PYTHONPATH": str(SCRIPTS)}
        return subprocess.run([sys.executable, "-m", "graph_control.status", *args], input=stdin,
                              cwd=self.repo, env=env, capture_output=True, text=True, check=False)

    def newer_session(self) -> Path:
        """A second session started later in the same checkout: the newest transcript, no agents."""
        newer = self.project / "newer-session.jsonl"
        newer.write_text(json.dumps({"type": "user", "timestamp": "2026-09-30T12:00:00Z"}) + "\n")
        stamp = time.time() + 60
        os.utime(newer, (stamp, stamp))
        return newer


class StatusLineTests(unittest.TestCase):
    def test_line_lists_live_agents_with_idle_marker(self):  # AC-W2-ST-01
        with tempfile.TemporaryDirectory() as tmp:
            result = Workspace(tmp).run("--line")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, EXPECTED_LINE + "\n")
        self.assertLessEqual(len(EXPECTED_LINE), 120)
        self.assertIn("reviewer(opus) 12m!", result.stdout)
        self.assertEqual(result.stdout.count("!"), 1)

    def test_nothing_live_prints_empty_line(self):  # AC-W2-ST-02
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            for relative in list(space.ages):
                if relative.startswith("synthetic-session/"):
                    space.ages[relative] = 20
            space.touch()
            result = space.run("--line")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_missing_session_dir_prints_empty_line(self):  # AC-W2-ST-02
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            shutil.rmtree(space.config)
            line = space.run("--line")
            full = space.run()
        self.assertEqual((line.returncode, line.stdout, line.stderr), (0, "", ""))
        self.assertEqual(full.returncode, 0)
        self.assertIn("NEEDS YOU", full.stdout)

    def test_long_line_is_capped_with_hidden_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Workspace(tmp, extra_agents=27).run("--line")
        line = result.stdout.rstrip("\n")
        self.assertLessEqual(len(line), 120)
        self.assertRegex(line, r"^ge 0192f3ab: 30 live · implementer\(opus\) 14m!.* \+\d+ · out 372k$")


class FullStatusTests(unittest.TestCase):
    def test_sections_needs_you_and_cost_per_type(self):  # AC-W2-ST-03
        with tempfile.TemporaryDirectory() as tmp:
            result = Workspace(tmp).run()
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertLessEqual(len(lines), 40)
        for title in ("RUNNING (3)", "NEEDS YOU (2)", "COST"):
            self.assertIn(title, lines)
        self.assertIn("  0192f3ab: Merge now or wait for qa? Default: wait, reversible", lines)
        self.assertIn("  0192f3ab: Keep the old flag one more release? Default: yes", lines)
        self.assertNotIn("Review on opus", result.stdout)
        self.assertRegex(result.stdout, r"\n  0192f3ab:review +reviewer\(opus\) +12m!\n")
        cost = {line.split()[0]: line.split()[1:] for line in lines[lines.index("COST") + 2:]}
        self.assertEqual(cost["main"], ["2", "18k", "20k", "21k"])
        self.assertEqual(cost["graph-engineering:implementer"], ["3", "13k", "30k", "66k"])
        self.assertEqual(cost["graph-engineering:qa"], ["0", "0", "0", "0"])
        self.assertEqual(cost["graph-engineering:implementer-simple"], ["1", "4k", "0", "20k"])
        self.assertNotIn("99999", result.stdout)  # the decoy session is never read

    def test_full_status_is_capped_at_40_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Workspace(tmp, extra_agents=27).run()
        self.assertLessEqual(len(result.stdout.splitlines()), 40)
        self.assertIn("more", result.stdout)

    def test_command_module_returns_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            out = io.StringIO()
            with mock.patch.dict(os.environ, space.env), mock.patch.object(sys, "stdin", io.StringIO("")), \
                    contextlib.redirect_stdout(out):
                code = cli.main(["status", "--line", "--root", str(space.repo)], modules=[status_command])
        self.assertEqual((code, out.getvalue()), (0, EXPECTED_LINE + "\n"))


class SessionSelectionTests(unittest.TestCase):
    """Two sessions in one checkout: each status line reads its own, never whichever wrote last."""

    def test_without_a_hint_the_newest_session_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            space.newer_session()
            result = space.run("--line")
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_session_flag_reads_that_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            space.newer_session()
            result = space.run("--line", "--session", "synthetic-session")
        self.assertEqual((result.returncode, result.stdout), (0, EXPECTED_LINE + "\n"), result.stderr)

    def test_status_line_stdin_names_the_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            space.newer_session()
            transcript = str(space.project / "synthetic-session.jsonl")
            by_path = space.run("--line", stdin=json.dumps({"session_id": "newer-session", "transcript_path": transcript,
                                                            "model": {"display_name": "Opus"}}))
            by_id = space.run("--line", stdin=json.dumps({"session_id": "synthetic-session", "cwd": str(space.repo)}))
        self.assertEqual(by_path.stdout, EXPECTED_LINE + "\n", by_path.stderr)
        self.assertEqual(by_id.stdout, EXPECTED_LINE + "\n", by_id.stderr)

    def test_a_named_session_that_is_missing_never_falls_back_to_the_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            bare = space.run("--line")
            flag = space.run("--line", "--session", "no-such-session")
            outside = space.run("--line", stdin=json.dumps({"transcript_path": str(Path(tmp) / "elsewhere.jsonl")}))
            junk = space.run("--line", stdin="not json")
        self.assertEqual(bare.stdout, EXPECTED_LINE + "\n")
        self.assertEqual([flag.stdout, outside.stdout], ["", ""])
        self.assertEqual((junk.returncode, junk.stdout), (0, EXPECTED_LINE + "\n"), "unreadable stdin is no hint")

    def test_a_session_id_that_is_a_path_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            flag = space.run("--line", "--session", "../synthetic-session")
            hint = space.run("--line", stdin=json.dumps({"session_id": "../../synthetic-session"}))
        self.assertEqual(flag.returncode, 2)
        self.assertEqual((hint.returncode, hint.stdout), (0, ""))

    def test_command_module_reads_the_session_flag_and_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            space.newer_session()
            outputs = []
            for argv, stdin in ((["--session", "synthetic-session"], ""),
                                ([], json.dumps({"session_id": "synthetic-session"}))):
                out = io.StringIO()
                with mock.patch.dict(os.environ, space.env), mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
                        contextlib.redirect_stdout(out):
                    code = cli.main(["status", "--line", "--root", str(space.repo), *argv], modules=[status_command])
                outputs.append((code, out.getvalue()))
        self.assertEqual(outputs, [(0, EXPECTED_LINE + "\n")] * 2)


class PrivacyAndCacheTests(unittest.TestCase):
    def test_sentinels_never_reach_output_or_cache(self):  # AC-W2-ST-04
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            outputs = [space.run("--line").stdout, space.run().stdout]
            outputs += [path.read_text() for path in space.cache.iterdir()]
        self.assertEqual(len(outputs), 3, "one cache file per session")
        for text in outputs:
            for sentinel in SENTINELS:
                self.assertNotIn(sentinel, text)

    def test_line_speed_and_cache_hit(self):  # AC-W2-ST-05
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp, extra_agents=27)
            started = time.perf_counter()
            first = space.run("--line")
            cold = time.perf_counter() - started
            shutil.rmtree(space.project / SESSION)
            started = time.perf_counter()
            second = space.run("--line")
            warm = time.perf_counter() - started
        print(f"\nstatus --line, 30-agent fixture: cold {cold * 1000:.0f} ms, cached {warm * 1000:.0f} ms "
              "(wall time incl. interpreter start)", file=sys.stderr)
        self.assertLess(cold, 1.0)
        self.assertEqual(second.stdout, first.stdout, "a call within 5 s reuses the cached result")
        self.assertIn("30 live", first.stdout)

    def test_cache_expires_and_reads_only_appended_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            transcript = space.project / SESSION / "agent-asyn0002.jsonl"
            duplicate = json.loads(transcript.read_text().splitlines()[1])
            final = json.loads(json.dumps(duplicate))
            final["message"].update(id="msg_synthetic_a2r2", stop_reason="end_turn",
                                    content=[{"type": "text", "text": SENTINELS[1]}])
            final["message"]["usage"].update(output_tokens=500, cache_read_input_tokens=40000,
                                             cache_creation_input_tokens=0)
            row = json.dumps(final) + "\n"
            now = time.time()
            with mock.patch.dict(os.environ, space.env):
                first = status.snapshot(space.repo, now)
                scanned = space.project / SESSION / "agent-asyn0001.jsonl"
                lines = scanned.read_text().splitlines(keepends=True)
                lines[1] = " " * (len(lines[1]) - 1) + "\n"  # same size: proves it is not re-read
                scanned.write_text("".join(lines))
                with transcript.open("a") as handle:
                    handle.write(json.dumps(duplicate) + "\n" + row[:40])  # a repeat, then a row mid-write
                space.touch(now)
                cached = status.snapshot(space.repo, now + 4)
                partial = status.snapshot(space.repo, now + 6)
                with transcript.open("a") as handle:
                    handle.write(row[40:])
                space.touch(now)
                done = status.snapshot(space.repo, now + 12)
        self.assertEqual(cached, first)
        self.assertEqual(first["cost"]["graph-engineering:reviewer"], [1, 8000, 0, 40000])
        self.assertEqual(partial["cost"]["graph-engineering:reviewer"], [1, 8000, 0, 40000])
        self.assertEqual(len(partial["live"]), 3)
        self.assertEqual(partial["cost"]["graph-engineering:implementer"], [3, 13200, 30000, 65700])
        self.assertEqual(done["cost"]["graph-engineering:reviewer"], [2, 8500, 40000, 40000])
        self.assertEqual([agent["type"] for agent in done["live"]], ["implementer", "qa"])

    def test_cache_owned_by_another_user_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            now = time.time()
            with mock.patch.dict(os.environ, space.env):
                first = status.snapshot(space.repo, now)
                shutil.rmtree(space.project / SESSION)
                with mock.patch.object(status.os, "getuid", create=True, return_value=os.getuid() + 1):
                    second = status.snapshot(space.repo, now + 1)
        self.assertEqual(len(first["live"]), 3)
        self.assertEqual(second["live"], [])

    def test_agent_stopped_by_user_is_not_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            space = Workspace(tmp)
            meta = space.project / SESSION / "agent-asyn0003.meta.json"
            meta.write_text(json.dumps({**json.loads(meta.read_text()), "stoppedByUser": True}))
            result = space.run("--line")
        self.assertEqual(result.stdout, "ge 0192f3ab: 2 live · reviewer(opus) 12m! implementer(opus) 2m · out 48k\n")


if __name__ == "__main__":
    unittest.main()
