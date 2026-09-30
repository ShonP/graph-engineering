"""Zero-token status: live subagents, open decisions and token cost of one Claude Code session.

    PYTHONPATH=<plugin>/scripts python3 -m graph_control.status [--line] [--root DIR]

Stdlib only (no uv start). Session: the newest `*.jsonl` in `<config>/projects/<slug of root>/`,
config $CLAUDE_CONFIG_DIR or ~/.claude, root --root or the cwd; keys and the live rule follow the
witness in tests/graph_control/fixtures/sessions/README.md. Never writes transcripts, never prints
prompt or response text. The view is cached 5 s in $TMPDIR with per-file byte offsets, so a
refresh parses only the rows appended since the last one.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

LIVE, STALLED, TTL = 15 * 60, 10 * 60, 5.0
LINE_MAX, LINES_MAX, VERSION = 120, 40, "v1"
RUN = re.compile(r"([0-9A-Za-z]{8}):(\S+)")
FAMILY = re.compile(r"claude-([a-z]+)")
USAGE = ("output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def session_of(root: Path) -> Path | None:
    """`<project>/<session id>` of the newest top-level transcript; a dir only once agents exist."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    project = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root))
    try:
        mains = [(entry.stat().st_mtime, entry.path) for entry in os.scandir(project)
                 if entry.name.endswith(".jsonl") and entry.is_file()]
    except OSError:
        return None
    return Path(max(mains)[1]).with_suffix("") if mains else None


def scan(path: Path, size: int, entry: dict | None) -> dict:
    """Fold the complete rows appended after `entry["offset"]` into the entry's totals."""
    if entry is None or size < entry["offset"]:
        entry = {"offset": 0, "requests": 0, "tokens": [0, 0, 0], "id": None, "last": [0, 0, 0],
                 "model": None, "final": False}
    if size > entry["offset"]:
        with path.open("rb") as stream:
            stream.seek(entry["offset"])
            data = stream.read(size - entry["offset"])
        complete = data.rfind(b"\n") + 1  # a row still being written waits for the next refresh
        entry["offset"] += complete
        for raw in data[:complete].splitlines():
            if b'"assistant"' in raw:
                _fold(entry, raw)
    return entry


def _fold(entry: dict, raw: bytes) -> None:
    """One assistant row. A message streamed over consecutive rows (same id) counts once, at its max."""
    try:
        row = json.loads(raw)
        message = row["message"]
        usage = message.get("usage") or {}
        counts = [max(int(usage.get(key) or 0), 0) for key in USAGE]
        key, model, content = message.get("id"), message.get("model"), message.get("content")
    except (ValueError, KeyError, TypeError, AttributeError):
        return
    if row.get("type") != "assistant" or model == "<synthetic>":
        return
    if key is not None and key == entry["id"]:
        entry["tokens"] = [total + max(new - old, 0) for total, new, old in zip(entry["tokens"], counts, entry["last"])]
        entry["last"] = [max(new, old) for new, old in zip(counts, entry["last"])]
    else:
        entry["requests"] += 1
        entry["tokens"] = [total + new for total, new in zip(entry["tokens"], counts)]
        entry["id"], entry["last"] = key, counts
    entry["model"] = model if isinstance(model, str) else entry["model"]
    tools = [block.get("name") for block in content if isinstance(block, dict)] if isinstance(content, list) else []
    entry["final"] = message.get("stop_reason") == "end_turn" or "StructuredOutput" in tools


def _meta(path: Path) -> dict:
    try:
        data = json.loads(path.with_suffix(".meta.json").read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def compute(session: Path, now: float, files: dict) -> tuple[dict, dict]:
    """The view (live agents, cost per agent type, session output) and the per-file scan state."""
    main = session.with_suffix(".jsonl")
    live, cost, state = [], {}, {}
    for path in [main, *sorted(session.glob("subagents/**/agent-*.jsonl"))]:
        try:
            info = path.stat()
            entry = scan(path, info.st_size, files.get(str(path)))
        except OSError:
            continue
        if "role" not in entry:
            entry["role"] = "main" if path == main else str(_meta(path).get("agentType") or "unknown")
        state[str(path)] = entry
        totals = cost.setdefault(entry["role"], [0, 0, 0, 0])
        for index, value in enumerate([entry["requests"], *entry["tokens"]]):
            totals[index] += value
        age = max(now - info.st_mtime, 0.0)
        if path == main or age > LIVE or entry["final"] or (meta := _meta(path)).get("stoppedByUser"):
            continue
        run = RUN.match(str(meta.get("description") or ""))
        family = FAMILY.match(entry["model"] or "")
        live.append({"run": run.group(1) if run else None, "node": run.group(2) if run else None,
                     "type": entry["role"].rsplit(":", 1)[-1], "age": age,
                     "model": family.group(1) if family else str(entry["model"] or meta.get("model") or "?")})
    live.sort(key=lambda agent: (-agent["age"], agent["type"]))
    view = {"session": session.name[:8], "live": live, "cost": cost, "out": sum(row[1] for row in cost.values())}
    return view, state


def cache_path(session: Path) -> Path:
    digest = hashlib.sha256(str(session).encode()).hexdigest()[:16]
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir()) / f"graph-engineering-status-{digest}.json"


