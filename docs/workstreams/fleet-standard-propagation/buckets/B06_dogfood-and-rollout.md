# Bucket [B06]: Dogfood on CMS DESIGN.md + queue fork rollout

Parent: ../workstream.md
State: later
Goal for session: Make CMS's own DESIGN.md conform; queue per-fork adoption.
Target duration: 25 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- Two closing acts on the same theme: (1) prove the convention by applying it to CMS's own
  current-architecture (the freshness check must pass on it); (2) coordinate rollout to
  downstream forks via the landing zone — not by reaching into their repos.

## Tasks

- [ ] Reconcile `docs/DESIGN.md §"Current architecture"` to conform to B04's convention; run B05's freshness check against it until it passes (dogfood).
- [ ] Confirm `cms update` + drift-warn (B01/B02) and the backfill scaffold (B03) are in the managed vendored set so an adopting fork picks them up.
- [ ] Write a **rollout handoff in the landing zone** (`$CMS_LANDING_ZONE/handoffs/`) listing the concrete downstream forks, each to: `cms update` to pick up the new checks, then run the backfill scaffold once against its own registry, then adopt the arch-doctype on next touch. The fork list stays in the landing-zone handoff, **not** in this public repo.
- [ ] Note the opt-in nature: rollout is per-fork cadence with drift-detection, never a forced push.

## Required touchpoints

- `docs/DESIGN.md  §"Current architecture"  (full section)`
  The dogfood target — edited here.
- `method/architecture-doc.md  §section template`
  The convention CMS's own doc must conform to (B04 output).
- `B04_arch-doc-convention.md  grep "## Updates"` and `B05_arch-doc-freshness-check.md  grep "## Updates"`
  Handoff: convention shape + how to run the freshness check.

## Conditional touchpoints

- `docs/DESIGN.md  §Roadmap → Workstream 2`
  Read only to update the WS2 phase status to done/landed at workstream close.

## Do-not-read / avoid

- Downstream fork repositories.
  Rollout is coordinated by handoff; do not edit other repos from this bucket.

## Design direction

- **Dogfood is the real exit criterion** for the convention: if CMS's own architecture doc
  can't conform + pass the freshness check, the convention is wrong — fix B04/B05, don't bend
  the doc.
- **Public-repo hygiene:** the rollout handoff (with the named fork list) lives in the landing
  zone, which is private; this bucket file and DESIGN.md name no private forks.
- Rollout is **opt-in + drift-detected** (cross-bucket invariant) — the handoff invites, it
  does not regenerate or rewrite.

## Validation

- B05 freshness check passes on the reconciled `DESIGN.md`.
- `tools/cms_lint.py` passes repo-wide.
- The landing-zone rollout handoff exists and lists each fork's three steps.

## Done criteria

- [ ] Tasks complete.
- [ ] Validation passes.
- [ ] Bucket `Updates` records discoveries/gotchas/handoff.
- [ ] Parent workstream `Progress` set to done; WS2 phase in DESIGN.md marked landed.

## Updates

- [2026-06-19 14:30] Created. Handoff: none yet. Gotchas: none yet.
- [2026-06-19 16:50] **`lint.py`-migration rollout guidance (brain2-verified fleet, confer `…-b07-review`).**
  Run `python3 tools/migrate_lint.py <fork>` **dry-run per fork first**, eyeball the classification, then:
  - **Corpus, monition, portfolio-site** — clean, byte-identical `check_relative_links` (benign
    old-skeleton ancestor; diff vs current is the payload→tools evolution, not local edits) → safe to
    `migrate_lint.py --apply`.
  - **RCA** — clean but a **different** `check_relative_links` (14 vs 11 lines); the one fork whose
    `⚠ body differs` isn't auto-attributable as benign → **eyeball before `--apply`** (confirm no local edit).
  - **fathom** — DIVERGED (`check_causal_terminology`, a fathom-domain check → stays project-local) →
    migrate, then move that check into the wrapper's `FORK_CHECKS` (worklist, manual).
  - `check_opening_thesis` is identical across all 4 → no signal there.
  This rollout edits *other* repos — keep it confirmation-gated and per-fork (don't batch-`--apply` blind).
