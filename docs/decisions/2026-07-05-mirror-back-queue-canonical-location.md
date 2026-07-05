---
status: decided
date: 2026-07-05
---

# Mirror-back: one canonical queue location (landing-zone hub), and §E reads it

## Context

An audit of the mirror-back sweep (2026-07-05) found it under-wired on the consumer side
and split on *where the queue lives*:

- **Producer split.** `/codify` appended candidates to `$CMS_LANDING_ZONE`-preferred
  (`upstream-candidates.md`), while a fork's `/mine-session` (fork-overrides step 6) wrote
  **repo-local** `handoffs/upstream-candidates.md`. The mirror-back sweep and `/housekeep`
  §E read **repo-local** only. So a codify-queued candidate on a hub could be written to
  one place and swept from another — missed.
- **Consumer under-wiring.** `/housekeep` §E scanned only the *current repo's* queue, so
  running it in CMS never surfaced a *fork's* candidates; the sole cross-fork harvest was
  the manual CLAUDE.md sweep. Evidence it rots unrun: a genuine fathom candidate
  (2026-07-04) sat 3 days unharvested.

Prior narrowing (2026-07-02, `docs/debt.md`): row-shaped lessons moved to the Monition hub
(`reach: general`), so the queue now carries **teaching-surface proposals only**
(`method/`, skills, `starter/`, linter). That shrank the channel but didn't fix *where* it
lives.

## Decision

**One canonical queue location, resolved identically by every producer and consumer:**
`$CMS_LANDING_ZONE/handoffs/upstream-candidates.md` when a landing zone is set — else the
fork's own `handoffs/upstream-candidates.md` (a standalone forker with no hub).

- On a shared hub, **every fork appends to the one queue**, so a single read surfaces all
  forks' open candidates — no sibling-directory enumeration, no machine-local paths in the
  shared skill (keeps it forkable).
- **`/housekeep` §E now reads that canonical queue** and counts only *open* candidates
  (dated `YYYY-MM-DD |` lines, not struck-provenance blocks). This gives the cross-fork
  visibility a per-repo scan missed — the detection half becomes automatic cadence.
  **Resolution stays manual + consent-gated** (the sweep): §E surfaces "N open — mirror-back
  due"; a human proposes each through the gate and strikes the landed ones.

### Why up (hub), not down (repo-local + sibling-scan)

Matches `/codify`'s existing landing-zone intent (down would *revert* it); keeps the shared
skill forkable (a repo-local design would need a machine-local sibling-directory scan in
`/housekeep`); and the hub *aggregates for free*, so §E needs no enumeration logic.

## Scope of change

`CLAUDE.md` mirror-back rule (canonical location defined once, referenced by the rest);
`mine-session.fork-overrides.md` step 6 (repo-local → canonical); `/housekeep` §E (bash +
report); `docs/DESIGN.md` upstream-contract section (currency). `/codify` already resolved
to the canonical location — unchanged.

## Migration

Clean cutover: the only open candidate anywhere was fathom's, harvested the same day into
`mine-session` step 0c (the three-bucket rating rubric) and struck from fathom's queue.
CMS and monition repo-local queues held zero open candidates. Future candidates land in the
hub queue.

## Supersedes

The **per-fork-repo-local-queue** aspect of
`docs/decisions/2026-06-13-mirror-back-dispatch-and-decisions-shelf.md` (annotated there).
That decision's dispatch/decisions-shelf substance stands; only the queue *location* moves
to the hub.

## Non-goals

Does **not** auto-fire the sweep — resolution needs judgment and consent, so §E owns
automatic *detection* and the sweep owns manual *resolution*. Does not touch the
teaching-surface-only charter (2026-07-02) or the row→hub routing.
