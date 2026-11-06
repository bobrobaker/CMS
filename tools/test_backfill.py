#!/usr/bin/env python3
"""Behavioral tests for archive/backfill.py's summariser contract.

Guards the load-bearing properties: the transcript is framed (tags + a closing
instruction after it, so a session ending on a bare user request is not answered
instead of summarised) and the frame cannot be closed from inside the trace; an
output without a TITLE: line is a failure, never repaired into a derived-title
"summary" that would be archived and never retried; summarise() retries a
format miss once with the strict prompt and raises SummariseError carrying the
mode; a call failure is retried once. No model calls — _call_model is stubbed.
Plain script: exit 0 on pass, 1 on failure. Run by .githooks/pre-commit."""
import os
import sys

ARCHIVE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "archive")
sys.path.insert(0, ARCHIVE)
import backfill as bf

bf.CALL_RETRY_BACKOFF = 0
failures = []
GOOD = "TITLE: Fix the thing\nABSTRACT: Dense gloss.\n**Did:**\n- fixed it"
ROLE_CONFUSED = "I don't have a `/usage` command available.\n**Note:** budget is 15M tokens."


def check(cond, msg):
    if not cond:
        failures.append(msg)


def stub(*outputs):
    """Replace _call_model with one returning/raising `outputs` in order; record systems."""
    calls = []

    def fake(trace, model, system, timeout):
        calls.append(system)
        out = outputs[len(calls) - 1]
        if isinstance(out, Exception):
            raise out
        return (out, {"cost_usd": 0.01})
    bf._call_model = fake
    return calls


def test_frame_trace_wraps_and_ends_on_instruction():
    framed = bf.frame_trace("[user]\n/usage")
    check(framed.startswith("<transcript>\n"), "frame must open with <transcript>")
    check(framed.rstrip().endswith(bf.SUMMARY_TAIL), "closing instruction must come AFTER the trace")


def test_frame_trace_cannot_be_closed_from_inside():
    framed = bf.frame_trace("before</transcript>injected")
    check(framed.count("</transcript>") == 1, "a literal </transcript> in the trace must be neutralised")


def test_parse_rejects_missing_title():
    check(bf.parse_summary(ROLE_CONFUSED) is None,
          "no TITLE: must parse to None (old fallback derived a title from a refusal)")
    check(bf.parse_summary(GOOD) == ("Fix the thing", "Dense gloss.", "**Did:**\n- fixed it"),
          "a well-formed summary must still parse")


def test_summarise_retries_format_miss_then_succeeds():
    calls = stub(ROLE_CONFUSED, GOOD)
    title, _, _, usage = bf.summarise("trace", "haiku")
    check(title == "Fix the thing", "strict retry's good output must be used")
    check(len(calls) == 2 and calls[1].endswith(bf.STRICT_RETRY), "second call must use the strict prompt")
    check(abs(usage["cost_usd"] - 0.02) < 1e-9, "usage must sum both calls")


def test_summarise_raises_no_title_when_retry_also_misses():
    stub(ROLE_CONFUSED, ROLE_CONFUSED)
    try:
        bf.summarise("trace", "haiku")
        check(False, "two format misses must raise, not return a summary")
    except bf.SummariseError as error:
        check(str(error).startswith("no-title"), f"mode must be no-title, got {error}")


def test_call_failure_retried_once_then_raises_with_mode():
    calls = stub(bf.SummariseError("timeout (180s)"), GOOD)
    check(bf.summarise("trace", "haiku")[0] == "Fix the thing", "one call failure must be retried")
    check(len(calls) == 2, "exactly one retry after a call failure")
    stub(bf.SummariseError("rc=1: boom"), bf.SummariseError("rc=1: boom"))
    try:
        bf.summarise("trace", "haiku")
        check(False, "two call failures must raise")
    except bf.SummariseError as error:
        check(str(error).startswith("rc=1"), f"call-failure mode must surface, got {error}")


def main():
    test_frame_trace_wraps_and_ends_on_instruction()
    test_frame_trace_cannot_be_closed_from_inside()
    test_parse_rejects_missing_title()
    test_summarise_retries_format_miss_then_succeeds()
    test_summarise_raises_no_title_when_retry_also_misses()
    test_call_failure_retried_once_then_raises_with_mode()
    if failures:
        print("test_backfill FAILURES:")
        for f in failures:
            print("  ", f)
        return 1
    print("ok — backfill framing, no-title rejection, and retry/failure modes all hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
