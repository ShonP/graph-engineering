import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACEHOLDER = "__CI_GATE__.sh"
HOOKS_PATH = ".githooks"
HOOK_SETUPS = (".husky", ".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml", ".lefthook.yml")
REPO_PATH = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]*(?:/[A-Za-z0-9._-]+)*")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True).stdout.strip()


def gate_error(root: Path, gate: str) -> str | None:
    if not REPO_PATH.fullmatch(gate) or ".." in gate.split("/"):
        return f"ci.gate `{gate}` is not a repo-relative path of letters, digits, `._-/`"
    if not (root / gate).is_file():
        return f"ci.gate `{gate}` does not exist; the scaffold never writes the gate script"
    return None


def hook_setups(root: Path) -> list[str]:
    found = [rel for rel in HOOK_SETUPS if (root / rel).exists()]
    current = _git(root, "config", "--get", "core.hooksPath")
    if current and current.rstrip("/") != HOOKS_PATH:
        found.append(f"core.hooksPath={current}")
    hooks = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "hooks"
    if hooks.is_dir():
        found += [f".git/hooks/{path.name}" for path in sorted(hooks.iterdir())
                  if path.is_file() and not path.name.endswith(".sample")]
    return found


def scaffold(root: Path, gate: str, write: bool) -> list[str]:
    lines = []
    for entry in json.loads((HERE / "manifest.json").read_text())["files"]:
        text = (HERE / entry["source"]).read_text().replace(PLACEHOLDER, gate)
        target = root / entry["target"]
        if target.exists():
            same = target.read_text(errors="replace") == text
            lines.append(f"unchanged {entry['target']}" if same else
                         f"kept {entry['target']}: it differs from the rendered template; merge by hand")
        elif write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
            target.chmod(int(entry["mode"], 8))
            lines.append(f"wrote {entry['target']}")
        else:
            lines.append(f"would write {entry['target']}")
    setups = hook_setups(root)
    if setups:
        lines.append(f"hooks: found {', '.join(setups)}; core.hooksPath not set, so they keep running; "
                     f"call `{HOOKS_PATH}/pre-push \"$@\"` from the existing pre-push hook to chain the gate")
    elif write:
        _git(root, "config", "core.hooksPath", HOOKS_PATH)
        lines.append(f"hooks: core.hooksPath={HOOKS_PATH}")
    else:
        lines.append(f"hooks: would set core.hooksPath={HOOKS_PATH}")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render the CI run-once scaffold with the profile's ci.gate.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    error = gate_error(root, args.gate)
    if error:
        print(f"scaffold: {error}", file=sys.stderr)
        return 2
    print("\n".join(scaffold(root, args.gate, args.write)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
