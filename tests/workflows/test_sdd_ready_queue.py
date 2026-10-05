"""The plugin's SDD ready-queue workflow keeps the host's script rules (AC-WF-1).

Static checks only: node is not a repo dependency, so the dry run itself is qa's
(AC-WF-2). These pin what the host would reject at load or resume time (a meta
that is not a pure literal, Date.now, Math.random, argless new Date, import()),
what the run engine forbids (isolation: 'worktree' branches from the default
branch), the 4-writer cap, every implementer status, per-task worktree removal,
and a dry run that can reach no agent() call. Stdlib only.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workflows/sdd-ready-queue.js"
DOC = ROOT / "docs/sdd-workflows.md"
STATUSES = ("DONE", "DONE_WITH_CONCERNS", "PARTIAL", "BLOCKED", "NEEDS_CONTEXT", "NEEDS_SETUP", "ESCALATE")
STRING = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`(?:[^`\\]|\\.)*`")


def block(text, start):
    """The source from the first `{` at or after start through its matching `}`, strings skipped."""
    open_at = text.index("{", start)
    depth, i = 0, open_at
    while i < len(text):
        match = STRING.match(text, i)
        if match:
            i = match.end()
            continue
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[open_at:i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces after offset {start}")


def functions(text):
    """Top-level `function name(` bodies by name."""
    return {m.group(1): block(text, m.end()) for m in re.finditer(r"^(?:async )?function (\w+)\(", text, re.M)}


def reachable(bodies, root):
    """Names of top-level functions root can call, root included."""
    seen, todo = set(), [root]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        todo.extend(n for n in bodies if n not in seen and re.search(rf"\b{n}\(", bodies[name]))
    return seen


class SddReadyQueue(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text(encoding="utf-8")
        self.code = STRING.sub("''", self.text)

    def test_meta_is_the_first_statement_and_a_pure_literal(self):
        self.assertTrue(self.text.startswith("export const meta = {"), "meta is not the first statement")
        meta = block(self.text, 0)
        bare = STRING.sub("''", meta)
        for forbidden in ("(", "...", "${", "`"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, bare, "meta is not a pure literal")
        for key in ("name: 'sdd-ready-queue'", "description:", "whenToUse:", "phases:"):
            with self.subTest(key=key):
                self.assertIn(key, meta)

    def test_no_call_the_host_forbids(self):
        for pattern in (r"Date\.now\(", r"Math\.random\(", r"new Date\(\s*\)", r"\bimport\(", r"\brequire\("):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.code))

    def test_no_host_worktree_isolation(self):
        self.assertNotIn("isolation", self.code)

    def test_no_barrier_and_a_race_loop(self):
        self.assertNotIn("parallel(", self.code)
        self.assertIn("Promise.race(", self.code)

    def test_writers_capped_at_four_and_default_four(self):
        self.assertRegex(self.code, r"MAX_WRITERS = 4\b")
        self.assertRegex(self.code, r"Math\.min\(MAX_WRITERS, Math\.max\(1,")

    def test_every_implementer_status_is_handled(self):
        for status in STATUSES:
            with self.subTest(status=status):
                self.assertRegex(self.text, rf"'{status}'")

    def test_agent_types_are_the_roster(self):
        for agent_type in ("graph-engineering:implementer", "graph-engineering:implementer-simple",
                           "graph-engineering:reviewer"):
            with self.subTest(agent_type=agent_type):
                self.assertIn(f"'{agent_type}'", self.text)
        self.assertNotIn("general-purpose", self.text)

    def test_worktree_from_run_branch_head_and_ancestry_check(self):
        for needle in ("git worktree add -b", "git merge-base --is-ancestor", "git merge --no-ff"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_merge_removes_only_its_own_worktree(self):
        # worktree-gc's prefix mode removes any clean worktree whose HEAD is behind the run branch,
        # which is a sibling an implementer has just cut and not yet written to.
        self.assertIn("git worktree remove ${worktree}", self.text)
        self.assertIn("git branch -d ${branch}", self.text)
        self.assertNotIn("--force", self.text)
        self.assertNotIn("worktree-gc.sh --apply", self.text)

    def test_dry_run_reaches_no_agent_call(self):
        bodies = functions(self.text)
        self.assertIn("simulate", bodies, "no simulate() for the dry run")
        for name in reachable(bodies, "simulate"):
            with self.subTest(function=name):
                self.assertNotIn("agent(", STRING.sub("''", bodies[name]))
        self.assertRegex(self.code, r"if \(input\.dry_run\) return simulate\(")

    def test_live_and_dry_share_one_ready_rule(self):
        bodies = functions(self.text)
        self.assertIn("readySet", bodies)
        self.assertIn("readySet", reachable(bodies, "simulate"))
        self.assertIn("readySet(", bodies.get("schedule", ""))

    def test_doc_covers_invocation_and_the_why(self):
        doc = " ".join(DOC.read_text(encoding="utf-8").split())
        for needle in ("/graph-ship", "/graph-engineering:sdd-ready-queue",
                       "Workflow(graph-engineering:sdd-ready-queue)", "dry_run", "max_writers",
                       "Finding 3", "2026-10-05-run-throughput-analysis.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
