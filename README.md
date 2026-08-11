# <img src="assets/logo.svg" width="32" height="32" style="vertical-align: middle; margin-right: 8px;" alt="Rabbit Hole logo"> Rabbit Hole

> Catch the moment a session stops fixing the login redirect and starts rewriting the session abstraction.

![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![Agent Skill](https://img.shields.io/badge/Agent-Skill-6C47FF)
![CI](https://github.com/ROM-Cloudia/rabbit-hole/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

Rabbit Hole is a small [agent skill](https://docs.claude.com/en/docs/claude-code/skills) — a dependency-free Python detector plus a documented workflow — for the moment a long tool-call streak quietly stops serving the original task. It scores every tool call in a session transcript against the task's own keywords and names the exact point things went sideways, instead of leaving that judgment to a vague "have I lost the plot?" feeling.

```text
session transcript (JSONL)
  every tool_use, in order
         │
         ├── score vs. task keywords
         │
         ├── find the LAST call that scored > 0  ──► anchor
         │
         └── count calls since the anchor
                    │
                    ├── streak < window  ──► on_task, nothing to report
                    └── streak >= window ──► RABBIT HOLE DETECTED
                                             return to: <anchor file/command>
```

## Why Rabbit Hole?

Scope creep during an agent session rarely looks dramatic in the moment — each individual tool call seems reasonable, and only the accumulated drift is the problem. Rabbit Hole makes that accumulation visible:

- one grep-and-score detector, no dependencies, works on any JSONL transcript;
- finds the exact last on-task action to return to, not just "you might be off track";
- explicit `--window`/`--min-actions` tuning so short sessions and legitimately sprawling refactors don't get falsely flagged;
- the detector produces scored evidence, never the verdict sentence — the skill is what turns that evidence into a report a human can act on.

## Quick start

Requirements: Python 3.8 or newer, no third-party packages.

```bash
git clone https://github.com/ROM-Cloudia/rabbit-hole.git
cd rabbit-hole
python3 tests/test_smoke.py   # optional: confirms the detector works in this environment
```

### Install as a skill

```bash
# Claude Code
cp -r rabbit-hole ~/.claude/skills/rabbit-hole

# Codex / Copilot CLI / Gemini CLI (cross-runtime alias)
cp -r rabbit-hole ~/.agents/skills/rabbit-hole
```

On Windows, use the `py` launcher instead of `python3` in all commands above and below.

## The detector

```bash
python3 drift.py <transcript.jsonl> --task "Fix login redirect"
```

Works on Claude Code's session transcript format (`~/.claude/projects/*/*.jsonl`) as-is, and on any other JSONL transcript that nests `{"type": "tool_use", "name": ..., "input": {...}}` objects somewhere in each line — tool-use blocks are found with a recursive walk, not a fixed schema.

```json
{
  "status": "drift_detected",
  "last_relevant_action": { "index": 2, "name": "Edit", "target": "auth/callback.ts", "relevance": 0.2 },
  "actions_since_last_relevant": [ /* 7 actions, none referencing the task */ ],
  "reason": "7 consecutive actions since action #2 (Edit -> auth/callback.ts) have zero keyword overlap with the task (threshold: 6)"
}
```

The output is evidence — the scored action list and the anchor point — not the human-readable "you are currently: X" sentence. `SKILL.md` documents how to turn that evidence into a report without inventing a narrative the actions don't actually support.

## Tuning

| Flag | Default | Effect |
|---|---|---|
| `--window` | `8` | Consecutive off-task actions required to trigger a detection |
| `--min-actions` | `10` | Minimum total tool calls before drift is evaluated at all |
| `--task` | auto-detected | Original task text; pass explicitly rather than trusting auto-detection on long sessions |

## Development

```bash
python3 tests/test_smoke.py
```

The smoke test builds one transcript that genuinely drifts and one that stays on-task, runs the real detector against both, and asserts the verdicts land correctly. No network access, no paid API, no third-party dependencies.

## License

[MIT](LICENSE)
