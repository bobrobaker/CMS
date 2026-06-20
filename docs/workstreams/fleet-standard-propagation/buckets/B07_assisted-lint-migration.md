# Bucket [B07]: Assisted `lint.py` migration (reach the existing frozen-copy fleet)

Parent: ../workstream.md
State: done
Goal for session: Migrate existing forks' frozen `lint.py` to the wrapper, safely.
Target duration: 30 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- The capstone of the propagation half: B01 built the seam + `--update`, but `--update`
  deliberately won't touch a legacy frozen `lint.py` — so the *existing* fleet (the whole point
  of WS2) stays on stale checks until migrated. This bucket does that migration, confirmation-
  gated (same shape as B03's scaffold).

## Why it's safe (fleet data, brain2-verified 2026-06-19)

- **4/5 forks are clean frozen copies** (Corpus, RCA, monition, portfolio-site): `lint.py` =
  `{check_relative_links, check_opening_thesis}` (an older skeleton), **no local additions** →
  auto-replace with the wrapper is a strict upgrade (they even *gain* `check_decision_status`).
- **1 diverged** (fathom: + a local `check_causal_terminology`, a fathom-domain check that
  stays project-specific) → flag for manual extraction into `FORK_CHECKS`, do not auto-replace.

## Tasks

- [ ] A migrator (CMS-side tool/mode, run against a fork) that classifies its `tools/lint.py`:
      **wrapper** (has `import lint_skeleton` → skip), **clean-frozen** (shared-check region
      byte-identical to a known skeleton lineage, no extra defs → auto-migratable),
      **diverged** (extra defs, or an edited shared-check body → manual).
- [ ] Auto-migrate the clean-frozen case: replace `lint.py` with the wrapper, then write the stamp.
- [ ] Diverged case: emit a worklist naming the fork-local check(s) to move into `FORK_CHECKS`;
      write nothing until a human confirms (proposed-then-confirmed, per monition §4).
- [ ] Never clobber: the auto gate is **byte-identical shared-check region vs skeleton lineage**
      (a diff), NOT merely "no added defs" — a fork could have edited a shared check's body in place.

## Required touchpoints

- `bootstrap.sh  grep -n "lay_down_lint_wrapper"  the wrapper heredoc + legacy detection`
  The migrator reuses the wrapper form and the legacy-detection seam.
- `tools/lint_skeleton.py  (full)  SHARED_CHECKS, run()`
  The skeleton lineage to diff a frozen copy against.
- `B03_backfill-scaffold.md  grep "## Updates", then read from that offset`
  Reuse the scaffold-with-confirmation shape (worklist → confirm → write).

## Design direction

- **Confirmation-gated, never silent** (cross-bucket invariant): auto-migrate only the
  byte-identical clean case; everything else is a proposal a human accepts.
- The "skeleton lineage" check needs the set of historical clean-skeleton hashes (or a structural
  diff that ignores the managed-check set CMS currently ships). Decide and record which.
- Reuses B01's `lay_down_lint_wrapper` and writes the stamp on success (consistent with `--update`).
- Run per-fork; the concrete fork list lives in the landing-zone rollout handoff (B06), not here.

## Validation

- Clean frozen `lint.py` (the 4-fork shape) → auto-migrated to wrapper; `python3 tools/lint.py`
  then runs the *current* managed checks (incl. `check_decision_status`) + exits 0.
- Diverged `lint.py` (fathom shape) → NOT auto-replaced; worklist names `check_causal_terminology`.
- A `lint.py` with an edited shared-check body → classified diverged (not clobbered).

## Done criteria

- [x] Tasks complete.
- [x] Validation passes (clean / diverged / edited-body cases).
- [x] Bucket `Updates` records discoveries/gotchas/handoff.
- [x] Parent workstream progress updated.

## Updates

- [2026-06-19 16:00] Created (user-approved new bucket from the impl-review confer). Fleet data:
  4 clean (auto), 1 diverged (fathom, flag). Depends on B01's seam (done).
- [2026-06-19 16:40] Done + validated. Built `tools/migrate_lint.py` (CMS-side): classifies a fork's
  `lint.py` as wrapper / clean / diverged / no-lint; dry-run by default, `--apply` migrates only the
  CLEAN class. Clean path **reuses `bootstrap.sh --update`** (single source for the wrapper) after
  backing up + removing the frozen copy. Diverged → worklist, never touched.
  - **Code-review fixes applied:** (1) block extraction now bounded by **indentation**, not a
    regex-to-next-def — the old form swallowed trailing `CHECKS=`/`main()` into the last check,
    falsely flagging it as edited; (2) **`SHARED` derived from `lint_skeleton.SHARED_CHECKS`+`REPO_CHECKS`**
    — the review caught it as a *re-introduction of the very `MANAGED_TOOLS` duplication WS2 just removed*;
    (3) `migrate_clean` backs up + restores `lint.py` on bootstrap failure, and the per-fork loop
    continues on error instead of aborting.
  - **Accepted limitation (review finding 4):** the CMS pre-commit refreshes the manifest from the
    *working tree*, not staged blobs — a partial-stage commit of a managed tool could ship a manifest
    describing uncommitted content. **Deferred on cost/benefit** (partial-staging a managed tool is
    rare; the manifest is advisory). *Rationale corrected (confer):* a staged-blob fix would NOT
    reintroduce duplication — bootstrap already owns `MANAGED_TOOLS`, so a `--refresh-manifest --staged`
    reading `git show :tools/$f` over that list adds nothing new. Cheap future option: pre-commit WARNs
    when a managed tool is *partially* staged (turns the silent niche into a loud one in a few lines).
  - Validated: clean/diverged/wrapper/no-lint classify correctly; over-capture regression (frozen copy
    of current skeleton → clean, no false diff); genuine body-edit still flagged; `--apply` migrates +
    fork gains `check_decision_status`; idempotent; diverged untouched.
