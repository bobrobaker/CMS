# Learning loop — mine the lesson, then house it

**Trigger:** read when setting up or running a session's end-of-session lesson pass, or
when deciding whether a mistake is worth capturing. This doc is the *mining* half —
turning a session into candidate lessons. Where a lesson lands is `lesson-routing.md`;
whether it lands is the consent gate (`write-path.md`).

## The loop

    work → MINE (audit + diagnose) → HOUSE (route) → FIRE (store / governance) → better work

Mining without a governed home accretes flat rule files; a home without mining
instrumentation starves. The loop closes only when both ends exist. Housing is
`lesson-routing.md`; this doc is the mining end.

## Two mining substrates (both ship per-project)

- **Session-end audit** — `session_tokens.py` (SessionEnd hook) sums API usage into the
  session log. The audit is the standing prompt to ask at wrap: what did this session
  waste, repeat, or rediscover? Token waste is the most mechanical lesson source — a
  re-read grep would have answered becomes a read-budget rule.
- **Mistake diagnosis** — when a session went wrong, `extract_session.py` lifts the
  role-labelled transcript (tool noise dropped) so the *why* is diagnosed over the
  actual exchange, not from memory. A diagnosed mistake becomes a trap-shaped gotcha:
  the trigger that should have fired, plus the move to make instead.

## The mining pass

At session end, review for lessons that are **reusable** (would recur) and
**non-obvious** (a future session wouldn't cheaply rediscover them). Mistakes,
gotchas, corrections, and confirmed preferences qualify; routine work does not. For
each candidate: state it as "in situation S, do/avoid X," route per
`lesson-routing.md`, propose through the consent gate. A candidate whose situation has
no name yet is not routable — leave it in session notes; don't force a row.

## Wiring & ownership

- The substrates (`session_tokens.py`, `extract_session.py`) and the orchestrating
  `/mine-session` pass ship together. Monition is a declared dependency, so a fork has the
  store and the automated pass from session one; for a single lesson mid-session, `/codify`
  inserts it directly rather than waiting for the end-of-session pass.
- This mining discipline is canonical here; the Monition module's mine-session template
  mirrors the pass (domain-stripped), propagated by `monition sync` — the same channel
  `lesson-routing.md` uses. Bump and hand off here on any change.
- **Delegated runs route the end pass through the architect.** When buckets are
  dispatched to stateless workers, the workers persist per-bucket gotchas to their
  `Updates` but cannot run the end-of-session pass; the architect runs one run-level mine
  (and one run-level wrap) over the worker results plus accumulated Updates. See
  `dispatch.md` §Architect → implementer.
