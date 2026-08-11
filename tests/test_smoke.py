#!/usr/bin/env python3
"""
Smoke test for drift.py — builds two synthetic transcripts (one that drifts
off-task, one that stays on-task) and asserts the detector calls them
correctly. Stdlib only; run directly:

    python3 tests/test_smoke.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DRIFT_PY = Path(__file__).resolve().parent.parent / "drift.py"

TASK = "Fix login redirect. After login, users get sent to /dashboard instead of the page they originally requested."

DRIFTED_TRANSCRIPT = [
    {"role": "user", "content": TASK},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "auth/callback.ts"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Grep", "input": {"pattern": "redirect", "path": "auth/"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "auth/callback.ts", "old_string": "redirectTo('/dashboard')", "new_string": "redirectTo(returnUrl)"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "npm test auth/callback.test.ts"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "session/store.ts"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "session/tokenRefresh.ts"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "session/store.ts", "old_string": "class SessionStore", "new_string": "abstract class SessionStore"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "session/InMemorySessionStore.ts", "command": "new file"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "session/RedisSessionStore.ts", "command": "new file"}}]},
]

ON_TASK_TRANSCRIPT = [
    {"role": "user", "content": TASK},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "auth/callback.ts"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Grep", "input": {"pattern": "redirect", "path": "auth/"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "auth/callback.ts", "old_string": "redirectTo('/dashboard')", "new_string": "redirectTo(returnUrl)"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "auth/loginRoute.ts"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "auth/loginRoute.ts", "old_string": "login(req)", "new_string": "login(req, returnUrl)"}}]},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "npm test auth/callback.test.ts -- redirect login"}}]},
]


def write_jsonl(path, events):
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def run_drift(path, extra_args):
    proc = subprocess.run(
        [sys.executable, str(DRIFT_PY), str(path)] + extra_args,
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, f"drift.py exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        drifted_path = Path(tmp) / "drifted.jsonl"
        on_task_path = Path(tmp) / "on_task.jsonl"
        write_jsonl(drifted_path, DRIFTED_TRANSCRIPT)
        write_jsonl(on_task_path, ON_TASK_TRANSCRIPT)

        drifted = run_drift(drifted_path, ["--window", "6", "--min-actions", "6"])
        assert drifted["status"] == "drift_detected", f"expected drift_detected, got {drifted['status']}"
        assert drifted["last_relevant_action"]["target"] == "auth/callback.ts", (
            f"expected the anchor to be auth/callback.ts, got {drifted['last_relevant_action']}"
        )

        on_task = run_drift(on_task_path, ["--window", "6", "--min-actions", "6"])
        assert on_task["status"] == "on_task", f"expected on_task, got {on_task['status']}"

    print("OK: rabbit-hole smoke test passed")


if __name__ == "__main__":
    main()
