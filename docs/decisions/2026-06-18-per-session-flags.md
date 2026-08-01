---
status: decided
---
# 2026-06-18 · Per-session flag store — scoped attribution, whole-directory drain

> **Superseded in part (2026-06-18, see `2026-06-18-flag-drain-liveness-scoped.md`):**
> the "whole-directory drain" decided below is wrong under concurrency — the flag
> directory is machine-global and shared by many simultaneous sessions, so a
> whole-directory sweep drains *active* sessions' in-flight flags. The drain is now
> **liveness-scoped** (own session always; other files only if their session is dead).
> Per-session files and the orphan-safety goal are unchanged; only the drain scope is.

> **Premise REFUTED in part (2026-07-31):** the three-way id equivalence asserted below
> does **not** hold for **resumed** sessions. The hook/statusline stdin `session_id`
> carries the *ancestor* session's UUID while `$CLAUDE_CODE_SESSION_ID` carries the live
> one — measured at ~10 of 33 recent sessions on the author's machine, and reproduced in
> the session that found it (payload `916fbb77…`, live `b7b8ef0e…`, whose ancestor
> transcript had been frozen since 2026-07-29). The decision to use per-session files
> **stands**; only its "key by any of the three without coordination" justification is
> wrong. Consequence: `autoflag.py` filed auto-flags under a dead ancestor id, defeating
> both consumers named under **Why** below. Fixed 2026-07-31 — `autoflag.py` now keys off
> `$CLAUDE_CODE_SESSION_ID`, matching the `/flag` skill; see the Producers note.
> **Treat `$CLAUDE_CODE_SESSION_ID` as the single authoritative source** (the same reading
> `session_tokens.py:live_transcript_path` already calls "the authoritative harness session
> id"). ~~Whether the payload's `transcript_path` carries the same ancestor staleness is
> **open** — suspected, not proved.~~ **RESOLVED 2026-07-31: it does NOT.** The staleness
> is **field-specific**. Measured from `autoflag.py`'s own scanpos record in the resumed
> session that found the bug: `transcript_path` named the **live** transcript
> (`b7b8ef0e…jsonl`, read to line 1132) while the same payload's `session_id` was the
> ancestor's — and the ancestor transcript is 515 lines, frozen two days earlier, so a
> hook reading it could not have reached 1132. This also removes the one alternative the
> diagnosis could not previously rule out: the flush race is the sole explanation for the
> 0-of-13, not a stale file.

**Decision.** Move the flag store from a single global file `~/.claude/session-flags.md`
to per-session files `~/.claude/session-flags/<session_id>.md`. The session id is the
Claude Code session UUID — the same value visible to the agent as
`$CLAUDE_CODE_SESSION_ID`, to hooks/statusline as `session_id` on stdin, and as the
transcript filename ~~(verified: all three resolve to the same UUID)~~ **[REFUTED
2026-07-31 — see the note above; resumed sessions break the equivalence]**. ~~So every
producer and consumer can key by it without coordination.~~ **Producers and consumers
must key off `$CLAUDE_CODE_SESSION_ID`.**

**Why.** Two consumers need per-session attribution that a single shared file can't give:

- `/statusline` shows a live count of *this session's* flags (a second widget alongside
  the existing monition-firings `⚑`). A shared file can't say which flags are "mine."
- `/mine-session` can attribute and surface this session's flags distinctly.

**Producers** (write `## [LABEL]` entries to this session's file):

- `/flag` skill — bash-appends to `~/.claude/session-flags/${CLAUDE_CODE_SESSION_ID:-unknown}.md`.
- `tools/autoflag.py` (Stop hook) — ~~writes to `<session_id>.md` using the stdin
  `session_id`~~ **[CORRECTED 2026-07-31]** writes to
  `${CLAUDE_CODE_SESSION_ID}.md`, falling back to the stdin `session_id` only when the env
  var is unset. It does not fall back to the transcript filename stem — ~~that path is
  suspected to carry the same ancestor staleness~~ **[measurement 2026-07-31 shows the
  stem would in fact resolve correctly; it is omitted because deriving identity from a
  path is a second-order inference the harness could change, not because it is stale]**.

**Consumers:**

- `/mine-session` step 0a **sweeps the whole directory**, not just its own file.
- `/postmortem` reads/clears the most-recent `POSTMORTEM` entry, checking this session's
  file first, then any other file the mine-session sweep may have routed here.

**The load-bearing choice: drain scope.** Per-session *files* but a whole-*directory*
drain — deliberately not strict per-session draining. Today's single-file design has a
safety net: any session's `mine-session` drains every pending flag, so a flag dropped in a
session that's never wrapped still gets caught by the next session's mining pass. Strict
per-session scoping would orphan those flags forever — the one failure the flag pipeline
exists to prevent (a dropped lesson). So `mine-session` globs `session-flags/*.md` and
drains all of them, deleting each file as it goes; the statusline reads only the current
session's file. Per-session for *visibility*, whole-directory for *draining*.

**Consequence.** "This session's flags are drained by this session's mine-session" softens
to "this session's mine-session drains this session's flags **plus** any orphans from
un-mined sessions." Accepted: not losing flags beats strict scoping.

**Statusline (machine-local, not part of CMS).** A fork doesn't inherit the author's
statusline, so the CMS machinery must not depend on it — it doesn't; the statusline just
*reads* the per-session file the CMS producers write and counts `## [` entries, resetting
to zero when `mine-session` deletes the file. Two distinct widgets, two distinct signals:
`⚑` = monition firings (transient, TTL'd text), the flag widget = queued `/flag`
bookmarks (count of entries in this session's file).

**Supersedes in part.** `2026-06-18-two-tier-autoflagger.md` (storage path only; the
two-tier design is unchanged).
