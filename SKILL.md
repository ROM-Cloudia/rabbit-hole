---
name: rabbit-hole
description: Use after a long stretch of tool calls in the current session, or when a task that started small has visibly expanded in scope, to check whether the agent has drifted from the original task — "have I lost the plot", "am I still on task", "check for scope creep", "did I wander off". Also use periodically during any session with 10+ tool calls on an open-ended task.
---

# Rabbit Hole

## Overview

Detects when a session has drifted from its original task by comparing the
most recent tool calls against the task's own keywords. If there's a run of
consecutive actions with zero keyword overlap with the task, following an
earlier action that DID connect to it, that's a rabbit hole: the last
connected action is where things went sideways.

## When to Use

- After 10+ tool calls in a session working on something open-ended
  (refactors, "fix this bug" where the fix keeps growing, exploratory
  debugging).
- When you notice the files you're touching don't obviously relate to what
  was originally asked.
- Periodically as a self-check — don't wait for the user to ask "are you
  still doing X?"

Don't use for short, bounded tasks (a few tool calls) — there's nothing to
detect drift against yet, and the script will correctly refuse to evaluate
below `--min-actions`.

## Workflow

1. Run the detector against the current session's transcript:
   ```
   py drift.py <transcript.jsonl> --task "<original task, verbatim>"
   ```
   On Claude Code, the current session's transcript is the `.jsonl` file
   under `~/.claude/projects/<project>/<session-id>.jsonl` — use the most
   recently modified one for the current project if you don't have the exact
   path. Passing `--task` explicitly is more reliable than auto-detection;
   only omit it if you don't have the original task text handy, in which
   case the script falls back to the first user message in the transcript.

2. Read the JSON output:
   - `status: "on_task"` — stop here, nothing to report.
   - `status: "never_on_task"` — the task text or its auto-detection is
     probably wrong; don't report a false rabbit-hole, fix the `--task`
     value and rerun.
   - `status: "drift_detected"` — `last_relevant_action` is the anchor point
     to return to; `actions_since_last_relevant` is the evidence trail of
     what happened since.

3. **The script does not write the verdict sentence for you.** It gives you
   raw evidence (a list of tool names + targets with zero task-keyword
   overlap). Synthesize the "you are currently: ..." line yourself, in your
   own words, from what's actually in `actions_since_last_relevant` — don't
   invent a narrative that isn't supported by the listed actions, and don't
   just dump the raw JSON at the user.

4. Report in this shape:

   ```
   RABBIT HOLE DETECTED.

   Original task:
   Fix login redirect.

   You are currently:
   rewriting the session storage abstraction (session/store.ts,
   InMemorySessionStore.ts, RedisSessionStore.ts — 7 actions, none
   referencing login/redirect/dashboard).

   Return to:
   auth/callback.ts (last action connected to the task, #2 in this session).
   ```

   Open the returned file yourself to give an exact line number if useful —
   the script only knows file paths from tool inputs, not line numbers.

## Quick Reference

| Field | Meaning |
|---|---|
| `last_relevant_action` | Last tool call whose target/content shared a keyword with the task |
| `actions_since_last_relevant` | Everything after that, in order — the drift evidence |
| `drift_detected: true` | Streak length since the anchor met/exceeded `--window` (default 8) |
| `status: "never_on_task"` | Nothing ever matched — check `--task` before trusting anything else |

## Tuning

- `--window N` — how many consecutive off-task actions triggers a detection
  (default 8). Lower it for short, tightly-scoped tasks; raise it for
  sprawling refactors where some legitimate wandering is expected.
- `--min-actions N` — refuse to evaluate below this many total tool calls
  (default 10), so a 3-tool-call session never gets falsely flagged.

## Common Mistakes

- Trusting auto-detected task text without checking it — the first user
  message in a long session may itself already be several turns removed
  from what's currently being worked on. Pass `--task` explicitly when in
  doubt.
- Writing a dramatic "you are currently..." line not actually backed by the
  listed actions. Every claim in that line must trace to a specific entry in
  `actions_since_last_relevant`.
- Flagging drift on a task that legitimately requires touching seemingly
  unrelated files (e.g. fixing a shared type breaks three other files) —
  keyword overlap is a heuristic, not ground truth. If the off-task-looking
  actions are still clearly in service of the original ask, say so instead
  of forcing a rabbit-hole verdict.
