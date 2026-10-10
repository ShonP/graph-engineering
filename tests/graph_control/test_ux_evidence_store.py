"""The optional UX evidence store: media captured locally, pushed to a store, never committed.

`uxEvidence.store` in the profile names a repo's own push, pull and link
commands. Empty keeps the default (the media is committed). These tests pin the
wording every role reads, so a repo that opts in is not told elsewhere to
commit the media or embed committed images, and the template default that
keeps every other repo on today's behaviour.
"""

import re
import unittest
from pathlib import Path

import yaml

import helpers  # noqa: F401  (puts scripts/ on sys.path)
from graph_control.preflight import UniqueLoader

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/process/ux-evidence/SKILL.md"
IMPLEMENTERS = [ROOT / "agents/implementer.md", ROOT / "agents/implementer-simple.md"]
REVIEW_PROTOCOL = ROOT / "skills/process/review-protocol/SKILL.md"
QA_VERIFICATION = ROOT / "skills/process/qa-verification/SKILL.md"
TEMPLATE = ROOT / "templates/graph-profile.yaml"
INIT = ROOT / "commands/graph-init.md"
DOCTOR = ROOT / "commands/graph-doctor.md"
README = ROOT / "README.md"
TOUCHED = [SKILL, *IMPLEMENTERS, REVIEW_PROTOCOL, QA_VERIFICATION, TEMPLATE, INIT, DOCTOR, README]
EM_DASH = chr(0x2014)


def flat(text):
    """Prose with its line wrapping removed, so a check does not depend on where a line breaks."""
    return " ".join(text.split())


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if match is None:
        raise AssertionError(f"no `## {heading}` section")
    return flat(match.group(1))


def bullet(text, label):
    """The one top-level bullet starting with `- **<label>**`, flattened."""
    match = re.search(rf"^- \*\*{re.escape(label)}\*\*.*?(?=^- |^\S|\Z)", text, re.M | re.S)
    if match is None:
        raise AssertionError(f"no `- **{label}**` bullet")
    return flat(match.group(0))


class Skill(unittest.TestCase):
    def setUp(self):
        self.where = section(SKILL.read_text(), "Where it lives")

    def test_store_keeps_media_out_of_git_and_commits_text_only(self):
        for phrase in ("When the profile sets `uxEvidence.store`",
                       "(png, jpg, jpeg, gif, webp, mp4, webm, mov) are **not committed**",
                       "run `<store.push> <folder>` and commit only README.md and the capture script",
                       "The repo-relative path is the storage key",
                       "Reviewers and qa read them with `<store.pull> <folder>`",
                       "`<store.link> <file>`, a short-lived URL that is never written into the PR body or any file"):
            self.assertIn(phrase, self.where)

    def test_empty_store_keeps_committing_the_media(self):
        self.assertIn("With no `uxEvidence.store` (the default), the media is committed in the folder", self.where)

    def test_pr_body_embeds_committed_images_only_when_media_is_committed(self):
        self.assertIn("embedding the committed images when the media is committed", self.where)
        self.assertIn("with `uxEvidence.store`, list each pair's repo-relative paths in the table", self.where)
        self.assertNotIn("embedding the committed images (they render inline on GitHub)", self.where)

    def test_large_recordings_go_to_the_store_when_one_is_set(self):
        self.assertIn("With `uxEvidence.store`, they are pushed like every other file", self.where)

    def test_reviewer_row_blocks_when_nothing_was_pushed(self):
        who = section(SKILL.read_text(), "Who does what")
        self.assertIn("no evidence folder (or, with `uxEvidence.store`, no pushed media under it: "
                      "`<store.pull>` returns nothing) = **Blocking**", who)
        self.assertIn("qa | runs `<store.pull> <folder>` first when the profile sets `uxEvidence.store`", who)


class Roles(unittest.TestCase):
    def test_implementers_push_to_the_store_and_commit_text_only(self):
        for path in IMPLEMENTERS:
            with self.subTest(path.name):
                line = bullet(path.read_text(), "UX evidence")
                self.assertIn("Committed under the profile's `uxEvidence.path` and embedded in the PR body; "
                              "when the profile sets `uxEvidence.store`, the media goes through its `push` command "
                              "instead and only the text is committed", line)
                self.assertIn("the PR body lists the repo-relative paths", line)

    def test_reviewer_lens_pulls_before_viewing(self):
        lens = bullet(REVIEW_PROTOCOL.read_text(), "UX evidence")
        self.assertIn("With `uxEvidence.store` set, run `<store.pull> <folder>` before looking", lens)
        self.assertIn("nothing to pull counts as missing", lens)

    def test_qa_pulls_before_viewing(self):
        text = flat(QA_VERIFICATION.read_text())
        self.assertIn("When the profile sets `uxEvidence.store`, run its `pull` command on the folder first", text)

    def test_readme_house_rule_names_the_store(self):
        rule = bullet(README.read_text(), "UX evidence.")
        self.assertIn("or, when the profile sets `uxEvidence.store`, pushed with its command and kept out of git",
                      rule)


class Template(unittest.TestCase):
    def setUp(self):
        self.profile = yaml.load(TEMPLATE.read_text(), Loader=UniqueLoader)

    def test_store_defaults_to_empty_commands(self):
        self.assertEqual(self.profile["uxEvidence"]["path"], "docs/ux/changes")
        self.assertEqual(self.profile["uxEvidence"]["store"], {"push": "", "pull": "", "link": ""})

    def test_template_comment_explains_the_opt_in(self):
        text = flat(re.sub(r"^\s*# ?", "", TEMPLATE.read_text(), flags=re.M))
        self.assertIn("Empty keeps the media committed", text)
        self.assertIn("the evidence folder or file is appended", text)


class Init(unittest.TestCase):
    def test_init_proposes_a_store_only_from_an_existing_command(self):
        text = flat(INIT.read_text())
        self.assertIn("Propose `uxEvidence.store` only when the repo already has an evidence store command", text)
        self.assertIn("Never invent one; without it the store stays empty and the media is committed", text)

    def test_init_proposes_the_media_ignore_lines_with_a_store(self):
        text = flat(INIT.read_text())
        self.assertIn("When `uxEvidence.store` is set, also propose ignoring the media under `uxEvidence.path`", text)

    def test_doctor_command_lists_the_store_check(self):
        self.assertIn("UX evidence store", DOCTOR.read_text().split("---\n")[1])


class Style(unittest.TestCase):
    def test_no_em_dashes_in_touched_files(self):
        for path in TOUCHED:
            with self.subTest(path.name):
                self.assertNotIn(EM_DASH, path.read_text())


if __name__ == "__main__":
    unittest.main()
