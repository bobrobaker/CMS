---
name: mine-session
description: End-of-session mining pass — review this session for reusable lessons and house them in the takeaway store with explicit triggers. Use when the user invokes /mine-session, says "mine this session" / "save the takeaways", or is wrapping up a session that hit gotchas worth keeping. NOT for mid-session one-offs the user wants codified immediately (that's /codify, which can also insert a takeaway).
---

# mine-session

You are mining this session for takeaways. The store's semantics live in
`method/takeaway-store.md` — read it before your first run in a session.

0a. **Drain session flags — run this before anything else.** Flags live per-session under `~/.claude/session-flags/<session_id>.md`, in a **machine-global directory shared by every concurrent Claude session**. Drain by *liveness* — never the whole directory, or you steal in-flight flags out from under another running session (the concurrency failure this scoping exists to prevent):
   - **This session's file** (`$CLAUDE_CODE_SESSION_ID.md`) — always in the worklist.
   - **Other files** — include one ONLY if its session is no longer live (a genuine orphan from a closed, un-mined session). A session is live if `~/.claude/sessions/*.json` holds a record whose `sessionId` equals the filename's id. **Never drain a file whose session is still live** — those flags belong to an active concurrent session. When liveness can't be determined (registry unreadable), treat as live and leave it.
   - Build the worklist: `ls ~/.claude/session-flags/*.md`, then for each, keep it iff its id == `$CLAUDE_CODE_SESSION_ID` OR its id is absent from the live registry. Read the kept, non-empty files.
   - Surface this session's flags first, then orphans. `POSTMORTEM` flags are high-priority — do not mine past them; ask whether to invoke `/postmortem` now or defer. `MONITION`/`GOVERNANCE` are pre-routed seeds. `GENERAL` joins the normal mining review.
   - Delete only the files you actually drained (`rm`). **Fail open:** absent directory, unreadable file, or unreadable registry → skip that file silently (when in doubt, do NOT delete).

0b. **Scan for admitted mistakes.** Before the rating pass, review the session for any moment where Claude explicitly admitted to an error — especially assertions made without verification that turned out to be wrong ("I was wrong about X", "I should have checked", "I asserted X without verifying"). Each such moment is a candidate seed for a governance change: flag it for routing in the mining pass. The question is always: *what would have prevented this class of mistake?* (The `autoflag.py` Stop hook is the mechanical mirror of this scan — it regex-catches the same admitted-error class live and writes a `GOVERNANCE` flag, so step 0a may already hold some.)

0c. **Rate what fired (the eval pass) — run this first, before mining.** The
   fire/suppress gate trains on rated firings, and fire-time rating collects ~none (a
   session mid-task won't stop to grade an injection). So rate here, **warm**, with the
   session still in context — LLM-auto, evidence-gated, bulk-confirmed.
   - **Pull the worklist, highest-value first:**
     `monition export-firings --unrated-only --session "$CLAUDE_CODE_SESSION_ID" --order-by priority`.
     `--order-by priority` is the head-not-tail metric — `rating_priority` = traffic ×
     distance-to-fire/suppress-boundary, cold-start rows rank high; monition owns the
     math, you only consume the order. If `$CLAUDE_CODE_SESSION_ID` is unset, scope with
     `--since <today>` instead. **Fail open:** if the `monition` CLI or live store is
     absent, skip the pass entirely.
   - **Walk the top N** (a budget — ~15; head, not tail; stop when `rating_priority`
     drops off or evidence runs out — skip the long tail). For each firing, look in the
     session for evidence the injected `one_liner` (it fired at `trigger_context` /
     `situation`) actually mattered: it **changed an action**, was **visibly ignored**,
     or was **contradicted** by what you did.
   - **Propose a rating ONLY where the session evidences it**, with a mandatory one-line
     citation of *what in this session* shows it. **No evidence → no rating** — never pad
     to hit coverage; an unsupported `helpful` is directional bias in the eval set, worse
     than a label missing at random. A cold dispatch-mine (an architect mining workers it
     didn't live through; see `method/learning-loop.md` §Wiring) evidences ~nothing and
     correctly proposes ~0.
   - **Present ONE batch for bulk confirm** — all proposed ratings at once, each line
     `<firing_id> helpful|noise — <one-line evidence>`. The user accepts the batch in a
     single gesture with per-line veto/flip. This is a **lighter gate than rows** (`method/
     write-path.md`): a rating is reversible eval data, not durable governance, so don't
     run rows-grade scrutiny per line.
   - **Apply the accepted lines:** `monition rate <firing_id> helpful|noise` for each.
     These leave uncommitted store state that folds into the `monition commit` at step 5
     (snapshot them on their own first only if you want them out of an unrelated diff —
     `method/takeaway-store.md` §Dolt mechanics).

   Then mine for new lessons:

1. Review the session for lessons that are **reusable** (would recur) and
   **non-obvious** (a future session wouldn't rediscover them cheaply). Mistakes,
   gotchas, corrections, and confirmed preferences all qualify; routine work does not.
   **A candidate already covered by an existing takeaway is not a new lesson — don't
   duplicate it; but if the covering row is a low-firing `on_demand` row, run
   `monition log-recurrence <id>` (optionally `--context "<why it recurred>"`) so the
   recurrence becomes scorer signal. Skip this for high-firing / `session_start` rows —
   their normal fire+rate loop already carries their value.**
2. **Route each candidate per `method/lesson-routing.md`** — not every lesson is a
   row. Lessons an existing skill, hook, prompt, or linter already owns, and
   always-on rules, are proposed as governance edits through the same consent gate;
   only lessons that route to the store continue below. Name the deciding test in
   the proposal.
3. For each store-routed candidate, draft the full row: `kind` (gotcha/rule/preference),
   `trigger_kind` + `trigger_spec` (*when should this fire?* — the design decision;
   edit_path glob, session_start, or on_demand), `one_liner` (what gets injected —
   make it a trap-warning, not a description), `full_content` (the why + the
   workaround), `source` (session/commit).
4. **Show the proposed rows and get acceptance before inserting** (consent gate).
5. Insert accepted rows (`monition add …`), then snapshot the store:
   `monition commit -m "mine: <session topic>"`. The store is the hub at the landing
   zone (`MONITION_STORE`), gitignored and unpublished — that Dolt commit *is* its
   version control, so there is nothing to stage into this repo's git. Any working-tree
   `git commit` of code/docs is separate from the store snapshot.
6. **Routing a domain-free lesson — CMS is the upstream, so promote, don't queue.** In
   a downstream fork a transferable lesson is queued to `upstream-candidates.md` for the
   mirror-back sweep that pulls it *up*; CMS has no upstream, so decide now instead. If
   the lesson would help a *fork* (it survives domain-stripping), propose it into the
   shared machinery — a `method/` doc, a `starter/` template, or a shipped takeaway —
   through the consent gate; if it only applies to building CMS or its modules, leave it
   a local row (`--reach project`, the default). A row meant to fire across every repo,
   not just where authored, is `--reach general`.
