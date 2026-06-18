---
name: wrap-session
description: Wrap the current session into the global session archive — a rich, embedding-friendly summary file plus a one-line index entry — so a half-remembered future query ("I remember working on X") can be found by progressive disclosure. Use when the user invokes /wrap-session, says "wrap this session" / "archive this session", or is ending a session worth being able to find again. Summarizes only from context already in the window — never re-reads the transcript. NOT for a decision-ready resume of in-flight work (that's /handoff).
---

# wrap-session

You are leaving a findable trace of THIS session in the global archive
(`~/.claude/logs/`, shared across every project). Governing principle:
**summarize only from what is already in your context window.** The prompt cache
is warm; re-reading the transcript spends tokens to re-derive what you already
hold. Capture what this session was *about*, for a reader who only half-remembers
it later.

Two writes — the rich summary file (rung 2 of the disclosure ladder) and the
one-line index entry in `sessions.md` (rung 1). **Fail open:** if a step's input
is missing, write what you can. An index line with no token counts still beats no
trace.

1. **Marker + provisional counts.** Get the session marker and provisional token
   line from the session-token helper in `--print` mode. Find it at
   `$CLAUDE_PROJECT_DIR/tools/session_tokens.py` and run `python3 <path> --print`. It prints a
   `<!-- session: <id> -->` marker and a `tokens:` line. This session's id is
   `$CLAUDE_CODE_SESSION_ID` (the harness sets it per session) — the source of
   truth, because newest-by-mtime misidentifies the session when another runs in
   the same cwd concurrently. If neither helper path exists there is no SessionEnd
   hook to finalize counts here: take the marker id from `$CLAUDE_CODE_SESSION_ID`
   (only if it is unset, fall back to the newest
   `~/.claude/projects/<cwd-slug>/<id>.jsonl`) and skip the counts.

2. **Write the summary file** to
   `~/.claude/logs/sessions/<YYYY-MM-DD>-<project>-<session-id>.md` (create the
   `sessions/` directory if missing; `<project>` is the cwd basename, spaces and
   slashes collapsed to `-`). Lean, prose-rich, embedding-friendly — a snapshot of
   this session as it ended, not maintained afterward:

   ```
   ---
   date: <YYYY-MM-DD>
   project: <project>
   session: <session-id>
   source: wrap-session
   title: >-
     <one line — what this session was about>
   abstract: >-
     <1–2 sentences of prose — the embed-text a semantic search vectorises:
     what this session was about, named so a half-memory matches it>
   files:
     - <one absolute path per line; omit the whole key if none — see below>
   ---

   **Did:** 2–5 bullets — what was built, changed, decided, or figured out.
   **Decisions:** the load-bearing calls, each with a one-clause why (omit if none).
   **Artifacts:** files, paths, commands, PRs touched (omit if none).
   **Open / next:** unfinished threads, or "none".
   ```

   The folded scalars (`>-`) keep free-text titles/abstracts valid YAML without
   escaping; `source: wrap-session` marks this as an authoritative wrap (vs a
   `source: backfill` stub). Write it from context you still hold. Do not re-read
   the transcript or the files — if a detail has fallen out of context, say so
   rather than re-fetching it. The summary is a point-in-time snapshot; a reader
   treats its claims as true *as of that date*, not now.

   **The `files:` list is the staleness-capture signal** — the files this session
   changed, so a later retrieval can warn that the summary may be stale if they
   have moved since. Unlike the prose, get it *deterministically*, not from
   memory: run the trace extractor in `--files` mode over this session's
   transcript. Find it at `$CLAUDE_PROJECT_DIR/tools/extract_session.py` and run
   `python3 <path> --files ~/.claude/projects/<cwd-slug>/<session-id>.jsonl`. Paste its output
   under `files:` as a YAML list (one `  - <path>` per line), keeping `files:` the
   last frontmatter key. Fail open: if the extractor errors or lists nothing, omit
   the `files:` key — retrieval just skips the staleness check. This reads the
   transcript mechanically (like the token helper); it is not re-summarising.

   **A summary file may already exist for this session** — a `source: backfill`
   stub the corpus seeder wrote before you wrapped. A live wrap supersedes it: read
   the existing file (the Write guard requires a prior read), then overwrite with
   your `source: wrap-session` version. Wrap always wins over backfill. If the file
   is already `source: wrap-session`, you have wrapped before — overwrite with this
   fresher one.

3. **Write the index entry** in `~/.claude/logs/sessions.md`. First check whether
   the file already contains this session's `<!-- session: <session-id> -->`
   marker — a backfill pass or the SessionEnd floor may already have written one.
   **If the marker exists, update that entry in place:** replace its `## …` title
   line with your title and ensure a `summary:` pointer line sits under the marker.
   Do not append a second entry for the same session. Only if no marker exists,
   **append** a fresh entry (newest entry last):

   ```
   ## <YYYY-MM-DD> · <project> · <title>

   <!-- session: <session-id> -->
   summary: sessions/<YYYY-MM-DD>-<project>-<session-id>.md
   ```

   Keep the marker line exactly as `--print` emitted it: the SessionEnd hook finds
   it to insert the final `tokens:` line beneath it. The `## …` header *is* the
   index line — its title is what a fuzzy search reads first, so make it specific
   ("session-archive trace extractor", not "CMS work").
