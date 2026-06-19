---
status: decided
---
# 2026-06-18 · Flag drain is liveness-scoped, not whole-directory

**Decision.** `mine-session` step 0a drains flag files by **session liveness**, not by
sweeping the whole `~/.claude/session-flags/` directory:

- This session's own file (`$CLAUDE_CODE_SESSION_ID.md`) — always drained.
- Any other file — drained ONLY if its session is no longer live, i.e. no
  `~/.claude/sessions/*.json` record carries that `sessionId`. A file whose session is
  still live is left untouched. When liveness is indeterminate (registry unreadable),
  treat the file as live and leave it.

**Why (the incident).** The flag directory is **machine-global** and shared by every
concurrent Claude session — in practice dozens run at once. The prior call
(`2026-06-18-per-session-flags.md`) had `mine-session` sweep and delete the *entire*
directory to avoid orphaning flags from sessions that were never mined. Under
concurrency that sweep drains **active** sessions' in-flight flags: a `/mine-session`
or `/eos` in session B deletes session A's still-accumulating flags and mines them in
B's unrelated repo context. This was observed live — a `/flag` in this session lost a
prior real flag (the `agent-spawn` `.venv` gotcha) to another session's mining pass.

**Why this fix is correct.** The orphan-safety goal — don't lose flags from un-mined
sessions — only ever concerned *dead* sessions. Protecting *live* sessions costs nothing
against that goal: a live session will drain its own file when it mines. So scoping by
liveness keeps the safety net (dead sessions' flags still get swept by the next miner)
while making it structurally impossible to steal a running session's flags. The
fail-safe is conservative: indeterminate liveness → leave the file (a missed orphan is
recoverable; a stolen active flag is silently mis-mined).

**What's unchanged.** Per-session files, the statusline reading only the current
session's file, and producers (`/flag`, `autoflag.py`) writing to
`<session_id>.md`. Only `mine-session`'s drain scope changed.

**Cost accepted.** `mine-session` must read the live-session registry
(`~/.claude/sessions/*.json`) to classify other files — a cheap directory read,
fail-open. A truly orphaned file from a session whose id still lingers in the registry
won't be swept until that record clears; acceptable (it's caught on a later pass).

**Supersedes in part.** `2026-06-18-per-session-flags.md` (drain scope only).
**Reversed a call I argued for.** The user's original instinct was strict per-session
scoping; I pushed whole-directory sweep and under-weighted that the directory is global
and sessions concurrent. Liveness-scoping is the synthesis: per-session safety *and*
orphan recovery.
