---
name: eos
description: End-of-session closeout — run the three wrap-up steps in order: mine the session for takeaways, archive the session, then commit the work. Use when the user invokes /eos, says "close out" / "end of session" / "wrap up for the day", or otherwise signals the session is done.
---

# eos — end-of-session closeout

First, one hygiene glance — two cheap checks, each at most one printed line, never
blocking and never acted on without a yes:

- **Housekeep staleness** — read the stamp `/housekeep` writes on completion:
  ```bash
  f="${XDG_STATE_HOME:-$HOME/.local/state}/cms/housekeep.last"
  if [ -f "$f" ]; then a=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 86400 ));
    [ "$a" -ge 2 ] && echo "housekeep last ran ${a}d ago"
  else echo "housekeep: no run recorded"; fi
  ```
  If it prints, suggest a `/housekeep` (morning cadence) in one line — don't run it.
- **Handoff consume-check** — if this session picked up, consumed, or resolved a
  handoff doc, close its lifecycle now (delete it, or archive with a stamp per
  `handoff/SKILL.md`); a consumed handoff left `status: open` is exactly the pile the
  consume-then-delete rule exists to prevent. Skip silently if none was touched.

Then run these three in order, pausing between each — don't batch them, since each can
change what the next one sees. If a step surfaces something needing the user's call,
stop there and ask.

1. **Mine** — invoke the `mine-session` skill. Capture reusable takeaways while the
   session context is still fresh (this can write to the takeaway store).
2. **Wrap** — invoke the `wrap-session` skill to archive a findable session summary.
3. **Commit** — stage and commit this session's work. Review `git status` first and
   stage this session's files explicitly — `git add -A` only after confirming nothing
   foreign is present (a concurrent session's artifacts or stray untracked files
   sweep in silently). Push if the repo's workflow expects it. Propose a message;
   include anything steps 1–2 wrote, so the session archive lands in the commit.

4. **Anchor** — record a replay anchor for the commit just made, so the session→anchor
   join exists for later causal re-grading of this session's firings (rationale:
   `docs/decisions/2026-07-07-cms-side-monition-value-audit-carries.md`). Guarded and
   **fail-open** — runs only when `monition` is on PATH and the repo is monition-wired, and
   never blocks close-out:
   ```bash
   if command -v monition >/dev/null 2>&1 && { [ -n "${MONITION_STORE:-}" ] || \
      [ -d "$(git rev-parse --show-toplevel 2>/dev/null)/monition" ]; }; then
     monition snapshot --session "${CLAUDE_CODE_SESSION_ID:-}" >/dev/null 2>&1 || true
   fi
   ```
   Skip silently otherwise (not installed, or no store joined).
