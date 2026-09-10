"""Build one hook event's JSON input, the shape the hooks reference documents.

Usage: make-input.py <EventName> [key=value ...]

The common fields come from "Common input fields"; the event-specific fields
come from "PostToolUse input", "Stop input" and "SessionStart input".
https://code.claude.com/docs/en/hooks
"""

import json
import sys

COMMON = {
    "session_id": "test-session",
    "transcript_path": "/dev/null",
    "cwd": "/",
    "permission_mode": "default",
}


def build(event, options):
    payload = dict(COMMON, hook_event_name=event)

    if event == "PostToolUse":
        file_path = options.get("file_path")
        payload["tool_name"] = options.get("tool_name", "Edit")
        payload["tool_input"] = {"file_path": file_path} if file_path else {}
        payload["tool_response"] = {"filePath": file_path, "success": True}
        payload["tool_use_id"] = "toolu_test"
        payload["duration_ms"] = 12
    elif event == "Stop":
        payload["stop_hook_active"] = options.get("stop_hook_active") == "true"
        payload["last_assistant_message"] = "done"
        payload["background_tasks"] = []
        payload["session_crons"] = []
    elif event == "SessionStart":
        payload["source"] = options.get("source", "startup")
    else:
        raise SystemExit("unknown event: %s" % event)

    return payload


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    options = {}
    for item in argv[2:]:
        key, _, value = item.partition("=")
        options[key] = value
    print(json.dumps(build(argv[1], options)))


if __name__ == "__main__":
    main(sys.argv)
