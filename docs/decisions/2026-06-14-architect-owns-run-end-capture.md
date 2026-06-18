# 2026-06-14 · The architect owns run-end mine + wrap for delegated runs

**Decision.** When a run delegates its buckets to stateless workers an orchestrator
tears down (the architect → implementer mode, internal or external), the **architect** —
the one context that spans the whole run — owns the two session-end disciplines the
workers cannot:

- **Per-bucket capture stays the worker's job.** Execution-protocol steps 8–9 already
  persist each bucket's discoveries/gotchas/handoff to the bucket and workstream
  `Updates` on disk; those survive teardown. This decision changes nothing there — it
  covers only what does *not* survive: routing lessons to the store (`/mine-session`)
  and the findable archive entry (`/wrap-session`).
- **Run-level granularity, not per-worker.** One mine pass over the worker results in
  the architect's window plus the bucket `Updates` on disk; one rung-2 wrap per run with
  workers as sub-sections — matching the per-run archive granularity set by
  `2026-06-13-external-teardown-session-capture.md`. A worker mining its own 5-minute
  slice produces the thin, dutiful rows the store rejects (`takeaway-store.md`: sparse
  honest labels beat dense dutiful ones); mining is a whole-arc, end-of-run review, and
  cross-bucket lessons only resolve from the full arc the per-bucket worker never sees.
- **Per-worker self-wrap stays available.** A worker that merits its own findable entry
  still writes its rung-2 as its final turn (capture-then-close, per the external-teardown
  decision); the architect's run-level wrap is the default, not a replacement.

**Why now.** The 2026-06-13 external-teardown decision wired *wrap* for a session an
external runner closes, but left two holes: it never named an owner for *mine*, and it
scoped only the external-runner case, not the internal architect-as-runner one. An
automated workstream (agent per bucket) therefore lands its diffs while its lessons never
reach the store and no archive entry is written — the learning loop's HOUSE→FIRE half
goes dark exactly when work is most parallel. The gap is invisible from inside CMS, which
is doc-shaped and never dogfoods agent-per-bucket execution; it bites only the code-heavy
downstream projects CMS generates.

**CMS implements.** This file; the run-end note in `method/dispatch.md` §Architect →
implementer; the operative step in the dispatch skill (`payload/skills/dispatch`); the
ownership line in `method/learning-loop.md` §Wiring. Orchestrator-side enforcement
(gating teardown on the wrap artifact existing) remains the runner's, per the
external-teardown decision's boundary.

**Provenance.** Session audit of context-management coverage under agent orchestration,
2026-06-14.
