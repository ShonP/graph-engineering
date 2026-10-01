"""Read-only health findings for a repo's graph-engineering setup and the executing plugin.

diagnose() reads the repo's .claude/graph-profile.yaml and .claude/graph-checks.json,
the plugin's own manifest and the host's installed-plugin record. It never runs a
configured command: the only process it starts is `git check-ignore`, and quick
mode (the cached SessionStart check) starts none.
"""

import importlib.util
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import Invalid, load
from .preflight import read_profile
from .risk import CONTROL, BadPattern, nested, parse_rows

LEVELS = ("error", "warn", "info")
TIERS = ("opus", "sonnet")
CLASS_KEYS = ("owner_classes", "auto_classes")
SKILL_KEYS = {"impl", "review", "qa", "design"}
SKILL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
UPGRADE = "run /graph-init --upgrade"


@dataclass(frozen=True)
class Finding:
    level: str  # error | warn | info
    id: str
    message: str
    fix: str


def diagnose(root: Path, plugin_root: Path, quick: bool) -> list[Finding]:
    """Every finding for `root`, errors first. quick=True runs only the checks that spawn nothing."""
    manifest = load(plugin_root / ".claude-plugin" / "plugin.json")
    findings: list[Finding] = []
    profile_path = root / ".claude" / "graph-profile.yaml"
    if not profile_path.is_file():
        findings.append(Finding("info", "no-profile", "this repo has no .claude/graph-profile.yaml",
                                "the owner runs /graph-init"))
    else:
        try:
            profile: dict[str, Any] | None = read_profile(profile_path)
        except (ValueError, OSError) as error:
            profile = None
            findings.append(Finding("error", "profile-invalid", f".claude/graph-profile.yaml cannot be read: {error}",
                                    "fix the YAML, or regenerate it with /graph-init --force"))
        if profile is not None:
            findings += _schema(profile) + _stale(profile)
            if not quick:
                findings += _runtime(profile) + _policy(profile) + _gates(profile)
                findings += _routing(profile, root, plugin_root, str(manifest.get("name", "")))
        findings += _checks(root, plugin_root, quick)
        if not quick:
            findings += _ignored(root)
    findings += _version(manifest)
    return sorted(findings, key=lambda finding: LEVELS.index(finding.level))


def _schema(profile: dict[str, Any]) -> list[Finding]:
    value = profile.get("schema_version")
    if type(value) is int and value >= 2:
        return []
    shown = "missing" if value is None else repr(value)
    return [Finding("warn", "schema-version", f"profile schema_version is {shown}; this plugin reads version 2",
                    UPGRADE)]


def _stale(profile: dict[str, Any]) -> list[Finding]:
    stale = ["content"] if "content" in profile else []
    gates = profile.get("gates")
    if isinstance(gates, dict) and "publication" in gates:
        stale.append("gates.publication")
    return [Finding("warn", "stale-key", f"profile key `{key}` was removed in 0.12 and is ignored",
                    f"delete `{key}`, or {UPGRADE}") for key in stale]


def _runtime(profile: dict[str, Any]) -> list[Finding]:
    if isinstance(profile.get("runtime"), dict):
        return []
    return [Finding("error", "runtime-missing", "profile has no `runtime` block, so preflight blocks every run",
                    f"add `runtime` (or `runtime.none` with the public-surface reason); {UPGRADE} fills it")]


def _policy(profile: dict[str, Any]) -> list[Finding]:
    policy = profile.get("policy")
    if not isinstance(policy, dict):
        return []
    findings = []
    roles = policy.get("roles")
    for role, model in (roles.items() if isinstance(roles, dict) else ()):
        if not (isinstance(model, str) and model in TIERS):
            findings.append(Finding("warn", "policy-model", f"policy.roles.{role} is {model!r}; tiers are opus or sonnet",
                                    f"set policy.roles.{role} to opus or sonnet"))
    never = policy.get("never")
    if isinstance(never, list) and "haiku" not in never:
        findings.append(Finding("warn", "policy-never", "policy.never does not list haiku",
                                "add haiku to policy.never"))
    return findings


def _risk(profile: dict[str, Any]) -> tuple[list[Finding], set[str] | None]:
    """The risk table read by the reader depth uses; None ids when its shape is wrong."""
    try:
        rows = parse_rows(profile.get("risk"))
    except BadPattern as error:
        return [Finding("error", "risk-keyword", str(error), "fix the regex after `re:`, or drop `re:` to match "
                        "the keyword literally")], None
    except Invalid as error:
        return [Finding("error", "risk-shape", str(error), "write `risk:` as a list of `- id: <name>` rows with "
                        "`paths` and `keywords`, as templates/graph-profile.yaml does")], None
    ids, slow = {row.id for row in rows}, nested(rows)  # slow is advisory: depth stops it at its time budget
    if not slow:
        return [], ids
    return [Finding("warn", "risk-nested", f"risk keywords nest quantifiers, so one line can backtrack for seconds: "
                    f"{', '.join(slow)}", "rewrite without the outer quantifier, e.g. (a+)+ as a+")], ids


