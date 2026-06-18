# 2026-06-14 · `/instantiate --store` — opt into a live Monition store at generation

> **Fully superseded by [2026-06-17 — CMS is a forkable reference implementation](2026-06-17-cms-forkable-refactor.md).**
> `/instantiate`, tier-0, and the `--store` flag are gone; the store is now the only path.
> What carries forward is this record's finding — firing provenance can't be backfilled, so
> the store is worth standing up from session one. Kept as a point-in-time record.

**Decision.** Add a `--store` argument to `/instantiate`. The default stays tier-0
(the self-contained flat lessons file + frozen executor, no Monition dependency).
`--store` instead stands up a live Monition store at generation time via `monition
init --adopt lessons.md` — which seeds the curated starter lessons as rows — then
deletes the flat file. Hard precondition: Monition installed; if absent, stop, never
silently fall back to tier-0.

**Why.** Firing provenance — `git_sha` / `git_dirty` / `session_id` / `situation` on
each `firings` row (store contract v4/v5) — is capture-time-only and **impossible to
backfill**. Tier-0 logs no firings at all, so every pre-adoption session is eval-data
lost forever. For a user committed to evals and willing to rate firings, starting on
the store captures that provenance from session one. Making it an explicit flag — not
the default, and not a buried judgment call inside step 5 — keeps the cheap,
dependency-free tier-0 as the default while giving the committed user a one-token
opt-in.

**Choices within it.** Seed via `monition init --adopt` rather than an empty `monition
init`, so a `--store` project keeps its starter lessons instead of launching blind.
Hard-fail (not fall back) on a missing module, because the user explicitly asked for
the store; a silent tier-0 would hide that the request wasn't honored.

**Cost accepted.** Adoption is one-way; the project is now coupled to the installed
Monition module (hooks fail-open, so it degrades rather than breaks). Day-one vs.
after-first-mining barely differ — little fires early — but the flag works at either
moment, so it doesn't force "literal day one."

**Not done (gated, unchanged by this).** The eval *consumers* — the EV firing engine
and tier-3 evaluation — remain unbuilt and gated on rating volume. `--store` only
starts the *capture*; it does not make evals available sooner.
