"""Tree-keyed check memo: key identity, storage bounds and the stdlib-only import chain."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from graph_control import memo  # noqa: E402
from graph_control.common import Invalid  # noqa: E402
from graph_control.identity import snapshot  # noqa: E402
from graph_control.state import write  # noqa: E402

GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
ARGV = ["make", "check"]
CONFIG = hashlib.sha256(b'{"version": 1}').hexdigest()


def git(root, *args):
    env = {key: value for key, value in os.environ.items() if key not in GIT_VARS}
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env)


def repo(base):
    root = Path(base).resolve() / "repo"
    root.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "test@example.invalid"],
                 ["config", "user.name", "Test"], ["config", "commit.gpgsign", "false"]):
        git(root, *args)
    (root / "tracked.txt").write_text("baseline\n")
    (root / ".gitignore").write_text("ignored/\n")
    git(root, "add", ".")
    git(root, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "baseline")
    return root


def row(status="fail", code=1, at="2026-09-30T12:00:00+00:00", tail="1 failed"):
    return {"status": status, "exit_code": code, "observed_at": at, "tail": tail, "argv": ARGV}


class MemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = repo(self.temp.name)

    def key(self, argv=ARGV, config=CONFIG):
        return memo.memo_key(self.root, argv, config)

    def test_path_lives_in_the_git_common_dir_shared_by_worktrees(self):
        path = memo.memo_path(self.root)
        self.assertEqual(path, self.root / ".git" / "graph-engineering" / "checks-state.json")
        linked = self.root.parent / "linked"
        git(self.root, "worktree", "add", "-qb", "linked", str(linked))
        self.assertEqual(memo.memo_path(linked), path)
        self.assertNotEqual(memo.memo_key(linked, ARGV, CONFIG), self.key())

    def test_same_tree_argv_and_config_give_the_same_key(self):
        first = self.key()
        self.assertEqual(self.key(), first)
        self.assertRegex(first, r"^[0-9a-f]{64}$")

    def test_tracked_untracked_config_and_argv_changes_each_change_the_key(self):  # AC-W2-MM-02
        seen = {self.key()}
        (self.root / "tracked.txt").write_text("edited\n")
        seen.add(self.key())
        (self.root / "new.txt").write_text("untracked\n")
        seen.add(self.key())
        seen.add(self.key(config=hashlib.sha256(b"other").hexdigest()))
        seen.add(self.key(argv=["make", "test"]))
        self.assertEqual(len(seen), 5)

    def test_ignored_files_do_not_change_the_key(self):
        before = self.key()
        (self.root / "ignored").mkdir()
        (self.root / "ignored/build.log").write_text("noise\n")
        self.assertEqual(self.key(), before)

    def test_store_then_lookup_round_trips_and_a_miss_is_none(self):
        key = self.key()
        self.assertIsNone(memo.lookup(self.root, key))
        memo.store(self.root, key, row())
        self.assertEqual(memo.lookup(self.root, key), row())
        self.assertIsNone(memo.lookup(self.root, self.key(argv=["other"])))

    def test_storing_does_not_change_the_snapshot(self):  # AC-W2-MM-05
        (self.root / "dirty.txt").write_text("untracked\n")
        before, status = snapshot(self.root, "candidate"), git(self.root, "status", "--porcelain").stdout
        memo.store(self.root, self.key(), row())
        self.assertEqual(snapshot(self.root, "candidate"), before)
        self.assertEqual(git(self.root, "status", "--porcelain").stdout, status)

    def test_verdict_stamps_a_utc_time_and_bounds_the_tail(self):
        value = memo.verdict("pass", 0, "x" * 5000, ("make", "check"))
        self.assertEqual(len(value["tail"]), memo.MAX_TAIL)
        self.assertEqual(value["argv"], ARGV)
        self.assertTrue(value["observed_at"].endswith("+00:00"), value["observed_at"])
        self.assertEqual(memo.verdict("timeout", None, "", ARGV)["exit_code"], None)

    def test_store_rejects_an_inconsistent_verdict(self):
        for bad in (row(status="skipped"), row(status="pass", code=1), row(status="fail", code=0),
                    row(status="timeout", code=0), row(tail="x" * 4001), row(at="2026-09-30T12:00:00"),
                    {**row(), "argv": []}, {**row(), "extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                memo.store(self.root, self.key(), bad)
        self.assertFalse(memo.memo_path(self.root).exists())

    def test_cap_keeps_the_newest_entries(self):
        path = memo.memo_path(self.root)
        path.parent.mkdir(parents=True)
        entries = {f"{n:064x}": row(at=f"2026-09-{1 + n // 24:02d}T{n % 24:02d}:00:00+00:00") for n in range(200)}
        write(path, {"schema_version": 1, "entries": entries})
        memo.store(self.root, "a" * 64, row(at="2026-09-30T00:00:00+00:00"))
        kept = json.loads(path.read_text())["entries"]
        self.assertEqual(len(kept), memo.MAX_ENTRIES)
        self.assertNotIn(f"{0:064x}", kept)
        self.assertIn("a" * 64, kept)
        memo.store(self.root, "b" * 64, row(at="2026-08-01T00:00:00+00:00"))
        self.assertIsNone(memo.lookup(self.root, "b" * 64))

    def test_corrupt_or_foreign_memo_is_a_miss_and_is_replaced(self):
        path, key = memo.memo_path(self.root), self.key()
        path.parent.mkdir(parents=True)
        for text in ("{", '{"schema_version": 2, "entries": {}}', '[]'):
            with self.subTest(text=text):
                path.write_text(text)
                self.assertIsNone(memo.lookup(self.root, key))
        memo.store(self.root, key, row())
        self.assertEqual(memo.lookup(self.root, key), row())

    def test_an_invalid_entry_never_replays(self):
        path, key = memo.memo_path(self.root), self.key()
        path.parent.mkdir(parents=True)
        write(path, {"schema_version": 1, "entries": {key: row(status="pass", code=1)}})
        self.assertIsNone(memo.lookup(self.root, key))

    def test_a_non_git_root_has_no_memo(self):  # AC-W2-MM-04, unit side
        plain = Path(self.temp.name) / "plain"
        plain.mkdir()
        with self.assertRaises(Invalid):
            memo.memo_key(plain, ARGV, CONFIG)
        with self.assertRaises(Invalid):
            memo.memo_path(plain)


class ImportChain(unittest.TestCase):  # AC-W2-MM-06, import side
    PROBE = ("import sys; sys.modules['yaml'] = None\n"
             "import graph_control.{module}\n"
             "roots = {{name.split('.')[0] for name, loaded in sys.modules.items() if loaded is not None}}\n"
             "print(sorted(roots - set(sys.stdlib_module_names) - {{'graph_control', '__main__'}}))\n")

    def probe(self, module):
        env = dict(os.environ, PYTHONPATH=str(SCRIPTS))
        return subprocess.run([sys.executable, "-S", "-c", self.PROBE.format(module=module)],
                              capture_output=True, text=True, env=env)

    def test_memo_imports_without_site_packages_or_pyyaml(self):
        result = self.probe("memo")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "[]"), result.stderr)

    def test_the_probe_catches_a_pyyaml_import(self):
        self.assertNotEqual(self.probe("preflight").returncode, 0)


if __name__ == "__main__":
    unittest.main()
