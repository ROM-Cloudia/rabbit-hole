# 🕳️ rabbit-hole

A [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills) that
detects when an agent session has drifted from its original task.

```
RABBIT HOLE DETECTED.

Original task:
Fix login redirect.

You are currently:
rewriting the session abstraction.

Return to:
auth/callback.ts line 71.
```

It works by scoring every tool call in a session transcript against the
keywords of the original task, then looking for a run of consecutive
actions with zero overlap, following an action that DID connect — that
earlier action is the last point the session was still anchored to the task.

## Install

```
# Claude Code
cp -r rabbit-hole ~/.claude/skills/rabbit-hole

# Codex / Copilot CLI / Gemini CLI (cross-runtime alias)
cp -r rabbit-hole ~/.agents/skills/rabbit-hole
```

## Use

After a long tool-call streak on an open-ended task, ask:

- "Have I lost the plot?"
- "Am I still on task?"
- "Check for scope creep in this session."

The skill runs `drift.py` against the current session transcript and reports
whether — and exactly where — things wandered.

## How the detector works

`drift.py` is a dependency-free Python 3 script (stdlib only):

```
py drift.py <transcript.jsonl> --task "Fix login redirect"
```

It works on Claude Code's session transcript format
(`~/.claude/projects/*/*.jsonl`) as-is, and on any other JSONL transcript
that nests `{"type": "tool_use", "name": ..., "input": {...}}` objects
somewhere in each line — tool-use blocks are found with a recursive walk,
not a fixed schema.

For each tool call it builds a "target" string (file path, command,
pattern, or the old/new content of an edit) and scores its keyword overlap
with the task. If `--window` (default 8) consecutive calls in a row have
zero overlap, following a call that did overlap, that's a detected rabbit
hole — the output names the last on-task call as the return point.

The script only produces evidence — the scored action list and the anchor
point. Turning that into the human-readable "you are currently: X" sentence
is the agent's job, described in `SKILL.md`.

## License

MIT