def _gates(profile: dict[str, Any]) -> list[Finding]:
    findings, ids = _risk(profile)
    if ids is not None and CONTROL in ids:
        findings.append(Finding("error", "risk-reserved", f"the risk table defines `{CONTROL}`, a built-in reserved row",
                                f"delete that row; `{CONTROL}` always covers .claude/**, CLAUDE.md, AGENTS.md, "
                                ".mcp.json, .github/** and instructionPaths"))
    gates = profile.get("gates")
    if not isinstance(gates, dict):
        return findings
    for key in ("plan", "merge"):
        if gates.get(key, "owner") != "owner":
            findings.append(Finding("warn", "gates-value", f"gates.{key} is {gates[key]!r}; the only value is owner, "
                                    f"so the {key} gate still stops for the owner",
                                    f"set gates.{key}: owner; merges open on their own only through gates.auto_classes"))
    auto = gates.get("auto_classes")
    if CONTROL in (auto if isinstance(auto, list) else [auto]):
        findings.append(Finding("warn", "gates-control", f"gates.auto_classes lists `{CONTROL}`, which always waits "
                                "for the owner", f"remove `{CONTROL}` from gates.auto_classes"))
    known = (ids or set()) | {"none", CONTROL}
    for key in CLASS_KEYS:
        value = gates.get(key)
        if value is None or ids is None:  # a misshapen table is reported once, as risk-shape
            continue
        items = value if isinstance(value, list) else [value]
        unknown = [repr(item) for item in items if not (isinstance(item, str) and item in known)]
        if unknown:
            findings.append(Finding("error", "gates-risk",
                                    f"gates.{key} names risk ids the risk table does not define: {', '.join(unknown)}",
                                    "add a `risk` row with that id, or remove it (`none` is always valid)"))
    return findings


def _skill_names(node: Any) -> set[str]:
    """Names in every impl/review/qa/design list under `routing`, at any depth."""
    if isinstance(node, dict):
        names: set[str] = set()
        for key, value in node.items():
            if key in SKILL_KEYS and isinstance(value, list):
                names |= {item for item in value if isinstance(item, str)}
            else:
                names |= _skill_names(value)
        return names
    if isinstance(node, list):
        return set().union(*map(_skill_names, node)) if node else set()
    return set()


def _routing(profile: dict[str, Any], root: Path, plugin_root: Path, plugin: str) -> list[Finding]:
    missing, bare_names = [], []
    for name in sorted(_skill_names(profile.get("routing"))):
        prefix, _, bare = name.rpartition(":")
        if prefix and prefix != plugin:
            continue  # another plugin's skill: not resolvable from here
        valid = SKILL_NAME.fullmatch(bare) is not None
        in_plugin = valid and any(plugin_root.glob(f"skills/*/{bare}/SKILL.md"))
        if not (in_plugin or valid and (root / ".claude" / "skills" / bare / "SKILL.md").is_file()):
            missing.append(name)
        elif in_plugin and not prefix:
            bare_names.append(name)
    findings = [Finding("warn", "routing-skill",
                        f"routing names skills that resolve to no plugin or repo skill: {', '.join(missing)}",
                        "correct the names, or add .claude/skills/<name>/SKILL.md")] if missing else []
    if bare_names:  # a bare name can resolve to a host built-in; the skill receipt counts only the exact name
        findings.append(Finding("warn", "routing-bare", f"routing names plugin skills bare: {', '.join(bare_names)}",
                                "write them qualified: " + ", ".join(f"{plugin}:{name}" for name in bare_names)))
    return findings


def _checks(root: Path, plugin_root: Path, quick: bool) -> list[Finding]:
    path = root / ".claude" / "graph-checks.json"
    if not path.is_file():
        return [Finding("warn", "checks-missing",
                        ".claude/graph-checks.json is missing, so the Stop and lint hooks do nothing (opt-in since 0.15)",
                        "copy the plugin's templates/graph-checks.json to .claude/graph-checks.json and set this repo's commands")]
    if quick:
        return []
    spec = importlib.util.spec_from_file_location("ge_checks_config", plugin_root / "hooks" / "scripts" / "checks_config.py")
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.load(path)  # parses and validates; runs nothing
    except (ValueError, OSError) as error:
        return [Finding("error", "checks-invalid", f".claude/graph-checks.json is invalid: {error}",
                        "correct it against the plugin's templates/graph-checks.json")]
    return []


def _ignored(root: Path) -> list[Finding]:
    try:
        result = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".graph/x"],
                                capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 1:  # 0 ignored, 128 not a repository
        return []
    return [Finding("warn", "graph-not-ignored", ".graph/ (run state and ledgers) is not ignored by git",
                    "add .graph/ to .gitignore")]


def _version(manifest: dict[str, Any]) -> list[Finding]:
    name, running = manifest.get("name"), manifest.get("version")
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        plugins = json.loads((config / "plugins" / "installed_plugins.json").read_text()).get("plugins")
    except (OSError, ValueError, AttributeError):
        plugins = None
    records = [record for key, value in (plugins.items() if isinstance(plugins, dict) else ())
               if isinstance(key, str) and key.split("@", 1)[0] == name
               for record in (value if isinstance(value, list) else [value]) if isinstance(record, dict)]
    installed = sorted({record["version"] for record in records if isinstance(record.get("version"), str)})
    if not installed:
        return [Finding("info", "cannot-determine",
                        f"cannot determine the installed {name} version: installed_plugins.json has no record of it",
                        "none needed; restart the session after any plugin update")]
    if running in installed:
        return []
    return [Finding("warn", "version-mismatch",
                    f"this session runs {name} {running}, but {' or '.join(installed)} is installed",
                    "restart the session so it loads the installed version")]
