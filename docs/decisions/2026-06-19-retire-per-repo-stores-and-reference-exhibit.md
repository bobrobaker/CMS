# 2026-06-19 · Retire the per-repo stores and the forkable reference exhibit (v6 cutover)

**Decision.** With the single Dolt hub live (`$CMS_LANDING_ZONE/monition`, see
`2026-06-19-monition-hub-at-landing-zone.md`) and the fold-everything-in verified, the
four per-repo `monition/` stores (CMS, Corpus, RCA, fathom) are **retired**: their rows
were folded into the hub, so each store dir is deleted (`git rm monition/dump.sql` —
history retains it — plus `rm -rf monition/.dolt`). Host repos now resolve to the hub via
the machine-wide `MONITION_STORE` (global `settings.json` `env`), so no per-repo store and
no re-instrument are needed.

The `CMS/monition` store was also the **forkable reference exhibit** — a tracked
`dump.sql` that `bootstrap.sh` shipped as "a reviewable snapshot of the reference store,"
never auto-loaded (forks start empty). **It too is retired** (decision C of the cutover
confer): forks start empty and learn the row schema from `method/takeaway-store.md`.

**Why.**
- Post-fold the per-repo stores are pure redundancy; the hub is the single store.
- Retirement is safe twice over: every row is in the hub (verified conservation + fold
  commits) *and* every source `dump.sql` is in its repo's git history.
- The reference exhibit was a stale, maintenance-heavy artifact. Refreshing it naively
  from the hub would publish the author's *entire* cross-repo takeaway store (personal +
  project rows, machine-local paths) into the public forkable repo; a curated domain-free
  subset would be ongoing work. The example-rows value it offered is better served by the
  schema documentation in `method/takeaway-store.md`.

**Sequencing.** Deletions + exhibit retirement done now. The **`bootstrap.sh` rework is a
separate, deferred change** (sequencing call in the cutover confer): `init_store()` →
`monition init-store <hub> --dolt` + `monition instrument --store <hub>`, and drop the now
-dead `dump.sql` exhibit note (`bootstrap.sh` ~117–120). Until then that note simply
no-ops (the file is gone).

**Pointers.**
- Cutover confer (monition↔CMS), archived in the monition repo:
  `monition/handoffs/archive/2026-06-19-confer-v6-cutover.md`.
- monition's fold/primitives: `monition/docs/decisions/2026-06-19-init-decompose-store-instrument.md`.
- CMS consumption contract: `2026-06-19-bootstrap-consumes-init-decomposition.md`.
