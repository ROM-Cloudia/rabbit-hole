#!/usr/bin/env python3
"""
rabbit-hole drift — detect when an agent session has wandered from its
original task.

Usage:
    py drift.py <transcript.jsonl> [--task "Fix login redirect"]
                                    [--window 8] [--min-actions 10]

Input:
    A JSONL transcript — one JSON object per line. Works with Claude Code's
    session transcript format (~/.claude/projects/*/*.jsonl) as-is, and with
    any other transcript that nests {"type": "tool_use", "name": ..., "input":
    {...}} objects somewhere in each line, since tool-use blocks are found by
    a recursive walk rather than a fixed schema.

What it does:
    1. Extracts every tool_use event in order, and a short "target" string for
       each (file_path / path / command / pattern / query — whatever the tool
       input contains).
    2. Builds a keyword set from the original task (either passed with --task,
       or auto-detected as the first user message in the transcript).
    3. Scores each tool_use's relevance to the task: overlap-coefficient
       between the target's tokens and the task's tokens.
    4. Finds the last action with nonzero overlap (the "anchor"), then counts
       how many actions have happened since. If that streak of zero-overlap
       actions reaches `--window`, the anchor is where the session was last
       connected to the task — everything since is candidate drift.

This script only produces evidence (the task keywords, the scored action
list, the last on-task action). It does NOT write the human-readable verdict
sentence ("you are currently rewriting the session abstraction") — that
synthesis from raw evidence is the job described in SKILL.md, done by the
agent reading this output, not by this script.

Output: JSON to stdout.
"""
import argparse
import json
import re
import sys

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "with", "this", "that",
    "have", "from", "was", "were", "will", "your", "our", "into", "onto",
    "then", "than", "when", "what", "which", "who", "why", "how", "can",
    "could", "should", "would", "does", "did", "has", "had", "its", "it's",
    "about", "just", "some", "such", "make", "made", "also", "each", "any",
    "one", "two", "get", "got", "use", "used", "using",
}

TARGET_INPUT_KEYS = ("file_path", "path", "command", "pattern", "query",
                      "description", "prompt", "url", "notebook_path")

# Included for relevance scoring only (they carry the real signal about what
# changed) but kept out of the short human-readable "target" label, since a
# whole old_string/new_string diff is too long to show as one line.
CONTENT_KEYS = ("old_string", "new_string", "content")
MAX_CONTENT_CHARS = 300


def load_jsonl(path):
    events = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def walk_tool_uses(obj, out):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use":
            out.append(obj)
        for v in obj.values():
            walk_tool_uses(v, out)
    elif isinstance(obj, list):
        for item in obj:
            walk_tool_uses(item, out)


def walk_first_user_text(obj):
    """Find the first plain-text user message in the transcript, to
    auto-detect the original task when --task isn't given."""
    if isinstance(obj, dict):
        if obj.get("role") == "user" or obj.get("type") == "user":
            content = obj.get("content") or obj.get("message", {}).get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        return item.get("text", "")
    return None


def tokenize(text):
    return {w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", (text or "").lower())
            if w not in STOPWORDS}


def overlap_coefficient(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b))


def target_of(tool_use):
    """Returns (name, label, scoring_text). `label` is a short human-readable
    target for display (first matching field). `scoring_text` additionally
    folds in old_string/new_string/content so relevance scoring sees the
    actual code being touched, not just the file path."""
    name = tool_use.get("name", "unknown")
    inp = tool_use.get("input", {}) or {}
    label = ""
    for key in TARGET_INPUT_KEYS:
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            label = v.strip()
            break
    scoring_parts = []
    for key in TARGET_INPUT_KEYS:
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            scoring_parts.append(v.strip())
    for key in CONTENT_KEYS:
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            scoring_parts.append(v.strip()[:MAX_CONTENT_CHARS])
    return name, label, " ".join(scoring_parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--task", default=None, help="Original task text; auto-detected from the first user message if omitted")
    ap.add_argument("--window", type=int, default=8, help="How many of the most recent actions count as 'recent'")
    ap.add_argument("--min-actions", type=int, default=10, help="Don't evaluate drift until at least this many tool_use events exist")
    args = ap.parse_args()

    events = load_jsonl(args.transcript)

    task_text = args.task
    if not task_text:
        for e in events:
            t = walk_first_user_text(e)
            if t:
                task_text = t
                break

    if not task_text:
        print(json.dumps({"error": "could not auto-detect the original task; pass --task explicitly"}))
        sys.exit(1)

    task_tokens = tokenize(task_text)

    tool_uses = []
    for e in events:
        walk_tool_uses(e, tool_uses)

    actions = []
    for i, tu in enumerate(tool_uses):
        name, label, scoring_text = target_of(tu)
        score = overlap_coefficient(task_tokens, tokenize(scoring_text))
        actions.append({"index": i, "name": name, "target": label, "relevance": round(score, 3)})

    result = {
        "task": task_text,
        "task_tokens": sorted(task_tokens),
        "total_actions": len(actions),
        "window": args.window,
    }

    if len(actions) < args.min_actions:
        result["status"] = "insufficient_data"
        result["drift_detected"] = False
        result["reason"] = f"only {len(actions)} tool_use actions found; need at least {args.min_actions} before evaluating drift"
        print(json.dumps(result, indent=2))
        return

    relevant_indices = [a["index"] for a in actions if a["relevance"] > 0]
    last_relevant = actions[relevant_indices[-1]] if relevant_indices else None
    streak_start = (relevant_indices[-1] + 1) if relevant_indices else 0
    irrelevant_streak = actions[streak_start:]

    result["last_relevant_action"] = last_relevant
    result["actions_since_last_relevant"] = irrelevant_streak

    if last_relevant is not None and len(irrelevant_streak) >= args.window:
        result["status"] = "drift_detected"
        result["drift_detected"] = True
        result["reason"] = (
            f"{len(irrelevant_streak)} consecutive actions since action #{last_relevant['index']} "
            f"({last_relevant['name']} -> {last_relevant['target']}) have zero keyword overlap with the task "
            f"(threshold: {args.window})"
        )
    elif last_relevant is None:
        result["status"] = "never_on_task"
        result["drift_detected"] = False
        result["reason"] = "no action in this transcript has any keyword overlap with the detected task — task text may be wrong, or task auto-detection picked the wrong message; check with --task"
    else:
        result["status"] = "on_task"
        result["drift_detected"] = False
        result["reason"] = f"only {len(irrelevant_streak)} action(s) since the last on-task action (threshold: {args.window})"

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
