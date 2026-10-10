"""Where a skill name resolves: the plugin's skills/*/<name>/SKILL.md, else the repo's .claude/skills/<name>/SKILL.md.

Shared by doctor's routing check and validate-briefs. Reads only file existence.
"""

import re
from pathlib import Path

SKILL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def ships(bare: str, plugin_root: Path) -> bool:
    """True when the plugin holds skills/<group>/<bare>/SKILL.md for a valid skill name."""
    return SKILL_NAME.fullmatch(bare) is not None and any(plugin_root.glob(f"skills/*/{bare}/SKILL.md"))


def resolves(name: str, plugin_root: Path, repo_root: Path, plugin: str = "graph-engineering") -> bool | None:
    """True when `name`, bare or `<plugin>:`-qualified, resolves in the plugin or the repo; None for another plugin's name."""
    prefix, _, bare = name.rpartition(":")
    if prefix and prefix != plugin:
        return None
    if SKILL_NAME.fullmatch(bare) is None:
        return False
    return ships(bare, plugin_root) or (repo_root / ".claude" / "skills" / bare / "SKILL.md").is_file()