def snapshot(root: Path, now: float) -> dict | None:
    """The session's view, from the cache when under 5 s old; None when the root has no session."""
    session = session_of(root)
    if session is None:
        return None
    target = cache_path(session)
    try:
        if hasattr(os, "getuid") and target.stat().st_uid != os.getuid():
            raise OSError("cache owned by another user")  # a shared /tmp must not feed the status line
        cache = json.loads(target.read_text())
        cache = cache if isinstance(cache, dict) and cache.get("session") == f"{VERSION}:{session}" else {}
    except (OSError, ValueError):
        cache = {}
    if "view" in cache and 0 <= now - cache.get("at", float("-inf")) < TTL:
        return cache["view"]
    view, state = compute(session, now, cache.get("files") or {})
    _store(target, {"session": f"{VERSION}:{session}", "at": now, "view": view, "files": state})
    return view


def _store(target: Path, data: dict) -> None:
    try:
        handle, temp = tempfile.mkstemp(dir=target.parent, prefix=target.name, suffix=".tmp")
    except OSError:
        return  # an unwritable TMPDIR costs a full parse next time, never the status line
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(data, stream)
        os.replace(temp, target)
    except OSError:
        Path(temp).unlink(missing_ok=True)


def human(count: int) -> str:
    return str(count) if count < 1000 else f"{round(count / 1000)}k" if count < 999_500 else f"{count / 1e6:.1f}M"


def _kind(agent: dict, pad: int = 0) -> str:
    """`<type>(<model>) <minutes>m`, with `!` once the agent has been idle over 10 minutes."""
    kind = f"{agent['type']}({agent['model']})"
    return f"{kind:<{pad}} {int(agent['age'] // 60)}m" + "!" * (agent["age"] > STALLED)


def render_line(view: dict | None) -> str:
    """`ge <run8>: <n> live · <type>(<model>) <age>... · out <tokens>`, at most 120 chars, most idle first."""
    if not view or not view["live"]:
        return ""
    tail = f" · out {human(view['out'])}"
    for shown in range(len(view["live"]), -1, -1):
        groups: dict[str, list] = {}
        for index, agent in enumerate(view["live"]):
            group = groups.setdefault(agent["run"] or "other", [0, [], 0])
            group[0] += 1
            if index < shown:
                group[1].append(_kind(agent))
            else:
                group[2] += 1
        text = "ge " + " | ".join(
            f"{run}: {count} live · " + " ".join(tokens + ([f"+{hidden}"] if hidden else []))
            for run, (count, tokens, hidden) in groups.items()) + tail
        if len(text) <= LINE_MAX:
            return text
    return text[:LINE_MAX]


def decisions(root: Path) -> list[str]:
    """Open `- [ ]` cards from every run's decisions.md, prefixed by the run's first 8 chars."""
    cards = []
    for path in sorted(root.glob(".graph/*/decisions.md")):
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        cards += [f"  {path.parent.name[:8]}: {line.strip()[6:].strip()}"[:LINE_MAX]
                  for line in lines if line.strip().startswith("- [ ]")]
    return cards


def _section(title: str, rows: list[str], limit: int, head: tuple[str, ...] = ()) -> list[str]:
    if not rows:
        return [title, "  none"]
    more = [f"  ... {len(rows) - limit} more"] if len(rows) > limit else []
    return [title, *head, *rows[:limit], *more]


def render_full(view: dict | None, root: Path) -> str:
    """RUNNING, NEEDS YOU and COST, at most 40 lines."""
    live = view["live"] if view else []
    header = (f"graph-engineering status · session {view['session']} · out {human(view['out'])}"
              if view else "graph-engineering status · no session found for this directory")
    running = [f"  {(agent['run'] + ':' + agent['node']) if agent['run'] else 'other':<24} {_kind(agent, 28)}"
               for agent in live]
    cost = sorted((view or {}).get("cost", {}).items(), key=lambda item: (-item[1][1], item[0]))
    width = max([len(role) for role, _ in cost] + [4])
    table = [f"  {role:<{width}} {row[0]:>8} {human(row[1]):>8} {human(row[2]):>12} {human(row[3]):>12}"
             for role, row in cost]
    head = (f"  {'type':<{width}} {'requests':>8} {'out':>8} {'cache reads':>12} {'cache writes':>12}",)
    cards = decisions(root)
    lines = [header, *_section(f"RUNNING ({len(live)})", running, 12),
             *_section(f"NEEDS YOU ({len(cards)})", cards, 10), *_section("COST", table, 9, head)]
    return "\n".join(lines[:LINES_MAX])


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--line", action="store_true", help="one status-line row; empty when nothing is live")
    parser.add_argument("--root", type=Path, help="project dir the session started in (default: the cwd)")


def render(line: bool, root: Path | None, now: float | None = None) -> str:
    root = (root or Path.cwd()).resolve()
    view = snapshot(root, time.time() if now is None else now)
    text = render_line(view) if line else render_full(view, root)
    return text + "\n" if text else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    add_arguments(parser)
    args = parser.parse_args(argv)
    sys.stdout.write(render(args.line, args.root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
