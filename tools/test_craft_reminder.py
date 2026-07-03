#!/usr/bin/env python3
"""Behavioral tests for tools/craft_reminder.py — the tier-2 write-time reminder.

Guards the load-bearing properties (method/write-path.md): most-specific rule wins,
each pointer fires once per session PER POINTER, the fork-local overlay merges by
`key` with local winning, and the hook fails open on malformed input. Plain script:
exit 0 on pass, 1 on failure. Run by .githooks/pre-commit."""
import io
import json
import os
import subprocess
import sys
import uuid

TOOLS = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(TOOLS, "craft_reminder.py")
sys.path.insert(0, TOOLS)
import craft_reminder as cr

failures = []


def check(label, cond):
    if not cond:
        failures.append(label)


def run_hook(payload):
    """Run the hook as the harness would; return parsed additionalContext or None."""
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    out = subprocess.run([sys.executable, HOOK], input=stdin,
                         capture_output=True, text=True).stdout.strip()
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


def main():
    # ── merge_rules: local wins on key collision; result is most-specific-first ──
    merged = cr.merge_rules(
        [{"key": "docs", "path": "docs/", "pointer": "default"}],
        [{"key": "docs", "path": "docs/", "pointer": "local"},
         {"key": "notes", "path": "docs/notes/", "pointer": "notes"}])
    check("local overrides default on same key",
          next(r for r in merged if r["key"] == "docs")["pointer"] == "local")
    check("most-specific path sorts first", merged[0]["key"] == "notes")

    # ── match: specificity and silence ──
    rules = cr.merge_rules(cr.RULES, [])
    check("decisions path hits the decisions rule",
          cr.match("docs/decisions/2026-01-01-x.md", rules)["key"] == "decisions")
    check("plain docs path hits the docs rule",
          cr.match("docs/road.md", rules)["key"] == "docs")
    check("ungoverned path matches nothing", cr.match("src/app.py", rules) is None)

    # ── end-to-end: once per session PER POINTER ──
    sid = "test-" + uuid.uuid4().hex
    first = run_hook({"session_id": sid,
                      "tool_input": {"file_path": "docs/decisions/2026-01-01-x.md"}})
    check("decisions pointer fires on first governed edit", first is not None)
    second = run_hook({"session_id": sid,
                       "tool_input": {"file_path": "docs/decisions/2026-01-01-y.md"}})
    check("same pointer stays silent second time (same session)", second is None)
    other = run_hook({"session_id": sid, "tool_input": {"file_path": "docs/road.md"}})
    check("a DIFFERENT pointer still fires in the same session",
          other is not None and other != first)
    fresh = run_hook({"session_id": "test-" + uuid.uuid4().hex,
                      "tool_input": {"file_path": "docs/decisions/2026-01-01-x.md"}})
    check("new session fires the pointer again", fresh == first)

    # ── the shipped local overlay is picked up (CMS governs method/ via it) ──
    local = run_hook({"session_id": "test-" + uuid.uuid4().hex,
                      "tool_input": {"file_path": "method/write-path.md"}})
    check("fork-local rule (method/) fires end-to-end", local is not None)

    # ── fail open ──
    check("malformed stdin exits silently", run_hook("not json{") is None)
    check("missing tool_input exits silently",
          run_hook({"session_id": "test-" + uuid.uuid4().hex}) is None)

    # ── marker write failure (e.g. an unwritable /tmp) must not crash the hook ──
    # In-process (not subprocess.run) so we can fault-inject: patch the module's
    # `open` global to raise OSError, then call main() directly and assert it still
    # exits cleanly instead of propagating the exception up through the hook.
    real_open = getattr(cr, "open", None)  # not a module attribute until we set one

    def failing_open(*a, **kw):
        raise OSError("simulated unwritable /tmp")

    sid = "test-" + uuid.uuid4().hex
    payload = json.dumps({"session_id": sid,
                          "tool_input": {"file_path": "docs/road.md"}})
    real_stdin, real_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(payload)
    sys.stdout = io.StringIO()
    crashed = False
    printed = None
    try:
        cr.open = failing_open
        cr.main()
        printed = sys.stdout.getvalue().strip()
    except Exception:
        crashed = True
    finally:
        if real_open is None:
            del cr.open
        else:
            cr.open = real_open
        sys.stdin, sys.stdout = real_stdin, real_stdout
    check("marker write failure does not crash main() (fails open)", not crashed)
    check("hook still emits its pointer despite the marker-write failure",
          not crashed and bool(printed))

    if failures:
        print("test_craft_reminder FAILURES:")
        for f in failures:
            print("  ", f)
        return 1
    print("test_craft_reminder OK — rules merge, per-pointer markers, fail-open all hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
