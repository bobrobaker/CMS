# Bucket [B06]: Dogfood on CMS DESIGN.md + queue fork rollout

Parent: ../workstream.md
State: done
Goal for session: Make CMS's own DESIGN.md conform; queue per-fork adoption.
Target duration: 25 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- Two closing acts on the same theme: (1) prove the convention by applying it to CMS's own
  current-architecture (the freshness check must pass on it); (2) coordinate rollout to
  downstream forks via the landing zone — not by reaching into their repos.

## Tasks

- [ ] Reconcile `docs/DESIGN.md §"Current architecture"` to conform to B04's convention; run B05's freshness check against it until it passes (dogfood).
- [ ] Confirm `cms update` + drift-warn (B01/B02), the backfill scaffold (B03), and the arch-doc freshness check (B05) are in the managed vendored set so an adopting fork picks them up. (B05's check rides inside the already-vendored `lint_skeleton.py`, so verify it landed in `SHARED_CHECKS` — it propagates automatically once there.)
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
- [2026-06-20 16:50] (pre-existing B07 rollout note retained below.)
- [2026-06-20] **Dogfood done.** Marked `docs/DESIGN.md` `doctype: architecture` (honors the
  standing call "CMS arch stays in DESIGN.md" — whole-file mark, no separate file); the B05
  freshness check now passes on it (0 errors), and `cms_lint` is clean repo-wide.
  - **Surfaced by the dogfood (real drift, fixed):** 3 path-spans in DESIGN.md referenced things
    not in CMS's tree — `monition/` (×2: a retired per-repo dir + a standalone-forker fallback)
    and `tools/lint.py` (the fork wrapper, in the roadmap narrative). Reworded to prose (they're
    fork/standalone/historical mentions, not CMS references). Also fixed a **stale CLAUDE.md Map
    entry** that still claimed `monition/` was "this repo's store" — it was retired in the v6 hub
    cutover; CMS now joins `$CMS_LANDING_ZONE/monition` via `monition instrument`.
  - **B05 check refinement (dogfood-driven):** a leading-slash token (`/wrap-session` and other
    `/slash-commands`, or an absolute path) is now *skipped* (not a repo-relative reference),
    instead of ERRORing — DESIGN.md is full of slash-commands. Fixed in both linters + mirror test.
  - **Task 2 (vendored set confirmed):** `MANAGED_TOOLS` = craft_reminder, autoflag,
    lint_skeleton (carries B02 drift-warn + B05 freshness), backfill_decision_status (B03);
    `SHARED_CHECKS` includes `check_architecture_freshness`; `cms update` verb present.
  - **Task 3 (rollout):** `$CMS_LANDING_ZONE/handoffs/2026-06-20-ws2-fork-rollout.md` — per-fork
    3-step adoption (cms update → backfill → adopt doctype), opt-in + drift-detected, fork list
    private. Suggested order: monition first, then clean forks, then RCA/fathom (verify-first).
- [2026-06-20] **Confer with brain2 (final).** All C, converged. Fixes built:
  - **A-1 (real code finding):** the B06 leading-slash skip had made B05's `isabs` ERROR branch
    *dead code* (absolute paths never reached `_resolve`), silently reversing the typo/`/etc/passwd`
    catch — and the mirror test couldn't see it (both copies equally dead). Fixed: a `/slash-command`
    (single segment, no extension) is skipped; an absolute path flows through and ERRORs again.
    Added slash-command + absolute fixtures to `test_lint_mirror.py` to lock parity.
  - **A-2:** RCA rollout note made executable — `--update` does a *silent whole-file cp* (verified,
    no guard), so the note now gives the diff-before-update step + the FORK_CHECKS lift-first remedy.
  - **A-3:** named the escape hatch (drop the marker → self-gate) and the **reword-vs-fix rule**
    (reword to prose only for category-errors; FIX a real drifted in-tree reference) in BOTH the
    rollout handoff and `method/architecture-doc.md` so forks inherit the discipline.
  - **Q2 (whole-file ratified; erosion tradeoff parked C):** whole-file FRESH puts the roadmap
    under the gate, so the easy path for future roadmap edits is "drop the backticks." Accepted now
    (the 3 reworded spans were genuine category-errors). **Revisit trigger:** when the roadmap
    accumulates several reworded-to-prose spans that *should* be structured cross-repo references,
    that's the signal to add section-awareness (a doctype-region marker / narrative-section opt-out)
    — built on a real caller, not speculatively.
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
