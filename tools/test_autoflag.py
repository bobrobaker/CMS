#!/usr/bin/env python3
"""Behavioral tests for the widened-window autoflag: `python3 tools/test_autoflag.py`.

Each test builds a fake transcript, invokes autoflag.py as a subprocess with a fake
Stop payload, and asserts on the flags file / scan state / debug log. Stdlib only,
no framework; exits non-zero on any failure. The tests write real (test-prefixed,
self-cleaning) entries under ~/.claude/session-flags/ and /tmp — they exercise the
actual fail-open subprocess path, not a mock, because the hook's failure mode under
test IS silent no-op.

Coverage worth knowing when editing autoflag.py: the flush-race recovery (T2, T17),
fallback boundaries (T4, T18, T19), code-span blanking + report-from-original
(T5, T6, T9, T15, T16), cross-layer dedup on one splitter (T14), and the
write-counted flag cap (T8, T21) — most of these encode defects found in the
2026-07-31 reviews, so a regression here is a known-bad state, not a style choice."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
FLAGS_DIR = Path.home() / ".claude" / "session-flags"
LOG_FILE = Path.home() / ".claude" / "logs" / "autoflag.log"

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def user_line(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_result_line():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def asst_line(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": text}]}}


def write_transcript(path, lines):
    with open(path, "w") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")


def run_hook(transcript, session, debug=True):
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID=session)
    if debug:
        env["AUTOFLAG_DEBUG"] = "1"
    payload = json.dumps({"transcript_path": str(transcript),
                          "session_id": session, "hook_event_name": "Stop"})
    r = subprocess.run([sys.executable, str(TOOLS / "autoflag.py")],
                       input=payload, capture_output=True, text=True, env=env)
    assert r.returncode == 0, f"hook exited {r.returncode}: {r.stderr}"
    return r


def flags(session):
    f = FLAGS_DIR / f"{session}.md"
    return f.read_text() if f.exists() else ""


def fresh_session():
    s = "test-" + uuid.uuid4().hex[:8]
    return s


def cleanup(session):
    (FLAGS_DIR / f"{session}.md").unlink(missing_ok=True)
    for p in Path("/tmp").glob(f"autoflag_*{session}*"):
        p.unlink(missing_ok=True)
    for p in Path("/tmp").glob(f"autoflag_scanpos_{session}.json"):
        p.unlink(missing_ok=True)


tmp = Path(tempfile.mkdtemp(prefix="autoflag-test-"))

# --- T1: basic admitted-error fires from the FINAL block (no race simulated) ---
s = fresh_session()
t = tmp / "t1.jsonl"
write_transcript(t, [user_line("do the thing"),
                     asst_line("Working on it."),
                     tool_result_line(),
                     asst_line("Done. I was wrong about the cache key earlier.")])
run_hook(t, s)
check("T1 final-block admission flagged", "I was wrong about the cache key" in flags(s))
cleanup(s)

# --- T2: race recovery — block flushed AFTER first Stop is caught by second ---
s = fresh_session()
t = tmp / "t2.jsonl"
lines = [user_line("go"), asst_line("Starting.")]
write_transcript(t, lines)
run_hook(t, s)  # Stop 1: reads 2 lines, persists offset=2
lines.append(asst_line("Actually my mistake — the config was never loaded."))
lines.append(user_line("next task"))
lines.append(asst_line("On it."))
write_transcript(t, lines)
run_hook(t, s)  # Stop 2: scans from offset — must include the late-flushed block
check("T2 late-flushed block caught at next Stop", "my mistake" in flags(s).lower())
cleanup(s)

# --- T3: mid-turn admission (before a tool result) is reachable ---
s = fresh_session()
t = tmp / "t3.jsonl"
write_transcript(t, [user_line("fix it"),
                     asst_line("Hmm, I didn't verify the schema before shipping — fixing now."),
                     tool_result_line(),
                     asst_line("All tests pass.")])
run_hook(t, s)
check("T3 mid-turn admission flagged", "verify the schema" in flags(s))
cleanup(s)

# --- T4: fallback boundary = current turn only (no state, prior turns ignored) ---
s = fresh_session()
t = tmp / "t4.jsonl"
write_transcript(t, [user_line("old task"),
                     asst_line("I was wrong about the old thing."),  # PRIOR turn
                     user_line("new task"),
                     asst_line("Doing the new thing now.")])
run_hook(t, s)  # first Stop ever for this session: current turn only
check("T4 prior-turn admission NOT flagged on first Stop", "old thing" not in flags(s))
cleanup(s)

# --- T5: code spans don't trip the matcher; apostrophe prose does ---
s = fresh_session()
t = tmp / "t5.jsonl"
code = "Run this:\n```python\nraise ValueError('I was wrong')\n# I didn't check\n```\nAll good."
write_transcript(t, [user_line("go"), asst_line(code)])
run_hook(t, s)
check("T5a fenced admission-lookalike NOT flagged", flags(s) == "")
cleanup(s)

s = fresh_session()
t = tmp / "t5b.jsonl"
write_transcript(t, [user_line("go"),
                     asst_line("You're right — I didn't check the return value, that's on me.")])
run_hook(t, s)
check("T5b contraction-heavy admission flagged", "I didn't check the return value" in flags(s))
cleanup(s)

s = fresh_session()
t = tmp / "t5c.jsonl"
write_transcript(t, [user_line("go"),
                     asst_line("The test asserts `I was wrong` appears in the log output.")])
run_hook(t, s)
check("T5c inline-backtick lookalike NOT flagged", flags(s) == "")
cleanup(s)

# --- T6: reported sentence comes from ORIGINAL text (not mutilated) ---
s = fresh_session()
t = tmp / "t6.jsonl"
write_transcript(t, [user_line("go"),
                     asst_line("I was wrong — `get_user()` never returns None here.")])
run_hook(t, s)
check("T6 report keeps original inline code", "`get_user()`" in flags(s), flags(s))
cleanup(s)

# --- T7: dedup — same snippet across two Stops flags once ---
s = fresh_session()
t = tmp / "t7.jsonl"
lines = [user_line("go"), asst_line("I was mistaken about the port number.")]
write_transcript(t, lines)
run_hook(t, s)
# simulate state loss → rescan same turn via fallback
Path(f"/tmp/autoflag_scanpos_{s}.json").unlink(missing_ok=True)
run_hook(t, s)
check("T7 re-scan does not double-flag", flags(s).count("port number") == 1)
cleanup(s)

# --- T8: multiple distinct admissions in one window → multiple flags, capped ---
s = fresh_session()
t = tmp / "t8.jsonl"
write_transcript(t, [user_line("go"),
                     asst_line("First: I was wrong about A. Second: I didn't verify B. "
                               "Third: my mistake on C. Fourth: I was mistaken about D.")])
run_hook(t, s)
n = flags(s).count("## [")
check("T8 multiple admissions flagged, capped at 3", n == 3, f"got {n}")
cleanup(s)

# --- T9: unclosed trailing fence is still blanked ---
s = fresh_session()
t = tmp / "t9.jsonl"
write_transcript(t, [user_line("go"),
                     asst_line("Here's the log:\n```\nERROR: I was wrong\nmore output")])
run_hook(t, s)
check("T9 unclosed fence NOT flagged", flags(s) == "")
cleanup(s)

# --- T10: debug log written with fields ---
s = fresh_session()
t = tmp / "t10.jsonl"
before = LOG_FILE.read_text().count("\n") if LOG_FILE.exists() else 0
write_transcript(t, [user_line("go"), asst_line("Nothing notable here.")])
run_hook(t, s)
log_lines = LOG_FILE.read_text().strip().splitlines() if LOG_FILE.exists() else []
last = json.loads(log_lines[-1]) if log_lines else {}
check("T10 debug line written", len(log_lines) == before + 1 and last.get("session") == s,
      json.dumps(last))
check("T10b debug has window fields", "chars" in last and "boundary" in last and "ms" in last,
      json.dumps(last))
cleanup(s)

# --- T11: stop_hook_active skips AND does not advance offset ---
s = fresh_session()
t = tmp / "t11.jsonl"
write_transcript(t, [user_line("go"), asst_line("I was wrong about E.")])
env = dict(os.environ, CLAUDE_CODE_SESSION_ID=s, AUTOFLAG_DEBUG="1")
payload = json.dumps({"transcript_path": str(t), "session_id": s,
                      "stop_hook_active": True})
subprocess.run([sys.executable, str(TOOLS / "autoflag.py")], input=payload,
               capture_output=True, text=True, env=env)
check("T11a active-stop produces no flag", flags(s) == "")
check("T11b active-stop leaves no scan state",
      not Path(f"/tmp/autoflag_scanpos_{s}.json").exists())
run_hook(t, s)
check("T11c following real Stop catches it", "about E" in flags(s))
cleanup(s)

# --- T12: score_text budget returns fast on huge input ---
sys.path.insert(0, str(TOOLS))
import time as _time
import flag_corpus
big = ("This sentence is ordinary filler content about deploying services. " * 800)
t0 = _time.monotonic()
flag_corpus.score_text(big, budget_ms=150)
elapsed = (_time.monotonic() - t0) * 1000
check("T12 budget bounds score_text", elapsed < 400, f"{elapsed:.0f}ms")

# --- T13: mutilation guard — sentence that is mostly code doesn't lexically fire ---
# (fragment survives stripping; without guard its shrunken union inflates scores)
mostly_code = "wrong `x = compute_the_thing(a, b, c, d, e, f)` said"
stripped = None
import importlib
autoflag = importlib.import_module("autoflag")
g = autoflag.guard_mutilated(mostly_code, autoflag.strip_code_spans(mostly_code))
check("T13 mutilation guard blanks mostly-code sentence",
      "wrong" not in g and "said" not in g, repr(g))

# --- T14: cross-layer dedup for non-period-terminated admissions ---
s = fresh_session()
t = tmp / "t14.jsonl"
write_transcript(t, [user_line("go"),
                     asst_line("I was wrong!\nLet me fix that now.")])
run_hook(t, s)
n = flags(s).count("## [")
check("T14 one moment -> one flag across layers", n == 1, f"got {n}:\n{flags(s)}")
cleanup(s)

# --- T15: cap cut inside a fence must not blank trailing prose ---
s = fresh_session()
t = tmp / "t15.jsonl"
big_code = "```\n" + ("x = 1\n" * 4000) + "```\n"  # ~24k chars, cap cuts inside it
write_transcript(t, [user_line("go"),
                     asst_line(big_code + "Separately, I was wrong about the API shape.")])
run_hook(t, s)
check("T15 admission after cap-cut fence flagged", "API shape" in flags(s))
cleanup(s)

# --- T16: regex floor fires on admission naming code in backticks ---
s = fresh_session()
t = tmp / "t16.jsonl"
write_transcript(t, [user_line("go"),
                     asst_line("I didn't check `get_user_session_token_from_cache(a, b, c)` before claiming it worked.")])
run_hook(t, s)
check("T16 backticked-identifier admission flagged", "before claiming it worked" in flags(s),
      flags(s))
cleanup(s)

# --- T17: torn tail line — offset must NOT advance past it ---
s = fresh_session()
t = tmp / "t17.jsonl"
write_transcript(t, [user_line("go"), asst_line("Starting.")])
with open(t, "a") as fh:
    fh.write('{"type":"assistant","message":{"role":"assistant","content":[{"type":"te')  # torn, no \n
run_hook(t, s)  # Stop 1: must not count the torn line
# harness completes the line
full = json.dumps(asst_line("Now complete: I was wrong about the flush race."))
content = t.read_text()
t.write_text(content[:content.rfind("\n") + 1] + full + "\n")
run_hook(t, s)  # Stop 2: completed line must be scanned
check("T17 completed torn line caught at next Stop", "flush race" in flags(s), flags(s))
cleanup(s)

# --- T18: transcript with no real user prompt -> scan nothing on fallback ---
s = fresh_session()
t = tmp / "t18.jsonl"
write_transcript(t, [tool_result_line(),
                     asst_line("I was wrong about the ancient thing."),
                     tool_result_line()])
run_hook(t, s)
check("T18 promptless fallback flags nothing", flags(s) == "")
cleanup(s)

# --- T19: same-path rewrite with >= offset lines but different content ---
s = fresh_session()
t = tmp / "t19.jsonl"
write_transcript(t, [user_line("go"), asst_line("First body.")])
run_hook(t, s)  # offset=2 with tail hash of line 2
# rewrite: same path, 3 lines, entirely different content (fingerprint mismatch)
write_transcript(t, [user_line("other"), asst_line("Different."), asst_line("Also different, I was wrong about X.")])
run_hook(t, s)
# fingerprint mismatch -> fallback current turn (after "other") -> admission IS in current turn, flagged
check("T19 rewrite detected via fingerprint, current turn scanned",
      "wrong about X" in flags(s), flags(s))
cleanup(s)

# --- T21: marker-deduped no-ops must not starve a new admission of a cap slot ---
s = fresh_session()
t = tmp / "t21.jsonl"
lines = [user_line("go"),
         asst_line("A: I was wrong about A. B: I didn't verify B. C: my mistake on C.")]
write_transcript(t, lines)
run_hook(t, s)  # 3 flags written, cap consumed by real writes
Path(f"/tmp/autoflag_scanpos_{s}.json").unlink()  # force fallback rescan
lines[1] = asst_line("A: I was wrong about A. B: I didn't verify B. C: my mistake on C. "
                     "D: I was mistaken about D-new.")
write_transcript(t, lines)
run_hook(t, s)  # rescan: A,B,C are deduped no-ops; D must still get a slot
check("T21 new admission survives rescan of flagged ones", "D-new" in flags(s), flags(s))
cleanup(s)

# --- T20: budget_ms=0 means no time, not unbounded ---
import flag_corpus as fc
t0 = _time.monotonic()
r = fc.score_text("You're right, I was wrong. " * 400, budget_ms=0)
e0 = (_time.monotonic() - t0) * 1000
check("T20 budget_ms=0 returns immediately", e0 < 50 and r is None, f"{e0:.0f}ms {r}")

shutil.rmtree(tmp)
print()
print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
