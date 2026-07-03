#!/usr/bin/env python3
"""Behavioral tests for tools/session_tokens.py — the SessionEnd token-counting hook.

Guards the load-bearing properties: usage summing tolerates malformed/unknown
transcript records without crashing, subagent transcripts are folded into the
session total, the marker-line insert is idempotent (a duplicate hook firing is a
no-op — the double-fire dedup guarantee), --print reports live counts without
writing, and the hook fails gracefully (never a traceback) on a missing, empty,
or too-short transcript. Plain script: exit 0 on pass, 1 on failure. Run by
.githooks/pre-commit."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(TOOLS, "session_tokens.py")
sys.path.insert(0, TOOLS)
import session_tokens as st

# Redirect the module's fixed diagnostic-log path for the lifetime of this test
# process — several behaviors under test (malformed lines, schema oddities)
# intentionally call log_diagnostic(), which otherwise writes into the real
# ~/.claude/logs/session-tokens.log. In-process calls below share this module
# object; subprocess calls get the same redirect via HOME below.
_DIAG_DIR = tempfile.mkdtemp(prefix="session-tokens-test-diag-")
st.DIAGNOSTIC_LOG_PATH = Path(_DIAG_DIR) / "session-tokens.log"

failures = []


def check(label, cond):
    if not cond:
        failures.append(label)


def usage_record(input_tokens=0, output_tokens=0, cache_write=0, cache_read=0, extra=None):
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_write,
        "cache_read_input_tokens": cache_read,
    }
    if extra:
        usage.update(extra)
    return {"type": "assistant", "message": {"usage": usage}}


def user_record(text="hello"):
    return {"type": "user", "message": {"content": text}}


def write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def run_script(args, stdin=None, home=None, cwd=None):
    """Run session_tokens.py as a subprocess with an isolated HOME.

    HOME is always overridden (to a fresh temp dir when the caller doesn't need
    a specific one) so a subprocess run never touches the real
    ~/.claude/logs/session-tokens.log diagnostic file or ~/.claude/projects/.
    """
    env = dict(os.environ)
    env["HOME"] = home or tempfile.mkdtemp(prefix="session-tokens-test-home-")
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        input=stdin, capture_output=True, text=True, env=env, cwd=cwd,
    )


def test_formatted_count():
    check("plain count", st.formatted_count(873) == "873")
    check("k-scale one decimal", st.formatted_count(51049) == "51.0k")
    check("M-scale one decimal", st.formatted_count(10703404) == "10.7M")
    check("M-scale no decimal above 100", st.formatted_count(150_000_000) == "150M")


def test_summed_usage_well_formed():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        write_jsonl(path, [
            usage_record(100, 50, 10, 5),
            usage_record(200, 25, 0, 15),
            user_record(),
        ])
        totals = st.summed_usage([path])
        check("input summed", totals.input_tokens == 300)
        check("output summed", totals.output_tokens == 75)
        check("cache-write summed", totals.cache_creation_input_tokens == 10)
        check("cache-read summed", totals.cache_read_input_tokens == 20)


def test_summed_usage_malformed_and_unknown():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        lines = [
            json.dumps(usage_record(100, 10, 0, 0)),
            "{not valid json",                       # malformed line
            "42",                                    # valid JSON, not a Mapping
            json.dumps({"type": "assistant"}),       # no message
            json.dumps({"type": "assistant", "message": {}}),  # no usage
            json.dumps(usage_record(50, 5, 0, 0, extra={"unknown_field": 3})),
            json.dumps(usage_record(0, 0, 0, 0, extra={"input_tokens": "oops"})),
        ]
        # the last record clobbers its own input_tokens with a non-int — the
        # dict literal for usage_record already set input_tokens=0 then
        # extra overwrites it to a string, exercising the non-int branch.
        path.write_text("\n".join(lines) + "\n")
        totals = st.summed_usage([path])  # must not raise
        check("well-formed + unexpected-field record both counted",
              totals.input_tokens == 150 and totals.output_tokens == 15)


def test_subagent_transcripts_folded_in():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        main_path = root / "sess.jsonl"
        write_jsonl(main_path, [usage_record(10, 1, 0, 0)])
        sub_dir = root / "sess" / "subagents"
        sub_dir.mkdir(parents=True)
        write_jsonl(sub_dir / "a.jsonl", [usage_record(20, 2, 0, 0)])
        write_jsonl(sub_dir / "b.jsonl", [usage_record(30, 3, 0, 0)])

        paths = st.session_transcript_paths(main_path)
        check("main + both subagent transcripts found", len(paths) == 3)

        totals = st.summed_usage(paths)
        check("subagent usage folded into session total",
              totals.input_tokens == 60 and totals.output_tokens == 6)


def test_marker_line_idempotency():
    marker = st.marker_line("sid-1")

    check("no marker returns None", st.updated_log_text("no marker here\n", "sid-1", "tokens: x") is None)

    log_with_marker = f"## entry\n\n{marker}\n\nsome body\n"
    inserted = st.updated_log_text(log_with_marker, "sid-1", "tokens: input 1")
    check("inserts new_line directly after the marker",
          inserted is not None and inserted.splitlines()[3] == "tokens: input 1")

    # the double-fire guarantee: a tokens line already follows the marker
    log_with_tokens = f"## entry\n\n{marker}\ntokens: input 1\n\nbody\n"
    unchanged = st.updated_log_text(log_with_tokens, "sid-1", "tokens: input 999")
    check("no-op when a tokens line already follows the marker (dedup)",
          unchanged == log_with_tokens)

    # several entries carry the marker (wrap-session ran twice) — last one wins
    log_two_markers = f"{marker}\nold body\n\n{marker}\n"
    inserted2 = st.updated_log_text(log_two_markers, "sid-1", "tokens: input 2")
    lines = inserted2.splitlines()
    last_marker_index = len(lines) - 1 - lines[::-1].index(marker)
    check("last marker occurrence wins", lines[last_marker_index + 1] == "tokens: input 2")


def test_live_transcript_path_prefers_env_session_id():
    with tempfile.TemporaryDirectory() as home_dir:
        old_home = os.environ.get("HOME")
        old_sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
        try:
            os.environ["HOME"] = home_dir
            cwd = Path("/some/project")
            import re
            slug = re.sub(r'[^A-Za-z0-9-]', '-', str(cwd))
            project_dir = Path(home_dir) / ".claude" / "projects" / slug
            project_dir.mkdir(parents=True)
            (project_dir / "old-session.jsonl").write_text("")
            (project_dir / "right-session.jsonl").write_text("")
            os.environ["CLAUDE_CODE_SESSION_ID"] = "right-session"
            found = st.live_transcript_path(cwd)
            check("env session id wins over mtime fallback",
                  found.name == "right-session.jsonl")

            del os.environ["CLAUDE_CODE_SESSION_ID"]
            found_fallback = st.live_transcript_path(cwd)
            check("falls back to newest-mtime when env unset",
                  found_fallback.name in ("old-session.jsonl", "right-session.jsonl"))
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_sid is None:
                os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            else:
                os.environ["CLAUDE_CODE_SESSION_ID"] = old_sid


def test_print_mode_end_to_end():
    with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as project_cwd:
        import re
        slug = re.sub(r'[^A-Za-z0-9-]', '-', str(Path(project_cwd)))
        project_dir = Path(home_dir) / ".claude" / "projects" / slug
        project_dir.mkdir(parents=True)
        session_id = "print-test-session"
        write_jsonl(project_dir / f"{session_id}.jsonl", [usage_record(7, 3, 0, 0)])

        env = dict(os.environ)
        env["HOME"] = home_dir
        env["CLAUDE_CODE_SESSION_ID"] = session_id
        result = subprocess.run(
            [sys.executable, SCRIPT, "--print"],
            capture_output=True, text=True, env=env, cwd=project_cwd,
        )
        out_lines = result.stdout.strip().splitlines()
        check("print mode exits 0", result.returncode == 0)
        check("print mode reports the marker line", out_lines[:1] == [st.marker_line(session_id)])
        check("print mode reports the tokens line",
              len(out_lines) == 2 and out_lines[1].startswith("tokens: input 7"))


def test_main_hook_new_unwrapped_entry():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        transcript = root / "sess.jsonl"
        write_jsonl(transcript, [user_record("do the thing"), user_record("again"), usage_record(5, 1, 0, 0)])
        log_path = root / "sessions.md"
        payload = {"cwd": "/home/x/myproject", "transcript_path": str(transcript), "session_id": "sess"}
        result = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        check("hook mode exits 0 on a well-formed payload", result.returncode == 0)
        check("log file created", log_path.exists())
        text = log_path.read_text() if log_path.exists() else ""
        check("unwrapped entry carries the marker", st.marker_line("sess") in text)
        check("unwrapped entry carries a tokens line", "tokens: input 5" in text)
        check("unwrapped entry titled from the first user message", "do the thing" in text)


def test_main_hook_updates_existing_marker_and_is_idempotent():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        transcript = root / "sess.jsonl"
        write_jsonl(transcript, [user_record("a"), user_record("b"), usage_record(11, 2, 0, 0)])
        log_path = root / "sessions.md"
        log_path.write_text(f"## wrapped entry\n\n{st.marker_line('sess')}\n\nbody\n")
        payload = {"cwd": "/home/x/myproject", "transcript_path": str(transcript), "session_id": "sess"}

        result1 = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        check("first firing exits 0", result1.returncode == 0)
        first_text = log_path.read_text()
        check("tokens line lands right after the existing marker",
              "tokens: input 11" in first_text)

        result2 = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        check("second (duplicate) firing exits 0", result2.returncode == 0)
        second_text = log_path.read_text()
        check("double firing is a no-op (dedup guarantee)", second_text == first_text)


def test_main_hook_skips_short_sessions():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        transcript = root / "sess.jsonl"
        write_jsonl(transcript, [user_record("only one turn")])  # < MIN_USER_TURNS
        log_path = root / "sessions.md"
        payload = {"cwd": "/home/x/myproject", "transcript_path": str(transcript), "session_id": "sess"}
        result = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        check("short session exits 0 (not an error)", result.returncode == 0)
        check("short session writes nothing", not log_path.exists())


def test_main_hook_skips_configured_cwd_fragment():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        log_path = root / "sessions.md"
        # transcript_path deliberately points nowhere — the cwd skip must fire
        # before the (nonexistent) transcript is ever read.
        payload = {
            "cwd": "/tmp/some-worktree",
            "transcript_path": str(root / "does-not-exist.jsonl"),
            "session_id": "sess",
        }
        result = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        check("skip-cwd session exits 0", result.returncode == 0)
        check("skip-cwd session writes nothing", not log_path.exists())


def test_main_hook_missing_transcript_file_is_graceful():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        log_path = root / "sessions.md"
        payload = {
            "cwd": "/home/x/myproject",
            "transcript_path": str(root / "does-not-exist.jsonl"),
            "session_id": "sess",
        }
        result = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        # count_user_turns fails soft (OSError -> 0 turns), so this is treated
        # as a too-short session rather than an error.
        check("missing transcript file exits 0", result.returncode == 0)
        check("missing transcript file writes nothing", not log_path.exists())
        check("no traceback on stderr", "Traceback" not in result.stderr)


def test_main_hook_empty_transcript_file_is_graceful():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        transcript = root / "sess.jsonl"
        transcript.write_text("")
        log_path = root / "sessions.md"
        payload = {"cwd": "/home/x/myproject", "transcript_path": str(transcript), "session_id": "sess"}
        result = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        check("empty transcript exits 0", result.returncode == 0)
        check("empty transcript writes nothing", not log_path.exists())


def test_main_hook_missing_transcript_path_key_fails_gracefully():
    with tempfile.TemporaryDirectory() as d:
        log_path = Path(d) / "sessions.md"
        payload = {"cwd": "/home/x/myproject", "session_id": "sess"}  # no transcript_path
        result = run_script(["--log", str(log_path)], stdin=json.dumps(payload))
        check("missing transcript_path key exits 1", result.returncode == 1)
        check("missing transcript_path key writes nothing", not log_path.exists())
        check("no traceback on stderr", "Traceback" not in result.stderr)


def test_main_hook_malformed_stdin_fails_gracefully():
    with tempfile.TemporaryDirectory() as d:
        log_path = Path(d) / "sessions.md"
        result = run_script(["--log", str(log_path)], stdin="not json{")
        check("malformed stdin exits 1", result.returncode == 1)
        check("malformed stdin writes nothing", not log_path.exists())
        check("no traceback on stderr", "Traceback" not in result.stderr)


def main():
    test_formatted_count()
    test_summed_usage_well_formed()
    test_summed_usage_malformed_and_unknown()
    test_subagent_transcripts_folded_in()
    test_marker_line_idempotency()
    test_live_transcript_path_prefers_env_session_id()
    test_print_mode_end_to_end()
    test_main_hook_new_unwrapped_entry()
    test_main_hook_updates_existing_marker_and_is_idempotent()
    test_main_hook_skips_short_sessions()
    test_main_hook_skips_configured_cwd_fragment()
    test_main_hook_missing_transcript_file_is_graceful()
    test_main_hook_empty_transcript_file_is_graceful()
    test_main_hook_missing_transcript_path_key_fails_gracefully()
    test_main_hook_malformed_stdin_fails_gracefully()

    if failures:
        print("test_session_tokens FAILURES:")
        for f in failures:
            print("  ", f)
        return 1
    print("ok — session_tokens parsing, summing, marker-dedup, --print, and fail-open all hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
