---
status: decided
---
# 2026-06-18 · /housekeep — a transient-store sweep, not a doc audit

**Decision.** Add a `/housekeep` skill that sweeps the system's *transient* stores for
orphaned or over-horizon residue and acts on what's safe. Scope v1 = A–F:

- A — unwrapped sessions (calls `archive/backfill.py --dry-run`, proposes the real run)
- B — orphaned flag files from dead sessions
- C — over-horizon `open` handoffs
- D — stale `open` confer threads
- E — queued `upstream-candidates.md` (report-only)
- F — abandoned git worktrees

It runs **on-demand + daily cadence**, so it is **silent when clean** (one line, no
sections).

**The load-bearing choice: a three-tier action split, with the skill's own write
permission split the same way.** Mirrors the Tier-3 philosophy in `method/tooling.md`
("report and propose; auto-apply only the mechanical class"):

1. **Auto-reap** — only the two actions that *cannot lose information*: deleting *empty*
   dead-session flag files, and `git worktree prune` of directories already gone.
2. **Propose** — every real change (delete/promote a handoff, archive a confer thread, run
   backfill, run `/mine-session` to drain non-empty orphan flags, remove an abandoned
   worktree).
3. **Report-only** — E, and the deferred-G marker.

**Why these boundaries.**

- **Never `rm` a non-empty flag file.** Un-mined flags carry lessons; auto-deleting them
  destroys exactly what the orphan-safety design preserves. So non-empty orphans are
  *proposed* (→ `/mine-session`), never reaped. (See `2026-06-18-flag-drain-liveness-scoped.md`
  for the liveness rule this reuses — never touch a *live* session's file.)
- **It calls its dependencies, never duplicates them.** backfill's `--dry-run` already
  computes the unwrapped-session set; mirror-back owns E's resolution. Reinventing either
  would silently diverge from the real criteria.
- **It is not the Tier-3 doc audit.** Tier-3 also covers summary/source drift, merge
  candidates, and always-on-layer leanness — judgment-heavy reads left out here. `/housekeep`
  is the orphan/staleness subset only; the skill and this doc say so to stop a later session
  from assuming the name means the whole Tier-3 pass.

**G is deferred, not dropped.** Reaping monition rows (retire noise-heavy, widen/fold
never-fired) is the `method/takeaway-store.md` audit cadence whose engine is `monition
score` — a later phase blocked on an ongoing refactor. Rather than implement the EV read
early or lose the intent, `/housekeep` prints a one-line deferred marker each run so it
resurfaces when the refactor lands. (Note: `monition rate` produces eval data on *firings*;
it does not itself reap rows — the audit cadence is the separate read that does.)

**Cadence is recommended, not wired.** The skill is built silent-when-clean so it's safe to
schedule daily, but actually scheduling it (via `/schedule` or a hook) is left to the user —
outward-facing, their call.
