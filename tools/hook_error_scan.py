#!/usr/bin/env python3
"""Recency-aware health read of the hooks' state log.

The hooks fail open: rather than break a session, they swallow the error and append
it to a per-machine state log. That log is the only evidence a hook ever failed, so a
deploy-time doctor check reads it — but the log is append-only and holds far more
routine accounting than failure, so "does this file contain an error" is the wrong
question. It stays true forever once anything has gone wrong even once, which turns
the check into a permanent false alarm and trains the operator to dismiss it.

The question worth asking is "is a hook failing *now*", and answering it needs a
notion of when each line was written. Two writers append here and only one can date
its own output:

  * the takeaway engine's own structured lines are timestamped at the source;
  * raw interpreter stderr arrives via the hook wiring's `2>>` redirect, so an
    import-time traceback is written before any of its code runs and can never carry
    a prefix.

Undated lines are therefore dated by *bracketing*: the log is one chronological
stream, so an undated line is no older than the nearest dated line that FOLLOWS it.
Bracketing forward rather than backward is the load-bearing choice. A backward
bracket looks equivalent and is not: when the engine dies at import, it stops writing
dated lines entirely, so every later traceback would inherit the last healthy
timestamp and a total, ongoing outage would age out of the window and report healthy.
That is precisely the failure this check exists to catch, so the bound has to lean
toward alarm. Where no dated line follows, the file's mtime stands in — polluted by
routine appends in general, but in the only case it is consulted the tail of the file
*is* the failure, so it is accurate exactly when it is used.

Two states fall out of that and both matter:

  * lines preceding the first dated line predate the timestamped writer, so their age
    is unknowable and unknowable-but-superseded: they are legacy, reported and not
    alarmed;
  * a file holding error-like lines and NO dated line at all means the structured
    writer has never run. That is not a legacy prefix, it is an alarm in its own
    right — the shell redirect creates this file on its own, so this is what a
    never-successfully-installed engine looks like.

Deliberately stdlib-only and importing nothing from the engine it reports on: the
loudest failure in scope is that package being dead at import, and a checker that
cannot run when its subject is broken does not check anything.

Exit codes: 0 healthy, 1 needs attention, 2 the scan itself failed. stdout carries a
one-line summary for the caller to surface verbatim.
"""
import argparse
import os
import re
import sys
from datetime import datetime, timedelta

# The writer's contract: local-time ISO-8601, one space, then the message.
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) ")
TS_FMT = "%Y-%m-%dT%H:%M:%S"

# Error-shaped lines. Deliberately the same coarse net the check has always used: the
# state log carries arbitrary third-party stderr, so anything narrower would miss
# failure shapes nobody has seen yet.
ERR_RE = re.compile(r"Traceback \(most recent call last\)|[Ee]xception|[Ee]rror")
TB_RE = re.compile(r"^\s*Traceback \(most recent call last\)")

DEFAULT_WINDOW_DAYS = 7

# Only the live log and the writer's single rotated generation. Hand-made archives
# (`.pre-cleanup-*` and friends) are deliberate history and must not re-alarm.
ROTATED_SUFFIX = ".1"

RECENT, HISTORICAL, LEGACY = "recent", "historical", "legacy"

# A raw traceback means a process died; a tagged line means a handled degradation the
# code caught and worked around. Both deserve the log, not the same alarm wording.
CRASH, HANDLED = "crash", "handled"


class Event:
    """One failure occurrence — not one line. A traceback spans several lines and is
    a single event; counting lines inflates the number a human reads."""

    def __init__(self, kind, when, age_class):
        self.kind = kind
        self.when = when
        self.age_class = age_class


def _parse_ts(raw):
    try:
        return datetime.strptime(raw, TS_FMT)
    except ValueError:
        return None


def _events_in_undated_run(run):
    """The distinct failures an undated run holds, as a list of kinds.

    A traceback block is header + indented frames + the final `SomeError:` line; every
    one of those matches the error net, so counting matches would report one crash as
    three. Consume each block whole, and count anything else error-shaped on its own —
    one run can hold both, and an early version that stopped at the traceback count
    silently dropped 27 of the 30 events in a real log."""
    events = []
    i, n = 0, len(run)
    while i < n:
        if TB_RE.match(run[i]):
            i += 1
            # Frames are indented; the first line back at column 0 is the exception
            # line that closes the block.
            while i < n and (not run[i].strip() or run[i][:1].isspace()):
                i += 1
            if i < n:
                i += 1
            events.append(CRASH)
            continue
        if ERR_RE.search(run[i]):
            events.append(HANDLED)
        i += 1
    return events


