---
status: decided
date: 2026-07-05
---

# Housekeep §G1 — retro rating supply (the audit-remediation item-3 clause)

## Context

The 2026-07 machinery audit's item 3 was a housekeep clause consuming Monition's
retro-rating seam. Monition shipped the producer side first — a per-row backlog sampler
(`export-firings --rows-by unrated-priority --sample-per-row N`) and a retro applier
(`rate --from-export`, provenance hardwired to `retro`) — commit `bf04875`, contracts in
`monition/docs/contracts/export-firings.md`. The clause was gated on a manual dogfood
answering one question: **are the stored `situation` excerpts rich enough to rate
relevance from the prompt alone?** The dogfood ran 2026-07-05 (30 retro labels, hub commit
`fisobjklg`) and cleared it — 3% abstain, and the lone abstain was a `situation: None` data
gap, not a thin excerpt. That unblocked the build.

## The seam (Monition owns; CMS consumes)

Monition owns the sampler, the `rating_priority` order (traffic × distance-to-fire/suppress
boundary), and the structural `retro` provenance. CMS's §G1 owns **only cadence, budget,
and consent**. It never re-implements selection or provenance. See
`monition/docs/decisions/2026-07-05-retro-rating-from-export.md` (producer + why retro is
structural) and `monition/docs/decisions/2026-07-04-rating-label-provenance.md` (the
live/retro axis + asymmetric-trust policy).

## Decisions

- **Who rates: an evidence-gated LLM retro-rater (option b), not a human hand-rater.**
  The retro analog of mine-session's live rating pass — rate only what the excerpt
  evidences, cite it, abstain (`outcome: null`) with no evidence. The dogfood showed the
  excerpts support it; (b) is the scalable answer and is what §G1 builds.
- **No model is pinned; the pass inherits the ambient model** the `/housekeep` sweep
  already runs under. Two reasons: (1) "representative of the consumer" is a *utility*
  notion, and retro structurally measures **relevance**, not utility (the rater saw the
  prompt, not the session), so representativeness is not the right selection criterion
  here — accuracy and consistency are; (2) inheriting the ambient model keeps retro and
  live labels under one labeler family (the live pass runs under the session model too),
  and a hardcoded model id is predictably-stale content that rots at the next model bump.
- **Cadence: weekly**, self-gated by a stamp (`$XDG_STATE_HOME/cms/monition-retro-rating.last`,
  `find -mtime -7`), mirroring the §K canary's invoke-every-run/let-the-gate-decide shape.
- **Budget: ~30–50 firings** across the highest-priority rows; `--sample-per-row` toward
  8–10 near the fire/suppress boundary (a small sample misjudges a borderline-helpful row).
- **Consent: one batched accept with per-line veto** — the lighter gate mine-session's
  rating pass uses (a rating is reversible eval data, not durable governance).

## Seam guardrail (load-bearing)

§G1 produces `retro` labels and nothing else. It must **not** touch the fire/suppress gate
or its held-out test set. Retro is asymmetric *training* supervision; the relevance test
set stays **live-only**, and retraining the gate on retro is deferred until volume accrues
under an evidenced weighting scheme.

## Labeler-model provenance — resolved by confer (no column; commit-message convention)

The open question was whether Monition should add a `rated_by_model` column so labeler
drift is auditable if the ambient model bumps. Settled 2026-07-05 by a CMS↔Monition confer
(thread `6a0af776`, archived): **no column now.** Monition's ground-truth check found all
three build-triggers fail — the fact is reconstructable (one retro pass = one atomic Dolt
commit, no squash), there is no near-term consumer (the only one is the deferred, undesigned
retro-weighted retrain), and backfill is a clean per-commit join, not lossy. The column's
real cost is a v10→v11 migration plus a cross-repo `--rated-by-model` flag the sweep would
have to pass on every run.

The one genuine gap Monition surfaced: the labeler model is durable **nowhere** — the
firing rows' `model` is the *fire-time* model, not the rater, and the commit records no
model. Substitute adopted (zero schema cost): **§G1 stamps the ambient model into its
`monition commit` message** as `[rated_by: <model-id>]`, making date→model durable and any
future backfill exact.

**Revisit trigger** — the column graduates from deferred to build the day **any** of: (a)
the retro-weighted retrain scheme is designed with a per-labeler term; (b) the sweep gains
automatic model-threading; (c) sweeps run under mixed models within a short window, breaking
per-commit date→model 1:1. Monition records this trigger durably on its side.

## Records

- Clause: `.claude/skills/housekeep/SKILL.md` §G1 (G2 is the pre-existing row audit).
- Method: `method/takeaway-store.md` §Rating (retro paragraph).
- Registry: `docs/DESIGN.md` (Phase 2 active layer).
