#!/usr/bin/env python3
"""Stop hook: deterministic backstop for the autoflagger.

Tier 1 is the agent itself — a CLAUDE.md rule has it self-flag flag-worthy moments
inline (the semantic judgment, free, with full context). This script is tier 2: a
mechanical net for moments the agent skips when context is crowded. It has two layers,
both LLM-free and deterministic:

  - a fixed **regex floor** — the unambiguous, keyword-detectable *admitted-error*
    class (the same pattern `mine-session` step 0b hunts); and
  - a **self-improving lexical layer** (`flag_corpus.py`) that scores the response
    against a corpus of known flag-worthy phrasings and fires on a strong match. The
    corpus is seeded from the regex patterns and grows at mine-time from the manual
    flags this layer missed, so its recall converges on the phrasings that recur.

Both append a flag to this session's file under `~/.claude/session-flags/<session_id>.md`
— the same per-session store `/flag` writes and `/mine-session` drains. This hook is
**read-only on the corpus**: all corpus mutation happens at mine-time (see
`flag_corpus.py`), never here, where concurrent sessions would clobber a shared file.

Input window: **all assistant text since the previous Stop**, not just the final
message. The final message races the hook — the harness flushes it to the transcript
within the same tens of ms the hook starts reading, so a last-message-only design
routinely scores the *penultimate* message (measured 2026-07-31: last-flush→hook gaps
of 58ms–1.7s against a 52–147ms hook runtime; 3-of-13 expected fires became 0). The
window sidesteps that race instead of racing better: a per-session scan offset in
/tmp marks how far the last invocation read, so a block that flushes after this
invocation reads is simply picked up by the next one. It also makes mid-turn
narration reachable — admissions the old design could never see by construction.
The window is capped (chars, newest-first) and code spans are blanked before
matching (fences and backticks ONLY — never quote characters, and never apostrophes:
admissions are contraction-heavy first-person prose, so apostrophe-stripping
destroys exactly the class this tool exists to catch).

Three load-bearing properties, mirroring craft_reminder.py — fires at most once per
matched snippet (a backstop that repeats becomes noise), never blocks the stop, and
fails open (malformed input or any error exits silently; a bookmark has no business
stopping work). The lexical layer is an optional import: if it can't load, the regex
floor still fires. Fail-open is NOT fail-silent: set AUTOFLAG_DEBUG=1 to append one
line per invocation to ~/.claude/logs/autoflag.log (window size, offsets, match
results) — the observability whose absence made the flush race expensive to find.

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
import time
from datetime import date, datetime
from pathlib import Path

# The lexical layer lives beside this script. Import is fail-open: a fork without it
# (or a load error) degrades to the regex floor, never an error in the Stop hook.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import flag_corpus
except Exception:
    flag_corpus = None

FLAGS_DIR = Path.home() / ".claude" / "session-flags"
LOG_FILE = Path.home() / ".claude" / "logs" / "autoflag.log"

# Window cap in chars, newest text kept. p95 of real since-last-Stop windows is
# ~8.7k, p99 ~16k (measured over 602 turns, 2026-07-31); the cap exists for the
# unbounded tail after a --resume or compact boundary, not the typical turn.
WINDOW_CAP = 16_000
# Wall-clock budget handed to the lexical layer. score_text is O(sentences ×
# corpus entries) with an add-only corpus, so cost grows over time; a Stop hook
# has no business spending more than this regardless of corpus size.
SCORE_BUDGET_MS = 150
# A sentence that lost more than this fraction of its tokens to code-stripping is
# mostly code — skip it rather than score the mutilated remainder (stripping
# shrinks the Jaccard union denominator, which *raises* scores on fragments).
MUTILATION_MAX_LOSS = 0.4
# At most this many regex-floor flags per invocation — the window can now hold a
# whole turn, and a backstop that dumps five flags at once becomes noise.
MAX_REGEX_FLAGS = 3

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


def _assistant_text(obj):
    """Text of one assistant transcript line, '' if not one (sidechains excluded)."""
    if obj.get("type") != "assistant" or obj.get("isSidechain"):
        return ""
    content = (obj.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""


def _real_user_prompt(obj):
    """True for an actual user prompt line — not a tool_result carrier, which the
    transcript also records as type 'user'."""
    if obj.get("type") != "user" or obj.get("isSidechain"):
        return False
    content = (obj.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        kinds = {b.get("type") for b in content if isinstance(b, dict)}
        return "text" in kinds and "tool_result" not in kinds
    return False


def _scan_state_path(session):
    return Path("/tmp") / f"autoflag_scanpos_{session}.json"


def _parse(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {}


def window_since_last_stop(transcript, session, dbg):
    """All assistant text flushed since the previous invocation's read point.

    The read point is a persisted per-session line offset — NOT a boundary inferred
    per-invocation — because that is what kills the flush race: whatever the harness
    hadn't flushed when this invocation read the file sits past the saved offset and
    is scanned by the next invocation instead of being lost. Two details carry that
    guarantee: a torn tail line (no trailing newline — still mid-flush) is not
    counted, so the offset never advances past text that hasn't finished landing;
    and the state carries a hash of the last counted line, so a same-path rewrite
    (compaction) can't smuggle a numerically-valid offset onto different content.

    With no valid state (first Stop of a session, a rewritten transcript, a changed
    path) the fallback is the current turn only: assistant lines after the last
    real user prompt — and if no real prompt exists, nothing at all. Never the
    whole file: a resumed session's transcript replays ancestor history, and
    scanning it would flag admissions from turns already mined.

    Known residual: the SESSION-FINAL block can still lose the race — there is no
    next invocation to pick it up. Every earlier block is covered.

    Returns UNCAPPED text; the caller caps AFTER code-span stripping (a cap cut
    inside a fence would orphan the closing ``` and blank everything after it).
    """
    try:
        with open(transcript, encoding="utf-8") as fh:
            content = fh.read()
    except Exception:
        return ""
    if content and not content.endswith("\n"):
        content = content[:content.rfind("\n") + 1]  # torn tail: not flushed yet
    raw_lines = [l for l in content.splitlines() if l.strip()]

    state_path = _scan_state_path(session)
    start = None
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
        if state.get("transcript") == str(transcript):
            n = int(state.get("lines", -1))
            if 0 <= n <= len(raw_lines) and (
                    n == 0 or _line_sha(raw_lines[n - 1]) == state.get("tail")):
                start = n
    except Exception:
        pass
    if start is not None:
        dbg["boundary"] = "offset"
        objs = [_parse(r) for r in raw_lines[start:]]
    else:
        # Parse everything only on this (rare) path; the offset path parses just
        # the suffix — a whole-transcript parse costs ~185ms at 27MB, more than
        # the entire hook budget.
        all_objs = [_parse(r) for r in raw_lines]
        last_prompt = -1
        for i, obj in enumerate(all_objs):
            if _real_user_prompt(obj):
                last_prompt = i
        start = last_prompt + 1 if last_prompt >= 0 else len(raw_lines)
        objs = all_objs[start:]
        dbg["boundary"] = ("fallback:last-prompt" if last_prompt >= 0
                          else "fallback:no-prompt")

    new_state = {"transcript": str(transcript), "lines": len(raw_lines),
                 "tail": _line_sha(raw_lines[-1]) if raw_lines else ""}
    try:
        import tempfile
        fd, tmp = tempfile.mkstemp(dir="/tmp", prefix="autoflag_scanpos_tmp_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(new_state, fh)
        os.replace(tmp, state_path)  # atomic; never truncates through a symlink
    except Exception:
        pass  # worst case: next invocation falls back to current-turn-only

    dbg["scanned_lines"] = f"{start}..{len(raw_lines)}"
    texts = [t for t in (_assistant_text(o) for o in objs) if t]
    dbg["blocks"] = len(texts)
    return "\n\n".join(texts)


def _line_sha(raw_line):
    return hashlib.sha1(raw_line.encode("utf-8")).hexdigest()[:16]


# --- code-span blanking (match on stripped, report from original) ---------------
#
# Fenced blocks and inline backtick spans are blanked before matching so quoted
# code can't trip the matcher — but ONLY those. Never quote characters, never
# apostrophes: admissions are contraction-heavy first-person prose ("You're right,
# I didn't check"), so apostrophe-stripping destroys exactly the target class.
# Blanked chars become spaces EXCEPT sentence punctuation and newlines, which are
# kept — that preserves every char offset and every sentence boundary, so a match
# found in the stripped text reports its sentence from the original text with no
# offset bookkeeping.

_FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# The sentence splitter MUST be the lexical layer's own: _original_sentence maps
# score_text's sentence back to the original by index, and matched_sentence's
# boundaries feed the dedup key both layers must agree on. A local copy is only
# the fallback for a fork missing flag_corpus (where neither consumer exists).
_SENT_SPLIT_RE = (flag_corpus._SENT_SPLIT if flag_corpus is not None
                  else re.compile(r"[.!?\n]+"))
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _blank(m):
    return "".join(c if c in ".!?\n" else " " for c in m.group(0))


def strip_code_spans(text):
    return _INLINE_CODE_RE.sub(_blank, _FENCE_RE.sub(_blank, text))


def _sentence_spans(text):
    """(start, end) spans of the same sentences _SENT_SPLIT_RE splitting yields."""
    spans, pos = [], 0
    for m in _SENT_SPLIT_RE.finditer(text):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return spans


def guard_mutilated(original, stripped):
    """Blank any sentence that lost more than MUTILATION_MAX_LOSS of its tokens to
    stripping. A mostly-code sentence's surviving fragment is not prose — and under
    Jaccard a shrunken sentence *scores higher*, so scoring fragments manufactures
    false positives rather than merely wasting time."""
    out = list(stripped)
    for s, e in _sentence_spans(stripped):
        orig_n = len(_TOKEN_RE.findall(original[s:e].lower()))
        strip_n = len(_TOKEN_RE.findall(stripped[s:e].lower()))
        if orig_n and (orig_n - strip_n) / orig_n > MUTILATION_MAX_LOSS:
            for i in range(s, e):
                if out[i] not in ".!?\n":
                    out[i] = " "
    return "".join(out)


def matched_sentence(text, match):
    """The sentence containing the match, trimmed to a one-liner. Sentence
    boundaries come from the SAME splitter the lexical layer uses — if the two
    layers segment differently they report different content for one moment,
    diverge on the dedup key, and the single-flag-per-moment guarantee breaks."""
    for s, e in _sentence_spans(text):
        if s <= match.start() < e:
            return " ".join(text[s:e].split())[:160].rstrip()
    return " ".join(text[match.start():match.end()].split())[:160].rstrip()


def _log_debug(dbg):
    """One line per invocation when AUTOFLAG_DEBUG is set. Fail-open stays right for
    a Stop hook; fail-open AND silent made the flush race a forensic exercise —
    found-nothing, crashed, and read-the-wrong-window must be distinguishable."""
    if not os.environ.get("AUTOFLAG_DEBUG"):
        return
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            if LOG_FILE.stat().st_size > 2_000_000:
                os.replace(LOG_FILE, LOG_FILE.with_suffix(".log.1"))
        except OSError:
            pass
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(
                {"ts": datetime.now().isoformat(timespec="milliseconds"), **dbg},
                ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    dbg = {}
    t0 = time.monotonic()
    try:
        _main(dbg)
    except Exception as exc:  # fail open — but never silently when debugging
        dbg["error"] = f"{type(exc).__name__}: {exc}"
    dbg["ms"] = round((time.monotonic() - t0) * 1000, 1)
    _log_debug(dbg)


def _main(dbg):
    try:
        data = json.load(sys.stdin)
    except Exception:
        dbg["skip"] = "bad-stdin"
        return  # fail open

    # Don't act on a stop the agent is already being forced to continue. The scan
    # offset is deliberately NOT advanced here, so the skipped text is scanned by
    # the invocation that ends the forced continuation.
    if data.get("stop_hook_active"):
        dbg["skip"] = "stop_hook_active"
        return

    transcript = data.get("transcript_path")
    if not transcript:
        dbg["skip"] = "no-transcript"
        return

    # Key off the harness env var, NOT the payload's `session_id`. The two were
    # verified equivalent when per-session flag files were introduced
    # (docs/decisions/2026-06-18-per-session-flags.md), and that premise has since
    # been falsified: in a RESUMED session the payload carries the *ancestor*
    # session's id while $CLAUDE_CODE_SESSION_ID holds the live one (measured
    # 2026-07-31: ~10 of 33 recent sessions on the author's machine). Keying off the
    # payload files an auto-flag under a dead ancestor id, so /statusline's
    # per-session count and /mine-session's attribution both point at the wrong
    # session — the two things per-session files exist to provide. The /flag skill
    # already uses the env var, so this also makes the two producers agree.
    #
    # The staleness is FIELD-SPECIFIC, not payload-wide: measured 2026-07-31 via this
    # hook's own scanpos record, `transcript_path` carried the LIVE session's file in
    # the same resumed session whose `session_id` was the ancestor's (scanpos named
    # b7b8ef0e…jsonl at line 1132; the ancestor's transcript is 515 lines and frozen).
    # So `Path(transcript).stem` would in fact resolve correctly today — it is omitted
    # anyway because deriving identity from a path is a second-order inference that the
    # harness could change without notice, and the env var is the authoritative source
    # the /flag skill already uses. "unknown" is the honest failure; /mine-session's
    # directory sweep still drains it.
    session = os.environ.get("CLAUDE_CODE_SESSION_ID") or str(
        data.get("session_id", "unknown"))
    dbg["session"] = session

    full = window_since_last_stop(transcript, session, dbg)
    if not full:
        return

    # Strip code spans BEFORE capping: a cap cut landing inside a fenced block
    # would orphan the closing ``` , which then pairs with end-of-text and blanks
    # every later sentence — the newest prose, on exactly the big code-heavy turns
    # the cap exists for. Stripping first sees balanced fences; the identical
    # slice then keeps original and stripped offset-aligned.
    stripped = strip_code_spans(full)
    text, stripped = full[-WINDOW_CAP:], stripped[-WINDOW_CAP:]
    dbg["chars"] = len(text)

    # Layer 1 — regex floor on the code-stripped text (NOT the mutilation-guarded
    # text: the guard's rationale is Jaccard-specific — fragments inflate scores —
    # and gates nothing the floor's precise patterns need; applied here it would
    # blank admissions that name the unchecked thing in backticks, which is the
    # house style for exactly the moments this floor exists to catch). The window
    # can hold several distinct admissions, so flag each matched sentence, bounded
    # — and the bound counts WRITES, not attempts: on a fallback rescan the
    # already-flagged (marker-deduped) sentences are no-ops and must not starve a
    # genuinely new admission out of its slot.
    attempted, writes = set(), 0
    for m in _RX.finditer(stripped):
        sentence = matched_sentence(text, m)
        if sentence in attempted:
            continue
        attempted.add(sentence)
        if _write_flag(session, "GOVERNANCE", sentence,
                       "the response contained an admitted-error signal "
                       "mine-session 0b routes to a governance candidate"):
            writes += 1
        if writes >= MAX_REGEX_FLAGS:
            break
    dbg["regex_fires"] = writes

    # Layer 2 — self-improving lexical match (optional, read-only on the corpus),
    # fed the mutilation-guarded text: a sentence that lost most of its tokens to
    # code-stripping scores artificially high under Jaccard and must not fire.
    if flag_corpus is not None:
        matchable = guard_mutilated(text, stripped)
        try:
            hit = flag_corpus.score_text(matchable, budget_ms=SCORE_BUDGET_MS)
        except TypeError:
            # A fork whose flag_corpus predates the budget parameter.
            try:
                hit = flag_corpus.score_text(matchable)
            except Exception:
                hit = None
        except Exception:
            hit = None
        if hit:
            wrote = _write_flag(
                session, hit["label"],
                _original_sentence(text, matchable, hit["sentence"]),
                f"lexical match (score {hit['score']}) on the learned phrase "
                f"{hit['phrase']!r}", layer="lexical")
            if wrote:
                dbg["lexical_fire"] = hit["phrase"]


def _original_sentence(original, matchable, stripped_sentence):
    """Map a sentence score_text returned (from the stripped text) back to its
    original wording — the flag file is for a human, mutilated text is not."""
    for s, e in _sentence_spans(matchable):
        if matchable[s:e].strip()[:200] == stripped_sentence:
            return " ".join(original[s:e].split())
    return stripped_sentence  # fallback: better a stripped snippet than none


def _write_flag(session, label, summary, reason, layer="regex"):
    """Append one auto-flag, deduped to once per (session, matched-snippet).
    Returns True only if a flag was actually WRITTEN — callers count writes
    against the per-invocation cap, and a marker-deduped no-op must not spend a
    slot. Mirrors craft_reminder.py's /tmp-marker idiom; fails open on every step."""
    summary = " ".join((summary or "").split())[:160].rstrip()
    if not summary:
        return False
    # Dedup key is the punctuation/case-collapsed snippet. Both layers report the
    # sentence from the ORIGINAL text with boundaries from the SAME splitter, so
    # they land on the SAME marker when they catch one moment. First writer wins;
    # the regex floor runs first, so an admitted error stays one GOVERNANCE flag
    # rather than a GOVERNANCE + lexical pair.
    key = re.sub(r"[^a-z0-9]+", " ", summary.lower()).strip()
    digest = hashlib.sha1((session + key).encode("utf-8")).hexdigest()[:12]
    marker = Path("/tmp") / f"autoflag_{session}_{digest}"
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False  # already flagged this snippet this session
    except Exception:
        pass  # if /tmp is unwritable we may double-flag; still better than silent loss

    entry = (
        f"\n## [{label}] Auto-flag ({layer}) — {summary}\n"
        f"> Auto-flagged by tools/autoflag.py (Stop-hook backstop): {reason}. "
        f"Verify it's real before acting on it.\n"
        f"> Flagged: {date.today().isoformat()}\n"
    )
    flags_file = FLAGS_DIR / f"{session}.md"
    try:
        FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(flags_file, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception:
        return False  # fail open
    return True


if __name__ == "__main__":
    main()
