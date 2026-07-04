#!/usr/bin/env python3
"""Behavioral tests for tools/eval_canary.py — the machinery-integration eval canary.

Guards the pure logic the three live tasks rest on: doctor-summary parsing, the
declarative craft-reminder wiring check (the half that CATCHES an unwired hook —
the phase's exit criterion), and the twice-consecutive debounce (one flake is
swallowed, two in a row alert, any pass resets the streak). The live tasks
(bootstrap / craft_reminder / mine_routing) are exercised by running the harness
itself — `python3 tools/eval_canary.py` — not here, to keep this guard fast and
dependency-free. Plain script: exit 0 on pass, 1 on failure. Run by
.githooks/pre-commit."""
import contextlib
import io
import json
import os
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import eval_canary as ec


def _r(name, status):
    return ec.Result(name, status, "")


def test_parse_doctor():
    out = (
        "CMS deploy doctor — /x\n\n"
        "  PASS  python3          3.11.0\n"
        "  PASS  githooks         core.hooksPath=.githooks\n"
        "  WARN  hub-env          no hub configured — standalone\n"
        "  PASS  store            per-repo: /x/monition ('monition list' OK)\n"
        "\n  11 pass · 4 warn · 0 fail\n"
    )
    p = ec.parse_doctor(out)
    assert p["counts"] == {"pass": 11, "warn": 4, "fail": 0}, p["counts"]
    assert "githooks" in p["passing"]
    assert "store" in p["passing"]
    assert "hub-env" not in p["passing"]  # WARN, not PASS


def test_parse_doctor_with_fails():
    out = "  FAIL  store            no working store\n\n  9 pass · 2 warn · 1 fail\n"
    p = ec.parse_doctor(out)
    assert p["counts"]["fail"] == 1, p
    assert "store" not in p["passing"]


def test_parse_doctor_unparseable():
    p = ec.parse_doctor("garbage with no summary line")
    assert p["counts"]["fail"] is None  # task treats None as a failure


def test_craft_reminder_wired_true():
    cfg = {"hooks": {"PreToolUse": [
        {"matcher": "Write|Edit", "hooks": [
            {"type": "command", "command": "monition fire-hook"},
            {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/craft_reminder.py\""},
        ]},
    ]}}
    assert ec.craft_reminder_wired(cfg) is True


def test_craft_reminder_unwired_is_caught():
    # The exit-criterion case: a deliberately-broken wiring (craft_reminder removed
    # from the PreToolUse hook) must be caught.
    cfg = {"hooks": {"PreToolUse": [
        {"matcher": "Write|Edit", "hooks": [
            {"type": "command", "command": "monition fire-hook"},
        ]},
    ]}}
    assert ec.craft_reminder_wired(cfg) is False
    # Also caught: the hook present but the matcher no longer covers edits.
    cfg2 = {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [
            {"type": "command", "command": "python3 tools/craft_reminder.py"},
        ]},
    ]}}
    assert ec.craft_reminder_wired(cfg2) is False
    # Empty / missing hooks block.
    assert ec.craft_reminder_wired({}) is False
    assert ec.craft_reminder_wired({"hooks": {}}) is False


def test_debounce_single_failure_no_alert():
    state, alerts = ec.debounce({}, [_r("bootstrap", ec.FAIL)])
    assert state["bootstrap"] == 1
    assert alerts == []  # first failure is swallowed


def test_debounce_two_consecutive_alerts():
    state, alerts = ec.debounce({"bootstrap": 1}, [_r("bootstrap", ec.FAIL)])
    assert state["bootstrap"] == 2
    assert alerts == ["bootstrap"]


def test_debounce_pass_resets_streak():
    state, alerts = ec.debounce({"bootstrap": 1}, [_r("bootstrap", ec.PASS)])
    assert state["bootstrap"] == 0
    assert alerts == []


def test_debounce_skip_resets_streak():
    state, alerts = ec.debounce({"mine_routing": 1}, [_r("mine_routing", ec.SKIP)])
    assert state["mine_routing"] == 0
    assert alerts == []


def test_debounce_mixed_batch():
    prev = {"bootstrap": 1, "craft_reminder": 0}
    results = [_r("bootstrap", ec.FAIL), _r("craft_reminder", ec.FAIL), _r("mine_routing", ec.PASS)]
    state, alerts = ec.debounce(prev, results)
    assert state["bootstrap"] == 2 and "bootstrap" in alerts       # 2nd in a row → alert
    assert state["craft_reminder"] == 1 and "craft_reminder" not in alerts  # 1st → debounced
    assert state["mine_routing"] == 0


def test_is_due():
    now = 1_000_000.0
    assert ec.is_due(None, 7, now) is True           # never run → due
    assert ec.is_due(now - 8 * 86400, 7, now) is True  # 8d ago, weekly → due
    assert ec.is_due(now - 3 * 86400, 7, now) is False  # 3d ago → not due
    assert ec.is_due(now - 7 * 86400, 7, now) is True   # exactly 7d → due (>=)


def test_if_due_silent_noop_when_not_due():
    # The cadence-gate contract housekeep relies on: when a run happened recently,
    # `--if-due` produces NO output and exits 0 — so housekeep surfaces nothing.
    with tempfile.TemporaryDirectory() as d:
        state = os.path.join(d, "state.json")
        with open(state, "w") as fh:
            json.dump({"streaks": {}, "last_run": 10 ** 12}, fh)  # far-future last_run
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ec.main(["--if-due", "7", "--state", state, "--only", "craft_reminder"])
        assert rc == 0
        assert buf.getvalue() == "", "expected silent no-op, got: {!r}".format(buf.getvalue())


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print("FAIL {}: {}".format(t.__name__, e))
        except Exception as e:  # noqa: BLE001 — surface any unexpected error as a failure
            failed += 1
            print("ERROR {}: {}: {}".format(t.__name__, type(e).__name__, e))
    if failed:
        print("\n{} of {} tests failed".format(failed, len(tests)))
        return 1
    print("all {} eval_canary tests passed".format(len(tests)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
