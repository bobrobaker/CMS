#!/usr/bin/env python3
"""Behavioral tests for the recency-aware hook state-log scan (hook_error_scan.py).

Plain-script style (no pytest, matching test_lint_mirror.py): collect failures, print
them, exit 1 on any. Run by the pre-commit hook.

These assert the AGE CLASSIFICATION, which is the whole of the module's judgment —
the line-matching is a coarse net by design and is not what can silently go wrong.
The case that earns most of this file is the trailing-tail one: a scanner that dates
an undated line from the nearest *earlier* timestamp passes every other test here and
still reports a totally dead engine as healthy, because a dead writer stops laying
down the timestamps such a scheme depends on. That case is guarded explicitly and
should be the last thing anyone deletes.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_error_scan as hes

failures = []


def check(label, cond):
    if not cond:
        failures.append(label)


NOW = datetime(2026, 7, 29, 12, 0, 0)
OLD = "2026-06-01T09:00:00"      # well outside any sane window
FRESH = "2026-07-29T08:00:00"    # four hours before NOW

TRACEBACK = [
    "Traceback (most recent call last):",
    '  File "/home/u/.local/bin/monition", line 5, in <module>',
    "    from monition.cli import main",
    "IndentationError: unindent does not match any outer indentation level",
]

ROUTINE = "[cascade] suppressed 12 of 140 candidate(s): t118@0.0030"
TAGGED = "[fire-batch-error] falling back to per-hit fire: query failed"


def cl(lines, fallback=None, window=7):
    return hes.classify(lines, fallback or (NOW - timedelta(days=365)), NOW, window)


# --- the kill case: a dead writer stops timestamping ---------------------------
# The engine died at import after a period of health. No dated line follows the
# crash, so the only honest bound is the file's mtime. Dating these from the last
# healthy line above them would age an ONGOING outage out of the window.

r = cl([f"{OLD} {ROUTINE}"] + TRACEBACK, fallback=NOW)
check("trailing traceback after an old dated line counts as recent", r["recent"] == 1)
check("trailing traceback is classed a crash", r["crashes_recent"] == 1)
check("trailing traceback is not filed as history", r["historical"] == 0)

# Same shape, but the process really did stop failing a month ago: mtime is old too.
r = cl([f"{OLD} {ROUTINE}"] + TRACEBACK, fallback=NOW - timedelta(days=30))
check("trailing traceback with an old mtime is historical", r["historical"] == 1)
check("trailing traceback with an old mtime does not alarm", r["recent"] == 0)


# --- a file the timestamped writer has never touched ---------------------------
# The hook wiring's `2>>` redirect creates the log on its own, so a never-working
# install produces errors with no dated line anywhere. That is an alarm, not a
# legacy prefix to be waved through.

r = cl(TRACEBACK)
check("no dated line at all is its own undatable state", r["undatable"] == 1)
check("undatable does not leak into recent", r["recent"] == 0)
check("undatable does not leak into legacy", r["legacy"] == 0)
code, msg = hes.summarize(
    {**r, "present": True, "bytes": 10}, 7, "/x/hook-errors.log")
check("undatable exits non-zero", code == 1)
check("undatable message names both causes, not just the scarier one",
      "dead at import" in msg and "predates timestamped logging" in msg)

# A file with no dated lines and no errors is simply quiet, not undatable.
r = cl(["[boilerplate] skipped harness-generated prompt"])
check("undated but error-free file is not undatable", r["undatable"] == 0)


# --- legacy: undated lines that predate the timestamped writer ------------------
# These sit before the first dated line, so they were written when nothing was being
# dated. Their age is unknowable, but anything still happening re-appears below.

r = cl(TRACEBACK + [f"{FRESH} {ROUTINE}"])
check("undated run before the first dated line is legacy", r["legacy"] == 1)
check("legacy does not alarm", r["recent"] == 0)
check("legacy is not counted as undatable", r["undatable"] == 0)
code, _ = hes.summarize({**r, "present": True, "bytes": 10}, 7, "/x")
check("a legacy-only log passes", code == 0)


# --- bracketing forward, mid-file ----------------------------------------------
# An undated run between two dated lines takes the age of the line that FOLLOWS it.

r = cl([f"{OLD} {ROUTINE}"] + TRACEBACK + [f"{FRESH} {ROUTINE}"], fallback=NOW)
check("mid-file traceback takes the following timestamp", r["recent"] == 1)

r = cl([f"{OLD} {ROUTINE}"] + TRACEBACK + [f"{OLD} {ROUTINE}"], fallback=NOW)
check("mid-file traceback bracketed by old lines is historical", r["historical"] == 1)
check("mid-file traceback bracketed by old lines does not alarm", r["recent"] == 0)


# --- events, not lines ----------------------------------------------------------

r = cl([f"{OLD} {ROUTINE}"] + TRACEBACK, fallback=NOW)
check("a four-line traceback is one event", r["recent"] == 1)

r = cl([f"{OLD} {ROUTINE}"] + TRACEBACK + TRACEBACK, fallback=NOW)
check("two consecutive tracebacks are two events", r["recent"] == 2)

# One undated run can hold a traceback AND unrelated tagged errors. Counting only
# traceback headers dropped 27 of 30 events in the real log this was built against.
r = cl([f"{OLD} {ROUTINE}"] + [TAGGED, TAGGED] + TRACEBACK + [TAGGED], fallback=NOW)
check("tagged errors sharing a run with a traceback are still counted",
      r["recent"] == 4)
check("only the traceback in a mixed run counts as a crash", r["crashes_recent"] == 1)

# The block consumer must stop at the exception line, not eat the whole run.
r = cl(TRACEBACK + [TAGGED] + [f"{FRESH} {ROUTINE}"])
check("a traceback does not swallow the line after it", r["legacy"] == 2)


# --- dated error lines ----------------------------------------------------------

r = cl([f"{FRESH} {TAGGED}"])
check("a fresh tagged error is recent", r["recent"] == 1)
check("a tagged error is not classed a crash", r["crashes_recent"] == 0)
_, msg = hes.summarize({**r, "present": True, "bytes": 10}, 7, "/x")
check("a handled-only alarm says so", "handled degradation" in msg)

r = cl([f"{OLD} {TAGGED}"])
check("an old tagged error is historical", r["historical"] == 1)
code, _ = hes.summarize({**r, "present": True, "bytes": 10}, 7, "/x")
check("a history-only log passes", code == 0)

# The timestamp prefix must never itself read as an error.
r = cl([f"{FRESH} {ROUTINE}", f"{FRESH} [breadth] cut 5 of 128 head-survivor(s)"])
check("routine dated lines produce no events", r["recent"] == 0 and r["historical"] == 0)

# The window is a real dial, not a decoration.
r = cl([f"2026-07-20T09:00:00 {TAGGED}"], window=7)
check("an event outside the window is historical", r["historical"] == 1)
r = cl([f"2026-07-20T09:00:00 {TAGGED}"], window=30)
check("the same event inside a wider window is recent", r["recent"] == 1)


# --- end-to-end over real files -------------------------------------------------

with tempfile.TemporaryDirectory() as d:
    log = os.path.join(d, "hook-errors.log")

    t = hes.scan(log, NOW)
    check("an absent log is not present", not t["present"])
    code, msg = hes.summarize(t, 7, log)
    check("an absent log passes", code == 0 and "absent" in msg)

    with open(log, "w") as f:
        f.write(f"{FRESH} {ROUTINE}\n")
    t = hes.scan(log, NOW)
    code, _ = hes.summarize(t, 7, log)
    check("a healthy log passes", code == 0 and t["recent"] == 0)

    # Rotation is a rename, so a process holding the old descriptor can still append
    # a fresh failure to a file whose name says it is history.
    with open(log + ".1", "w") as f:
        f.write(f"{FRESH} {TAGGED}\n")
    t = hes.scan(log, NOW)
    check("the rotated generation is scanned", t["recent"] == 1)

    # Hand-made archives are deliberate history and must not re-alarm.
    with open(log + ".pre-cleanup-2026-07-02", "w") as f:
        f.write(f"{FRESH} {TAGGED}\n")
    t = hes.scan(log, NOW)
    check("hand-made archives are ignored", t["recent"] == 1)

    # An unreadable log must fail loud, not quietly pass. Both paths diagnose on
    # stderr by design; swallow it here so a passing run stays silent.
    bad = os.path.join(d, "sub")
    os.mkdir(bad)
    with open(os.devnull, "w") as devnull:
        real_stderr, sys.stderr = sys.stderr, devnull
        try:
            unreadable = hes.main(["--log", bad])
            bad_window = hes.main(["--log", log, "--window-days", "0"])
        finally:
            sys.stderr = real_stderr
    check("a log that cannot be read exits 2", unreadable == 2)
    check("a nonsense window exits 2", bad_window == 2)


if failures:
    print("FAIL (%d):" % len(failures))
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("ok")
