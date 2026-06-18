#!/usr/bin/env python3
"""Stop hook: deterministic backstop for the two-tier autoflagger.

Tier 1 is the agent itself — a CLAUDE.md rule has it self-flag flag-worthy moments
inline (the semantic judgment, free, with full context). This script is tier 2: a
mechanical net that catches one unambiguous, keyword-detectable class the agent might
skip — an *admitted error* in the just-finished response (the same pattern
`mine-session` step 0b hunts). It appends a GOVERNANCE flag to the same
`~/.claude/session-flags.md` that `/flag` writes and `/mine-session` drains.

No LLM call: regex only. Three load-bearing properties, mirroring craft_reminder.py —
fires at most once per matched snippet (a backstop that repeats becomes noise), never
blocks the stop, and fails open (malformed input or any error exits silently; a
bookmark has no business stopping work).

Wire in .claude/settings.json:

    {"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "python3 tools/autoflag.py"}]}]}}

(Path is relative to the project; use "$CLAUDE_PROJECT_DIR/tools/autoflag.py" if the
hook may run from another cwd.)
"""
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

FLAGS_FILE = Path.home() / ".claude" / "session-flags.md"

# Admitted-error patterns — kept tight to avoid false positives. Each marks a moment
# mine-session step 0b would treat as a governance-change candidate.
PATTERNS = [
    r"\bI was wrong\b",
    r"\bI was mistaken\b",
    r"\bmy mistake\b",
    r"\bI should have (?:checked|verified|read|tested|looked|run)\b",
    r"\bI (?:asserted|claimed|said|stated|assumed)\b[^.]{0,60}\bwithout (?:verifying|checking|testing|reading)\b",
    r"\bI didn'?t (?:verify|check|test|read|run)\b",
    r"\bI (?:incorrectly|wrongly|falsely) (?:assumed|claimed|stated|said|reported)\b",
    r"\bturns out (?:I was|that was) (?:wrong|mistaken|incorrect)\b",
]
_RX = re.compile("|".join(PATTERNS), re.IGNORECASE)


def last_assistant_text(transcript_path):
    """Return the text of the final assistant message in the transcript, or ''."""
    text = ""
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "assistant":
                    continue
                content = (obj.get("message") or {}).get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = [
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    if any(parts):
                        text = "\n".join(p for p in parts if p)
    except Exception:
        return ""
    return text


def matched_sentence(text, match):
    """The sentence containing the match, trimmed to a one-liner."""
    start = text.rfind(".", 0, match.start()) + 1
    end = text.find(".", match.end())
    end = len(text) if end == -1 else end + 1
    sentence = " ".join(text[start:end].split())
    return sentence[:160].rstrip()


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # fail open

    # Don't act on a stop the agent is already being forced to continue.
    if data.get("stop_hook_active"):
        return

    transcript = data.get("transcript_path")
    if not transcript:
        return

    text = last_assistant_text(transcript)
    if not text:
        return

    m = _RX.search(text)
    if not m:
        return

    summary = matched_sentence(text, m)

    # Dedup: one flag per (session, matched-snippet). craft_reminder.py uses the same
    # /tmp-marker idiom.
    session = str(data.get("session_id", "unknown"))
    digest = hashlib.sha1((session + summary).encode("utf-8")).hexdigest()[:12]
    marker = Path("/tmp") / f"autoflag_{session}_{digest}"
    if marker.exists():
        return
    try:
        marker.touch()
    except Exception:
        pass  # if /tmp is unwritable we may double-flag; still better than silent loss

    entry = (
        f"\n## [GOVERNANCE] Admitted error — {summary}\n"
        f"> Auto-flagged by tools/autoflag.py (Stop-hook backstop): the response "
        f"contained an admitted-error signal mine-session 0b routes to a governance "
        f"candidate. Verify it's real before acting on it.\n"
        f"> Flagged: {date.today().isoformat()}\n"
    )
    try:
        FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FLAGS_FILE, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception:
        return  # fail open


if __name__ == "__main__":
    main()