def classify(lines, fallback, now, window_days=DEFAULT_WINDOW_DAYS):
    """Pure classifier — the whole of this module's judgment, kept free of I/O so the
    tests can drive the cases that define correctness directly.

    `fallback` dates undated lines with no dated line after them (in practice the
    file's mtime). Returns a dict; `undatable` is the standalone alarm for a file that
    holds failures but has never been written to by the timestamped writer."""
    cutoff = now - timedelta(days=window_days)
    has_dated = any(TS_RE.match(line) for line in lines)
    events = []

    i, n = 0, len(lines)
    while i < n:
        m = TS_RE.match(lines[i])
        if m:
            if ERR_RE.search(lines[i]):
                when = _parse_ts(m.group(1)) or fallback
                events.append(Event(HANDLED, when, None))
            i += 1
            continue

        # A maximal run of undated lines: raw stderr, bracketed as a unit.
        j = i
        while j < n and not TS_RE.match(lines[j]):
            j += 1
        kinds = _events_in_undated_run(lines[i:j])

        if not has_dated:
            # No dated line anywhere: the structured writer has never run here.
            # Ageing these against anything would invent a precision we lack.
            events.extend(Event(k, None, None) for k in kinds)
        elif i == 0:
            # The only undated run that can precede the first dated line, so by
            # construction these were written before the writer was timestamping.
            events.extend(Event(k, None, LEGACY) for k in kinds)
        else:
            when = _parse_ts(TS_RE.match(lines[j]).group(1)) if j < n else fallback
            events.extend(Event(k, when or fallback, None) for k in kinds)
        i = j

    if not has_dated:
        return {
            "undatable": len(events),
            "recent": 0, "historical": 0, "legacy": 0,
            "last_recent": None, "crashes_recent": 0, "dated": False,
        }

    for e in events:
        if e.age_class is None:
            e.age_class = RECENT if e.when and e.when >= cutoff else HISTORICAL

    recent = [e for e in events if e.age_class == RECENT]
    return {
        "undatable": 0,
        "recent": len(recent),
        "historical": sum(1 for e in events if e.age_class == HISTORICAL),
        "legacy": sum(1 for e in events if e.age_class == LEGACY),
        "last_recent": max((e.when for e in recent if e.when), default=None),
        "crashes_recent": sum(1 for e in recent if e.kind == CRASH),
        "dated": True,
    }


def _read(path):
    with open(path, "r", errors="replace") as f:
        return f.read().splitlines()


def scan(path, now, window_days=DEFAULT_WINDOW_DAYS):
    """Classify the live log plus the writer's rotated generation, if present. The
    rotated file is scanned because rotation is a rename: a process holding the old
    descriptor keeps appending to it, so a fresh failure can land in a file whose name
    says it is history."""
    totals = {"undatable": 0, "recent": 0, "historical": 0, "legacy": 0,
              "crashes_recent": 0, "last_recent": None, "dated": False,
              "present": False, "bytes": 0}

    for target in (path, path + ROTATED_SUFFIX):
        if not os.path.exists(target):
            continue
        totals["present"] = True
        totals["bytes"] += os.path.getsize(target)
        lines = _read(target)
        if not lines:
            continue
        result = classify(lines, datetime.fromtimestamp(os.path.getmtime(target)),
                          now, window_days)
        for key in ("undatable", "recent", "historical", "legacy", "crashes_recent"):
            totals[key] += result[key]
        totals["dated"] = totals["dated"] or result["dated"]
        if result["last_recent"] and (totals["last_recent"] is None
                                      or result["last_recent"] > totals["last_recent"]):
            totals["last_recent"] = result["last_recent"]
    return totals


def summarize(t, window_days, path):
    """Render the doctor's one-line verdict. Returns (exit_code, message)."""
    if not t["present"]:
        return 0, "absent (no recorded hook failures)"
    if t["undatable"]:
        # Two very different causes, and the check cannot tell them apart from the
        # file alone — so name both rather than assert the scarier one. Either way a
        # single successful structured write clears this state.
        return 1, (f"{t['undatable']} error-like event(s) and no timestamped line at all "
                   f"— either the takeaway engine has never logged successfully here "
                   f"(dead at import), or its writer predates timestamped logging; "
                   f"read {path}")
    if t["recent"]:
        stamp = t["last_recent"].strftime("%Y-%m-%d %H:%M") if t["last_recent"] else "?"
        shape = (f", {t['crashes_recent']} of them a crashed process"
                 if t["crashes_recent"] else " (all handled degradations, not crashes)")
        return 1, (f"{t['recent']} error event(s) in the last {window_days}d, last at "
                   f"{stamp}{shape} — hooks are failing now; read {path}")

    quiet = []
    if t["historical"]:
        quiet.append(f"{t['historical']} older than {window_days}d")
    if t["legacy"]:
        quiet.append(f"{t['legacy']} undated (pre-timestamp)")
    if quiet:
        return 0, (f"no failures in the last {window_days}d "
                   f"({'; '.join(quiet)} — history, not live)")
    return 0, f"present, informational only ({t['bytes']} bytes, no error events)"


def default_log_path():
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state")
    return os.path.join(state, "monition", "hook-errors.log")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", default=None, help="log path (default: the state dir)")
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    args = ap.parse_args(argv)

    path = args.log or default_log_path()
    if args.window_days < 1:
        print("--window-days must be >= 1", file=sys.stderr)
        return 2
    try:
        totals = scan(path, datetime.now(), args.window_days)
    except OSError as e:
        # Fail loud. A health check that goes quiet when it cannot read is the same
        # defect it was written to remove.
        print(f"could not read {path}: {e}", file=sys.stderr)
        return 2
    code, message = summarize(totals, args.window_days, path)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
